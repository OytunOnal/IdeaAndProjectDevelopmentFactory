"""Deterministic tests for the decomposed-DA micro-passes (no LLM calls)."""

import pytest

from app.agents.decomposed_da import (
    _parse_items,
    _parse_verdict,
    check_claim,
    merge_evidence_votes,
    safe_eval,
    validate_item,
)

# ── safe_eval ──────────────────────────────────────────────────────────────

def test_safe_eval_arithmetic():
    assert safe_eval("12 * 12") == 144
    assert safe_eval("(1 - 0.10) ** 12") == pytest.approx(0.2824, abs=1e-3)
    assert safe_eval("5800 / 9.20") == pytest.approx(630.43, abs=0.01)
    assert safe_eval("-3 + 5") == 2


@pytest.mark.parametrize("evil", [
    "__import__('os').system('x')",
    "open('f')",
    "a + 1",
    "(1).__class__",
    "[1,2][0]",
    "1 if True else 2",
    "lambda: 1",
    "",
])
def test_safe_eval_rejects_non_arithmetic(evil):
    with pytest.raises(ValueError):
        safe_eval(evil)


# ── validate_item ──────────────────────────────────────────────────────────

DOC = """## Unit economics
- **ARPU:** $12/month
- **CAC:** $40
- **LTV:** $35
- **LTV:CAC ≈ 3.6 : 1** — healthy above the 3:1 rule-of-thumb threshold
"""


def test_validate_accepts_grounded_item():
    item = {"quote": "**LTV:CAC ≈ 3.6 : 1**", "expression": "35 / 40", "claimed": 3.6}
    assert validate_item(item, DOC) is None


def test_validate_rejects_missing_quote():
    item = {"quote": "LTV is fantastic", "expression": "35 / 40", "claimed": 3.6}
    assert "quote not found" in validate_item(item, DOC)


def test_validate_rejects_invented_numbers():
    item = {"quote": "**LTV:CAC ≈ 3.6 : 1**", "expression": "999 / 40", "claimed": 3.6}
    assert "absent from document" in validate_item(item, DOC)


def test_validate_allows_percent_decimal_conversion():
    doc = "- churn 10% monthly\n- ~90% retained after 12 months"
    item = {
        "quote": "~90% retained after 12 months",
        "expression": "(1 - 0.10) ** 12",
        "claimed": 0.90,
    }
    # 0.10 is grounded via the percent conversion (doc says 10%); the 1 is
    # formula scaffolding — both must pass the grounding check
    assert validate_item(item, doc) is None


def test_validate_rejects_non_numeric_claim():
    item = {"quote": "**LTV:** $35", "expression": "35 / 40", "claimed": "healthy"}
    assert "not numeric" in validate_item(item, DOC)


def test_validate_accepts_markdownless_quote():
    # models quote content without the doc's ** markers — must still match
    item = {"quote": "LTV:CAC ≈ 3.6 : 1 — healthy above the 3:1 rule-of-thumb threshold",
            "expression": "35 / 40", "claimed": 3.6}
    assert validate_item(item, DOC) is None


def test_validate_rejects_self_computed_claim():
    # measured 8B failure mode: the model "helpfully" writes its own computed
    # value (0.875) as claimed, silently repairing the seeded error
    item = {"quote": "**LTV:CAC ≈ 3.6 : 1**", "expression": "35 / 40", "claimed": 0.875}
    assert "not stated in the quote" in validate_item(item, DOC)


# ── check_claim ────────────────────────────────────────────────────────────

def test_check_claim_passes_rounded_truth():
    # 1/0.03 = 33.3 vs claimed 33 — within tolerance, no finding
    assert check_claim({"quote": "q", "expression": "1 / 0.03", "claimed": 33}) is None


def test_check_claim_flags_seeded_ltv_error():
    # dev-set defect A3: LTV $35, CAC $40, claimed ratio 3.6
    f = check_claim({"quote": "q", "expression": "35 / 40", "claimed": 3.6})
    assert f is not None and f["computed"] == pytest.approx(0.875)


def test_check_claim_flags_seeded_retention_error():
    # dev-set defect B3: 10% churn but ~90% retained after 12 months
    f = check_claim({"quote": "q", "expression": "(1 - 0.10) ** 12", "claimed": 0.90})
    assert f is not None and f["computed"] == pytest.approx(0.2824, abs=1e-3)


def test_check_claim_skips_unevaluable():
    assert check_claim({"quote": "q", "expression": "x / y", "claimed": 1}) is None


# ── _parse_items ───────────────────────────────────────────────────────────

def test_parse_items_fenced():
    reply = 'noise\n```json\n[{"quote": "a", "expression": "1+1", "claimed": 2}]\n```\nmore'
    assert _parse_items(reply) == [{"quote": "a", "expression": "1+1", "claimed": 2}]


def test_parse_items_bare_array():
    assert _parse_items('[{"quote": "a"}]') == [{"quote": "a"}]


def test_parse_items_garbage():
    assert _parse_items("no json here") == []
    assert _parse_items('{"not": "array"}') == []


# ── evidence pass: verdict parsing + vote merge ───────────────────────────

def test_parse_verdict_fenced_and_bare():
    assert _parse_verdict('```json\n{"supported": false, "source": "none"}\n```') == {
        "supported": False, "source": "none"}
    assert _parse_verdict('{"supported": true, "source": "prd"}')["supported"] is True


def test_parse_verdict_rejects_garbage():
    assert _parse_verdict("not json") is None
    assert _parse_verdict('{"supported": "yes"}') is None  # non-bool


def test_parse_verdict_key():
    from app.agents.decomposed_da import _parse_verdict_key
    assert _parse_verdict_key('```json\n{"completed_claim": true}\n```', "completed_claim") is True
    assert _parse_verdict_key('{"completed_claim": false}', "completed_claim") is False
    assert _parse_verdict_key('{"completed_claim": "yes"}', "completed_claim") is None
    assert _parse_verdict_key("garbage", "completed_claim") is None


def test_merge_votes_majority_rule():
    no = {"supported": False, "source": "none"}
    yes = {"supported": True, "source": "prd"}
    assert merge_evidence_votes([no, no, no]) is True
    assert merge_evidence_votes([no, no, yes]) is True  # one noisy vote can't veto
    assert merge_evidence_votes([no, yes, yes]) is False
    assert merge_evidence_votes([no, yes]) is False  # tie withholds
    assert merge_evidence_votes([no, None, None]) is True  # majority of valid
    assert merge_evidence_votes([None, None]) is False  # fail-safe: no finding
    assert merge_evidence_votes([]) is False
