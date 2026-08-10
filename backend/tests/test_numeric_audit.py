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


def test_normalize_bridges_heading_label_quotes():
    from app.agents.decomposed_da import _normalize_ws
    doc = "## Targets\n- 10 million registered users by month 3 on a $500 total marketing budget"
    quote = "Targets: 10 million registered users by month 3 on a $500 total marketing budget"
    # measured: the model prefixes quotes with a section label; heading/bullet/
    # colon punctuation must not break the verbatim check
    assert _normalize_ws(quote) in _normalize_ws(doc)


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


def test_candidate_pairs_same_unit_disagreeing_values():
    from app.agents.decomposed_da import candidate_pairs
    facts = [
        {"doc": "prd", "quote": "q1", "concept": "per-van monthly price", "value": 8, "unit": "USD/van/month"},
        {"doc": "gtm", "quote": "q2", "concept": "self-serve van price", "value": 15, "unit": "USD/van/month"},
        {"doc": "financial", "quote": "q3", "concept": "monthly churn", "value": 3, "unit": "percent"},
        {"doc": "prd", "quote": "q4", "concept": "per-van monthly price", "value": 8.2, "unit": "USD/van/month"},
    ]
    pairs = candidate_pairs(facts)
    # 8 vs 15 pairs (units match, disagree); 8 vs 8.2 within tolerance; churn has no partner
    assert len(pairs) == 2  # (8,15) and (15,8.2)
    values = {frozenset((a["value"], b["value"])) for a, b in pairs}
    assert frozenset((8, 15)) in values and frozenset((8.2, 15)) in values


def test_candidate_pairs_unit_family_bridges_tag_drift():
    from app.agents.decomposed_da import candidate_pairs
    facts = [
        {"doc": "prd", "quote": "q", "concept": "van monthly price", "value": 8, "unit": "USD/month"},
        {"doc": "gtm", "quote": "q", "concept": "self-serve van price", "value": 15, "unit": "USD/van/month"},
    ]
    # measured failure: the same price tagged USD/month in one doc and
    # USD/van/month in another must still pair
    assert len(candidate_pairs(facts)) == 1


def test_is_derived_guard():
    from app.agents.decomposed_da import is_derived
    a = {"value": 8}   # $8/van
    b = {"value": 120}  # $120/fleet
    # 120 = 8 × 15 where 15 (avg fleet size) is a stated fact → derivation
    assert is_derived(a, b, [8, 120, 15, 25]) is True
    # 8 vs 15 (the real price mismatch): no fact ≈ 1.875 → NOT derived
    assert is_derived({"value": 8}, {"value": 15}, [8, 15, 120, 25]) is False
    # the pair's own values don't count as multipliers
    assert is_derived({"value": 2}, {"value": 30}, [2, 30]) is False


def test_candidate_pairs_ranks_token_overlap_first():
    from app.agents.decomposed_da import candidate_pairs
    facts = [
        {"doc": "a", "quote": "q", "concept": "take rate", "value": 15, "unit": "percent"},
        {"doc": "b", "quote": "q", "concept": "take rate", "value": 25, "unit": "percent"},
        {"doc": "c", "quote": "q", "concept": "monthly churn", "value": 8, "unit": "percent"},
    ]
    pairs = candidate_pairs(facts)
    assert pairs[0][0]["concept"] == "take rate" and pairs[0][1]["concept"] == "take rate"


def test_fact_valid_grounding():
    from app.agents.decomposed_da import _fact_valid
    doc = "Self-serve at **$8/van/month**; 14-day trial."
    assert _fact_valid({"quote": "Self-serve at $8/van/month", "concept": "van price",
                        "value": 8, "unit": "USD/van/month"}, doc) is True
    assert _fact_valid({"quote": "Self-serve at $8/van/month", "concept": "van price",
                        "value": 15, "unit": "USD/van/month"}, doc) is False  # value not in quote
    assert _fact_valid({"quote": "not in doc", "concept": "x", "value": 8, "unit": "USD"}, doc) is False


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
