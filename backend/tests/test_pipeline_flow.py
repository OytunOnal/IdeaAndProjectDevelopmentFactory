"""End-to-end pipeline flow tests with mocked LLM calls.

Verifies the LangGraph routing: idea conversation pause, per-document
approval gates, revisions, research review, spec/quality gates, the
quality improvement loop, and packaging. No real LLM/API calls are made.
"""

import pytest

import app.agents.collaboration as collaboration_mod
import app.agents.idea_analyst as idea_analyst_mod
import app.agents.packaging as packaging_mod
import app.agents.quality as quality_mod
import app.agents.research as research_mod
import app.agents.specification as specification_mod
from app.agents.decision_handler import resolve_decision
from app.agents.graph import pipeline


def _base_state(**overrides) -> dict:
    state = {
        "project_id": "test-project",
        "project_name": "TestApp",
        "current_phase": "discovery",
        "pipeline_status": "running",
        "current_agent": "orchestrator",
        "api_key": "",
        "autonomy_level": {"strategic": "ask", "technical": "suggest",
                           "content": "delegate", "quality": "ask"},
        "messages": [{"id": "msg-user-0", "role": "user",
                      "content": "I want to build a boat marketplace", "timestamp": ""}],
        "decisions": [],
        "pending_decision": None,
        "approved_docs": [],
        "revision_target": None,
        "revision_feedback": None,
    }
    state.update(overrides)
    return state


CONFIRMED_BRIEF = {
    "problem_statement": "Hard to buy/sell boats online",
    "target_users": [{"type": "boat owners", "description": "...", "priority": "primary"}],
    "value_proposition": "One marketplace for everything marine",
    "core_features": ["listings", "search", "messaging"],
    "revenue_model": "commission",
    "domain_category": "saas",
    "scope_in": ["listings"],
    "scope_out": ["payments"],
    "confirmed": True,
}


async def _fake_call_llm(messages, **kwargs):
    return "Mocked LLM response."


WEB_REPORT = """Mocked web-grounded report.

## Recommended Adjustments
1. Launch in Germany only first — most demand is there.
2. Start with brokers instead of private sellers."""


async def _fake_web_search(system, user_content, api_key, **kwargs):
    return WEB_REPORT, ["https://example.com/source"]


QUALITY_RESPONSE_LOW = """## Quality Review

Gaps found in market sizing and API design.

```json
{"total": 62, "breakdown": {"strategy": 13, "product": 18, "design_gtm": 13, "technical": 18}, "grade": "D", "verdict": "FAIL", "top_fixes": ["prd: Add real TAM data", "architecture: Define the listing API endpoints", "prd: Add acceptance criteria to user stories"]}
```"""

QUALITY_RESPONSE_HIGH = """## Quality Review

Improved substantially.

```json
{"total": 84, "breakdown": {"strategy": 17, "product": 25, "design_gtm": 16, "technical": 26}, "grade": "B", "verdict": "PASS"}
```"""


class QualityLLM:
    """First review scores low, post-improvement review scores high."""

    def __init__(self):
        self.review_calls = 0

    async def __call__(self, messages, **kwargs):
        if "Quality Reviewer" in messages[0]["content"]:
            self.review_calls += 1
            return QUALITY_RESPONSE_LOW if self.review_calls == 1 else QUALITY_RESPONSE_HIGH
        return "Mocked LLM response."


