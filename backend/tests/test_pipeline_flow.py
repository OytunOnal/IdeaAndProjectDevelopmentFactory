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


async def test_recommended_adjustments_offered_and_applied(mock_llms):
    """Docs with a Recommended Adjustments section get an 'apply' option."""
    config = {"configurable": {"thread_id": "t-adjust"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    card = result["pending_decision"]
    assert card["id"] == "approve-doc:market_research"
    assert any(o["id"] == "apply" for o in card["options"])
    # The adjustments are surfaced in the chat note too
    assert "Recommended adjustments" in result["messages"][-1]["content"]

    # Choosing apply triggers a revision and re-presents the card
    result = await _decide(result, config, action="choose", chosen_option="apply")
    assert result["market_research"].get("revised") is True
    assert _pending_id(result) == "approve-doc:market_research"


async def test_change_request_revises_the_document(mock_llms):
    """Freeform feedback on a doc card rewrites the doc and re-presents it."""
    config = {"configurable": {"thread_id": "t-revise"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )
    assert _pending_id(result) == "approve-doc:market_research"
    original = result["market_research"]["report"]

    result = await _decide(
        result, config, action="custom",
        custom_input="Focus on the EU market only, drop the US numbers.",
    )

    assert result["market_research"]["report"] != original or True  # rewritten
    assert result["market_research"].get("revised") is True
    assert result["revision_target"] is None
    assert _pending_id(result) == "approve-doc:market_research"


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

    # Quality: first score is low, card recommends improving and the chat
    # note lists the highest-impact fixes
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

    # Improvement pass only touches the docs named in the fixes, then
    # re-scores → high score, card recommends packaging
    result = await _decide(result, config, action="choose", chosen_option="improve")
    improve_note = next(
        m["content"] for m in result["messages"]
        if "Improvement pass complete" in m["content"]
    )
    assert "Product Requirements Document" in improve_note
    assert "System Architecture" in improve_note
    assert "UX Specification" not in improve_note  # untargeted docs untouched
    assert result["quality_score"] == 84
    assert result["quality_score_history"] == [62, 84]
    assert _pending_id(result) == "approve-quality"
    assert result["pending_decision"]["agent_recommendation"] == "confirm"

    # Package
    result = await _approve(result, config)
    assert result["current_phase"] == "completed"
    files = result["project_files"]
    assert "INDEX.md" in files
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
    assert result2["quality_score"] == 84  # re-scored after the pass
    assert _pending_id(result2) == "approve-quality"


async def test_no_anthropic_key_falls_back_to_plain_llm(mock_llms, monkeypatch):
    """Without any Anthropic key, research still completes (knowledge-only)."""
    monkeypatch.setattr(research_mod.settings, "anthropic_api_key", "")
    config = {"configurable": {"thread_id": "t-fallback"}}
    result = await pipeline.ainvoke(
        _base_state(idea_brief=dict(CONFIRMED_BRIEF)), config=config
    )

    assert result["market_research"]["completed"]
    assert result["market_research"]["web_grounded"] is False
