"""Integration tests for the decomposed-DA production path (no LLM calls)."""

import pytest

from app.agents import quality
from app.agents.decomposed_da import compose_production_report
from app.config import settings

STATE = {
    "project_name": "t", "idea_brief": {"confirmed": True},
    "prd": "p", "architecture": "a", "ux_design": "u",
    "gtm_strategy": "g", "financial_model": "f",
    "market_research": "m", "competitor_analysis": "c", "tech_feasibility": "tf",
    "messages": [],
}

FINDING = {"kind": "missing-critical", "topic": "privacy-compliance",
           "detail": "No spec document substantively addresses it"}


@pytest.fixture
def decomposed_on(monkeypatch):
    monkeypatch.setattr(settings, "da_decomposed", True)


async def _noop_progress(*a, **k):
    return None


def test_flag_off_uses_monolithic_path(monkeypatch):
    called = {}

    async def fake_report_agent(state, agent_id, *a, **k):
        called["monolithic"] = True
        return {**state, "devils_advocate": "MONO"}

    monkeypatch.setattr(settings, "da_decomposed", False)
    monkeypatch.setattr(quality, "_run_report_agent", fake_report_agent)
    import asyncio
    result = asyncio.run(quality.devils_advocate_node(dict(STATE)))
    assert called.get("monolithic") and result["devils_advocate"] == "MONO"


def test_flag_on_uses_decomposed_path(monkeypatch, decomposed_on):
    async def fake_run(docs, brief=None, audit_keys=None, stats=None):
        # spec docs audited, research present as sources
        assert set(audit_keys) == {"prd", "architecture", "ux_design",
                                   "gtm_strategy", "financial_model"}
        assert "market_research" in docs
        return [FINDING], "unused"

    import app.agents.decomposed_da as dda
    monkeypatch.setattr(dda, "run_decomposed_da", fake_run)
    monkeypatch.setattr(quality, "emit_progress", _noop_progress)
    import asyncio
    result = asyncio.run(quality.devils_advocate_node(dict(STATE)))
    report = result["devils_advocate"]
    assert "RISK: HIGH" in report  # missing-critical → HIGH
    assert "## Recommended Adjustments" in report
    assert "privacy-compliance" in report


def test_decomposed_failure_falls_back(monkeypatch, decomposed_on):
    async def boom(*a, **k):
        raise RuntimeError("ollama down")

    async def fake_report_agent(state, agent_id, *a, **k):
        return {**state, "devils_advocate": "MONO-FALLBACK"}

    import app.agents.decomposed_da as dda
    monkeypatch.setattr(dda, "run_decomposed_da", boom)
    monkeypatch.setattr(quality, "_run_report_agent", fake_report_agent)
    monkeypatch.setattr(quality, "emit_progress", _noop_progress)
    import asyncio
    result = asyncio.run(quality.devils_advocate_node(dict(STATE)))
    assert result["devils_advocate"] == "MONO-FALLBACK"


def test_production_report_shapes():
    empty = compose_production_report([])
    assert "RISK: LOW" in empty
    assert "None — the current direction holds up." in empty
    risky = compose_production_report([FINDING])
    assert "RISK: HIGH" in risky and "1. Add substantive privacy-compliance" in risky