@pytest.fixture
def mock_llms(monkeypatch):
    quality_llm = QualityLLM()
    monkeypatch.setattr(idea_analyst_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(research_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(research_mod, "call_anthropic_web_search", _fake_web_search)
    monkeypatch.setattr(research_mod.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(specification_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(quality_mod, "call_llm", quality_llm)
    monkeypatch.setattr(packaging_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(collaboration_mod, "call_llm", _fake_call_llm)
    return quality_llm


async def _decide(result, config, **submission):
    updated = resolve_decision(dict(result), submission)
    return await pipeline.ainvoke(updated, config=config)


async def _approve(result, config):
    return await _decide(result, config, action="choose", chosen_option="confirm")


def _pending_id(result):
    return (result.get("pending_decision") or {}).get("id")


async def test_idea_conversation_pauses_for_user(mock_llms):
    """Without a confirmed brief, the analyst answers once and the graph stops."""
    config = {"configurable": {"thread_id": "t-idea"}}
    result = await pipeline.ainvoke(_base_state(), config=config)

    assert result["pipeline_status"] == "waiting_for_user"
    assert result["messages"][-1]["role"] == "agent"


async def test_each_research_doc_gets_an_approval_gate(mock_llms):
    """Every research document pauses at its own approval card."""
    config = {"configurable": {"thread_id": "t-gates"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    assert result["market_research"]["completed"]
    assert "competitor_analysis" not in result or not result.get("competitor_analysis")
    assert _pending_id(result) == "approve-doc:market_research"

    result = await _approve(result, config)
    assert _pending_id(result) == "approve-doc:competitor_analysis"

    result = await _approve(result, config)
    assert _pending_id(result) == "approve-doc:tech_feasibility"

    result = await _approve(result, config)
    # All three approved → synthesis + phase gate
    assert result["research_review_done"] is True
    assert _pending_id(result) == "approve-research"
    # The summary is a document, not a chat dump
    assert result["research_summary"]
    assert "research_summary.md" in result["messages"][-1]["content"]


async def test_apply_and_continue_skips_the_extra_review_round(mock_llms):
    """'Apply adjustments & continue' revises, auto-approves, and moves on."""
    config = {"configurable": {"thread_id": "t-adjust"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    card = result["pending_decision"]
    assert card["id"] == "approve-doc:market_research"
    assert any(o["id"] == "apply" for o in card["options"])
    assert any(o["id"] == "apply_review" for o in card["options"])
    assert card["agent_recommendation"] == "apply"
    # The adjustments are surfaced in the chat note too
    assert "Recommended adjustments" in result["messages"][-1]["content"]

    # Apply & continue: revised, auto-approved, pipeline moved to the next doc
    result = await _decide(result, config, action="choose", chosen_option="apply")
    assert result["market_research"].get("revised") is True
    assert "market_research" in result["approved_docs"]
    assert _pending_id(result) == "approve-doc:competitor_analysis"


async def test_apply_and_review_consumes_adjustments(mock_llms):
    """'Apply & review again' re-presents the gate WITHOUT a fresh apply loop."""
    from app.agents.common import extract_adjustments

    config = {"configurable": {"thread_id": "t-adjust-review"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"

    result = await _decide(result, config, action="choose", chosen_option="apply_review")
    assert result["market_research"].get("revised") is True
    # Gate returns, but the applied adjustments are consumed — no apply button
    card = result["pending_decision"]
    assert card["id"] == "approve-doc:market_research"
    assert not any(o["id"] == "apply" for o in card["options"])
    assert extract_adjustments(result["market_research"]["report"]) is None
    assert "have been applied" in result["market_research"]["report"]


async def test_change_request_revises_the_document(mock_llms, monkeypatch):
    """Freeform change request on a doc card → discussion agent triggers a
    revision → doc rewritten and the gate re-presented."""
    config = {"configurable": {"thread_id": "t-revise"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"

    async def _action_llm(messages, **kwargs):
        if "TAKE ACTION" in messages[0]["content"]:
            return ('```json\n{"action": "revise", "target": "market_research", '
                    '"feedback": "Focus on the EU market only."}\n```')
        return "Mocked LLM response."

    monkeypatch.setattr(research_mod, "call_llm", _action_llm)

    result = await _decide(
        result, config, action="custom",
        custom_input="Focus on the EU market only, drop the US numbers.",
    )

    assert result["market_research"].get("revised") is True
    assert result["revision_target"] is None
    assert _pending_id(result) == "approve-doc:market_research"


async def test_stale_apply_on_doc_without_adjustments_approves(mock_llms, monkeypatch):
    """Apply clicked while the doc says 'None' → approve as-is, no rewrite."""

    async def _no_adjustments_search(system, user_content, api_key, **kwargs):
        return ("Report.\n\n## Recommended Adjustments\n**None** — holds up.",
                ["https://example.com/source"])

    monkeypatch.setattr(research_mod, "call_anthropic_web_search", _no_adjustments_search)

    config = {"configurable": {"thread_id": "t-stale-apply"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    card = result["pending_decision"]
    assert card["id"] == "approve-doc:market_research"
    # Decorated "None" correctly means: no apply buttons on a fresh card
    assert not any(o["id"] == "apply" for o in card["options"])

    # Even if a stale card lets "apply" through, it approves instead of rewriting
    result = await _decide(result, config, action="choose", chosen_option="apply")
    assert "market_research" in result["approved_docs"]
    assert result["market_research"].get("revised") is not True
    assert _pending_id(result) == "approve-doc:competitor_analysis"


async def test_turkish_rewrite_request_revises_not_approves(mock_llms):
    """'Tekrar yazar mısın bu dökümanı' revises deterministically — the LLM
    intent parser is bypassed, so a weak model can't misread it as approval."""
    config = {"configurable": {"thread_id": "t-rewrite-tr"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"

    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "rw", "role": "user",
                     "content": "Tekrar yazar mısın bu dökümanı?", "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)

    assert result2["market_research"].get("revised") is True
    assert "market_research" not in (result2.get("approved_docs") or [])
    assert _pending_id(result2) == "approve-doc:market_research"


async def test_go_back_reopens_step_without_rewriting(mock_llms):
    """'Devils advocate adımına geri dönelim' reopens the gate, doc untouched."""
    config = {"configurable": {"thread_id": "t-reopen-da"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    for _ in range(3):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-research
    for _ in range(5):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-spec
    result = await _approve(result, config)  # DA report approved
    assert _pending_id(result) == "approve-doc:consistency_report"
    da_before = result["devils_advocate"]

    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "gb", "role": "user",
                     "content": "devils advocate adımına geri dönelim.",
                     "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)

    # Gate reopened, document NOT rewritten, approval revoked
    assert _pending_id(result2) == "approve-doc:devils_advocate"
    assert result2["devils_advocate"] == da_before
    assert "devils_advocate" not in (result2.get("approved_docs") or [])


async def test_rerun_step_request_revises_and_shows_result(mock_llms):
    """'Adımı baştan çalıştıralım ve oradan devam edelim' re-runs the gated
    report and RE-PRESENTS it — it must not be auto-approved past the user."""
    config = {"configurable": {"thread_id": "t-rerun-da"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    for _ in range(3):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-research
    for _ in range(5):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-spec
    assert _pending_id(result) == "approve-doc:devils_advocate"

    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "rr", "role": "user",
                     "content": "Devil adımını baştan çalıştıralım ve oradan devam edelim",
                     "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)

    # Report re-generated, NOT silently approved — the gate comes back
    assert "devils_advocate" not in (result2.get("approved_docs") or [])
    assert _pending_id(result2) == "approve-doc:devils_advocate"


async def test_freeform_approval_intent_approves_instead_of_revising(
    mock_llms, monkeypatch
):
    """'Noted, let's continue' typed on the card approves the doc — no rewrite."""
    config = {"configurable": {"thread_id": "t-approve-intent"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"

    async def _approve_llm(messages, **kwargs):
        if "TAKE ACTION" in messages[0]["content"]:
            return '```json\n{"action": "approve", "target": "market_research"}\n```'
        return "Mocked LLM response."

    monkeypatch.setattr(research_mod, "call_llm", _approve_llm)

    result = await _decide(
        result, config, action="custom",
        custom_input="Önerileri sonrası için kaydedelim, ilerleyelim.",
    )

    assert "market_research" in result["approved_docs"]
    assert result["market_research"].get("revised") is not True  # untouched
    # Pipeline moved on to the next research document
    assert _pending_id(result) == "approve-doc:competitor_analysis"


async def test_full_pipeline_with_quality_improvement_loop(mock_llms):
    """Low score → improve → re-score high → package."""
    config = {"configurable": {"thread_id": "t-full"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    # Approve the three research docs, then the research phase
    for _ in range(3):
        assert _pending_id(result).startswith("approve-doc:")
        result = await _approve(result, config)
    assert _pending_id(result) == "approve-research"
    result = await _approve(result, config)

    # Approve the five spec docs, then the spec phase
    for _ in range(5):
        assert _pending_id(result).startswith("approve-doc:")
        result = await _approve(result, config)
    assert _pending_id(result) == "approve-spec"
    result = await _approve(result, config)

    # Quality: adversarial + consistency reports come first, each gated —
    # the reviewer scores LAST, with those findings in view
    assert _pending_id(result) == "approve-doc:devils_advocate"
    assert result.get("quality_score") is None  # reviewer hasn't run yet
    result = await _approve(result, config)
    assert _pending_id(result) == "approve-doc:consistency_report"
    result = await _approve(result, config)

    # First score is low, card recommends improving and the chat note lists
    # the highest-impact fixes
    assert result["quality_score"] == 62
    assert _pending_id(result) == "approve-quality"
    assert result["pending_decision"]["agent_recommendation"] == "improve"
    assert result["quality_top_fixes"] == [
        "prd: Add real TAM data",
        "architecture: Define the listing API endpoints",
        "prd: Add acceptance criteria to user stories",
    ]
    assert "To raise the score" in result["messages"][-1]["content"]
    assert "Add real TAM data" in result["messages"][-1]["content"]
    # Scores are stamped with the rubric version (code-side, not model-side)
    from app.agents.quality import RUBRIC_VERSION
    assert result["quality_breakdown"]["rubric_version"] == RUBRIC_VERSION
    assert f"rubric version `{RUBRIC_VERSION}`" in result["quality_feedback"]

    # Improvement pass only touches the docs named in the fixes, then the
    # STALE consistency report re-checks the updated specs (own gate) before
    # the reviewer re-scores — step-by-step, no jumping to the final gate
    result = await _decide(result, config, action="choose", chosen_option="improve")
    improve_note = next(
        m["content"] for m in result["messages"]
        if "Improvement pass complete" in m["content"]
    )
    assert "Product Requirements Document" in improve_note
    assert "System Architecture" in improve_note
    assert "UX Specification" not in improve_note  # untargeted docs untouched
    assert _pending_id(result) == "approve-doc:consistency_report"
    assert result.get("quality_score") == 62  # not re-scored yet

    result = await _approve(result, config)  # approve the fresh consistency check
    assert result["quality_score"] == 84
    assert result["quality_score_history"] == [62, 84]
    assert _pending_id(result) == "approve-quality"
    assert result["pending_decision"]["agent_recommendation"] == "confirm"

    # Package
    result = await _approve(result, config)
    assert result["current_phase"] == "completed"
    files = result["project_files"]
    assert "INDEX.md" in files
    assert "00_IDEA/idea_brief.md" in files
    assert "One marketplace for everything marine" in files["00_IDEA/idea_brief.md"]
    assert "01_RESEARCH/market_research.md" in files
    assert result["pending_decision"] is None


async def test_question_at_doc_gate_gets_answered_and_card_returns(mock_llms):
    """Asking a question at a doc gate routes to discussion, card comes back."""
    config = {"configurable": {"thread_id": "t-docq"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"

    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "q", "role": "user",
                     "content": "Is the TAM realistic?", "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)
    assert result2["messages"][-1]["role"] == "agent"
    assert _pending_id(result2) == "approve-doc:market_research"


async def test_chat_request_at_quality_gate_triggers_targeted_improvement(
    mock_llms, monkeypatch
):
    """'Fix the consistency issues' typed in chat → discussion agent emits an
    action → targeted improvement pass runs → re-score."""
    config = {"configurable": {"thread_id": "t-action"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    for _ in range(3):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-research
    for _ in range(5):
        result = await _approve(result, config)
    result = await _approve(result, config)  # approve-spec
    result = await _approve(result, config)  # devils_advocate report
    result = await _approve(result, config)  # consistency report
    assert _pending_id(result) == "approve-quality"

    # Discussion agent responds with an action instead of advice
    async def _action_llm(messages, **kwargs):
        if "TAKE ACTION" in messages[0]["content"]:
            return ('```json\n{"action": "improve", '
                    '"focus": "fix the consistency issues", "targets": ["prd"]}\n```')
        return "Mocked LLM response."

    monkeypatch.setattr(specification_mod, "call_llm", _action_llm)

    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "q", "role": "user",
                     "content": "consistency raporuna göre düzelt", "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)

    improve_note = next(
        m["content"] for m in result2["messages"]
        if "Improvement pass complete" in m["content"]
    )
    assert "Product Requirements Document" in improve_note
    assert "System Architecture" not in improve_note  # only the requested target
    # Step-by-step: stale consistency re-checks first, then the re-score
    assert _pending_id(result2) == "approve-doc:consistency_report"
    result2 = await _approve(result2, config)
    assert result2["quality_score"] == 84  # re-scored after the pass
    assert _pending_id(result2) == "approve-quality"


def test_brief_extraction_tolerates_model_formatting():
    """Brief JSON parses across fence/spacing variants free models produce."""
    from app.agents.idea_analyst import _extract_brief

    brief = {"problem_statement": "x", "core_features": ["a"]}
    payload_spaced = '{"action": "present_brief", "brief": {"problem_statement": "x", "core_features": ["a"]}}'
    payload_tight = '{"action":"present_brief","brief":{"problem_statement":"x","core_features":["a"]}}'

    # Canonical form
    assert _extract_brief(f"Here it is:\n```json\n{payload_spaced}\n```") == brief
    # No space after colons (common in compact model output)
    assert _extract_brief(f"```json\n{payload_tight}\n```") == brief
    # Fence without a language tag / uppercase tag
    assert _extract_brief(f"```\n{payload_spaced}\n```") == brief
    assert _extract_brief(f"```JSON\n{payload_spaced}\n```") == brief
    # No fence at all
    assert _extract_brief(f"Final brief below.\n{payload_tight}") == brief
    # Not a brief
    assert _extract_brief("just chatting about present_brief plans") is None
    assert _extract_brief("no marker here") is None


def test_adjustments_parser_tolerates_model_formatting():
    """Heading variants parse; absence or 'None' means no adjustments."""
    from app.agents.common import extract_adjustments

    # Models write the heading in many ways — all must parse
    assert extract_adjustments("intro\n## Recommended Adjustments\n1. x") == "1. x"
    assert extract_adjustments("intro\n### recommended adjustments\n1. x") == "1. x"
    assert extract_adjustments("intro\n**Recommended Adjustments:**\n1. x") == "1. x"
    # "None" and absence both mean no adjustments (no buttons, no forcing)
    assert extract_adjustments("## Recommended Adjustments\nNone — fine.") is None
    assert extract_adjustments("no section at all") is None
    # Decorated "None" variants (bold/list markers render invisibly in the UI)
    assert extract_adjustments("## Recommended Adjustments\n**None** — holds up.") is None
    assert extract_adjustments("## Recommended Adjustments\n- None — fine.") is None
    assert extract_adjustments("## Recommended Adjustments\n1. None.") is None
    assert extract_adjustments("## Recommended Adjustments\n*None — ok.*") is None
    # Section ends at the next heading
    assert extract_adjustments(
        "## Recommended Adjustments\n1. x\n## Sources\n- y"
    ) == "1. x"
    # Numbered heading (models mirror the numbered doc structure)
    assert extract_adjustments("## 6. Recommended Adjustments\n1. x") == "1. x"
    assert extract_adjustments("**5) Recommended Adjustments**\n1. x") == "1. x"
    # Turkish output (whole doc translated by free models)
    assert extract_adjustments("## Önerilen Ayarlamalar\n1. x") == "1. x"
    assert extract_adjustments("### Tavsiye Edilen Değişiklikler\n1. x") == "1. x"
    assert extract_adjustments("## Önerilen Ayarlamalar\nYok — mevcut yön uygun.") is None


def test_report_gate_offers_single_honest_apply_option():
    """Quality-report cards apply to the SPECS — no misleading 'review again'."""
    from app.agents.common import doc_gate_card

    report_card = doc_gate_card("devils_advocate", has_adjustments=True)
    ids = [o["id"] for o in report_card["options"]]
    assert "apply" in ids and "apply_review" not in ids
    assert "specs" in report_card["question"]

    spec_card = doc_gate_card("prd", has_adjustments=True)
    ids = [o["id"] for o in spec_card["options"]]
    assert "apply" in ids and "apply_review" in ids


def test_context_strips_adjustments_and_blocklists_them():
    """Earlier docs' suggestions don't leak into downstream agents as context,
    and are passed as an explicit do-not-repeat blocklist."""
    from app.agents.common import (
        docs_context,
        prior_adjustments_blocklist,
        strip_adjustments_section,
    )

    doc = "# Report\n\nBody.\n\n## Recommended Adjustments\n1. Focus Turkey.\n\n## Sources\n- y"
    stripped = strip_adjustments_section(doc)
    assert "Focus Turkey" not in stripped
    assert "## Sources" in stripped  # rest of the document survives

    state = {"market_research": {"report": doc, "completed": True}}
    assert "Focus Turkey" not in docs_context(state, ["market_research"])

    block = prior_adjustments_blocklist(state)
    assert "BLOCKLIST" in block and "Focus Turkey" in block
    assert prior_adjustments_blocklist({}) == ""


async def test_no_anthropic_key_falls_back_to_plain_llm(mock_llms, monkeypatch):
    """Without any Anthropic key, research still completes (knowledge-only)."""
    monkeypatch.setattr(research_mod.settings, "anthropic_api_key", "")
    config = {"configurable": {"thread_id": "t-fallback"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    assert result["market_research"]["completed"]
    assert result["market_research"]["web_grounded"] is False
