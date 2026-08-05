"""Tier-0 deterministic tests for the negated-approve guard.

The measured failure this guards against: a local model (qwen3:8b, think-off)
executed the OPPOSITE of "don't approve yet". Critical intents live in code.
"""

import pytest

from app.agents.common import _approve_negated, apply_discussion_action


def _state(user_message: str) -> dict:
    return {
        "current_phase": "specification",
        "prd": "# PRD\n\nSome content.",
        "approved_docs": [],
        "messages": [
            {"role": "agent", "agent_id": "orchestrator", "content": "PRD ready."},
            {"role": "user", "content": user_message},
        ],
    }


BLOCKED = [
    "şimdilik onaylama, yarın bakacağım",
    "onaylamayalım şimdilik",
    "bunu approve etme lütfen",
    "don't approve it yet, I'll take a look tomorrow",
    "do not approve this until I check the numbers",
    "let's not approve for now",
    "hold off on approving this one",
    "no lo apruebes todavía",
    "bitte nicht genehmigen",
]

ALLOWED = [
    "onayla, devam edelim",
    "onaylıyorum",
    "revize etmene gerek yok, devam et",
    "why don't we approve it and move on?",
    "approve it, looks good",
    "lgtm, approved",
]


@pytest.mark.parametrize("message", BLOCKED)
def test_negated_approve_detected(message):
    assert _approve_negated(_state(message)) is True


@pytest.mark.parametrize("message", ALLOWED)
def test_positive_approve_not_blocked(message):
    assert _approve_negated(_state(message)) is False


@pytest.mark.parametrize("message", BLOCKED)
def test_guard_blocks_approve_action(message):
    result = apply_discussion_action(
        _state(message), {"action": "approve", "target": "prd"}
    )
    assert result is None  # blocked — no state change


def test_guard_allows_normal_approve():
    result = apply_discussion_action(
        _state("onayla, devam"), {"action": "approve", "target": "prd"}
    )
    assert result is not None
    assert "prd" in result["approved_docs"]
