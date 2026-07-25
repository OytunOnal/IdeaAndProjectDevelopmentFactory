"""End-to-end pipeline flow tests with mocked LLM calls.

Verifies the LangGraph routing: idea conversation pause, sequential research
fan-out, review decision pause, and approval → specification phase.
No real LLM/API calls are made.
"""

import pytest

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


async def _fake_web_search(system, user_content, api_key, **kwargs):
    return "Mocked web-grounded report.", ["https://example.com/source"]


QUALITY_RESPONSE = """## Quality Review

Solid specs overall; minor gaps in accessibility.

```json
{"total": 84, "breakdown": {"strategy": 17, "product": 25, "design_gtm": 16, "technical": 26}, "grade": "B", "verdict": "PASS"}
```"""


async def _fake_quality_llm(messages, **kwargs):
    if "Quality Reviewer" in messages[0]["content"]:
        return QUALITY_RESPONSE
    return "Mocked LLM response."


@pytest.fixture
def mock_llms(monkeypatch):
    monkeypatch.setattr(idea_analyst_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(research_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(research_mod, "call_anthropic_web_search", _fake_web_search)
    monkeypatch.setattr(research_mod.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(specification_mod, "call_llm", _fake_call_llm)
    monkeypatch.setattr(quality_mod, "call_llm", _fake_quality_llm)
    monkeypatch.setattr(packaging_mod, "call_llm", _fake_call_llm)


async def test_idea_conversation_pauses_for_user(mock_llms):
    """Without a confirmed brief, the analyst answers once and the graph stops."""
    config = {"configurable": {"thread_id": "t-idea"}}
    result = await pipeline.ainvoke(_base_state(), config=config)

    assert result["pipeline_status"] == "waiting_for_user"
    assert result["messages"][-1]["role"] == "agent"
    assert result.get("idea_brief") is None or not result["idea_brief"].get("confirmed")


async def test_research_runs_after_brief_confirmation(mock_llms):
    """Confirmed brief → all three research agents run, then review pauses."""
    config = {"configurable": {"thread_id": "t-research"}}
    state = _base_state(idea_brief=dict(CONFIRMED_BRIEF))

    result = await pipeline.ainvoke(state, config=config)

    for key in ("market_research", "competitor_analysis", "tech_feasibility"):
        assert result[key]["completed"], f"{key} should be completed"
        assert result[key]["web_grounded"] is True
        assert result[key]["sources"] == ["https://example.com/source"]

    assert result["research_review_done"] is True
    assert result["pipeline_status"] == "waiting_for_user"
    assert result["pending_decision"]["id"] == "approve-research"


async def test_research_approval_moves_to_specification(mock_llms):
    """Approving research advances the phase and runs the spec agents."""
    config = {"configurable": {"thread_id": "t-approve"}}
    state = _base_state(idea_brief=dict(CONFIRMED_BRIEF))
    result = await pipeline.ainvoke(state, config=config)
    assert result["pending_decision"]["id"] == "approve-research"

    updated = resolve_decision(dict(result), {"action": "choose", "chosen_option": "confirm"})
    final = await pipeline.ainvoke(updated, config=config)

    assert final["research_approved"] is True
    assert final["current_phase"] == "specification"
    # The spec agents run immediately and end at the spec approval gate
    assert final["pending_decision"]["id"] == "approve-spec"


async def test_research_discussion_answers_questions(mock_llms):
    """A follow-up question after review routes to the discussion agent."""
    config = {"configurable": {"thread_id": "t-discuss"}}
    state = _base_state(idea_brief=dict(CONFIRMED_BRIEF))
    result = await pipeline.ainvoke(state, config=config)

    # User asks a question instead of approving
    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "q", "role": "user",
                     "content": "How big is the TAM exactly?", "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)

    result2 = await pipeline.ainvoke(state2, config=config)

    assert result2["messages"][-1]["role"] == "agent"
    assert result2["pending_decision"]["id"] == "approve-research"
    assert result2["pipeline_status"] == "waiting_for_user"


async def test_full_pipeline_to_completion(mock_llms):
    """approve-research → 5 spec docs → quality trio → packaging → completed."""
    config = {"configurable": {"thread_id": "t-full"}}
    state = _base_state(idea_brief=dict(CONFIRMED_BRIEF))
    result = await pipeline.ainvoke(state, config=config)

    # Approve research → specification phase writes all five documents
    updated = resolve_decision(dict(result), {"action": "choose", "chosen_option": "confirm"})
    result = await pipeline.ainvoke(updated, config=config)

    for key in ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model"):
        assert result[key], f"{key} should be written"
    assert result["pending_decision"]["id"] == "approve-spec"

    # Approve specs → quality phase runs reviewer, devil's advocate, consistency
    updated = resolve_decision(dict(result), {"action": "choose", "chosen_option": "confirm"})
    result = await pipeline.ainvoke(updated, config=config)

    assert result["quality_score"] == 84
    assert result["quality_breakdown"]["verdict"] == "PASS"
    assert result["devils_advocate"]
    assert result["consistency_report"]
    assert result["pending_decision"]["id"] == "approve-quality"

    # Approve quality → packaging produces roadmap + final file set
    updated = resolve_decision(dict(result), {"action": "choose", "chosen_option": "confirm"})
    result = await pipeline.ainvoke(updated, config=config)

    assert result["current_phase"] == "completed"
    assert result["implementation_roadmap"]
    files = result["project_files"]
    assert "INDEX.md" in files
    assert "02_PRODUCT/prd.md" in files
    assert "01_RESEARCH/market_research.md" in files
    assert "https://example.com/source" in files["01_RESEARCH/market_research.md"]
    assert result["pending_decision"] is None

    # Post-completion questions still get answered
    state2 = dict(result)
    messages = list(state2["messages"])
    messages.append({"id": "q2", "role": "user",
                     "content": "What should I build first?", "timestamp": ""})
    state2.update(messages=messages, pipeline_status="running", pending_decision=None)
    result2 = await pipeline.ainvoke(state2, config=config)
    assert result2["messages"][-1]["role"] == "agent"


async def test_no_anthropic_key_falls_back_to_plain_llm(mock_llms, monkeypatch):
    """Without any Anthropic key, research still completes (knowledge-only)."""
    monkeypatch.setattr(research_mod.settings, "anthropic_api_key", "")
    config = {"configurable": {"thread_id": "t-fallback"}}
    state = _base_state(idea_brief=dict(CONFIRMED_BRIEF))

    result = await pipeline.ainvoke(state, config=config)

    assert result["market_research"]["completed"]
    assert result["market_research"]["web_grounded"] is False
