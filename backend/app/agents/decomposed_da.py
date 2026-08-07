"""Decomposed Devil's Advocate — Phase 3 of the local migration.

The monolithic "criticize everything" DA call is the measured weak spot of
local models (broad, open-ended). This module decomposes it into micro-passes
ordered by verifiability (LOCAL_MIGRATION_PLAN.md, Phase 3). The design rule
for every pass: the LLM only does NARROW extraction or answers narrow
questions; wherever a judgment can be computed, code computes it.

Pass 1 — numeric audit: an extraction call turns each document's arithmetic
claims into checkable expressions; Python evaluates them exactly and flags
mismatches. The LLM never judges whether the math is right.
"""

import ast
import json
import logging
import operator
import re

from app.agents.llm import call_llm

logger = logging.getLogger(__name__)

# ── safe arithmetic evaluator ──────────────────────────────────────────────

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str) -> float:
    """Evaluate a pure-arithmetic expression (numbers, + - * / ** parens).

    Raises ValueError on anything else — names, calls, subscripts — so a
    malformed or malicious extraction can never execute code.
    """

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"disallowed element in expression: {ast.dump(node)}")

    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"not an expression: {expr!r}") from e
    return _eval(tree)


# ── extraction validation (code, deterministic) ────────────────────────────

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

# Formula scaffolding the model may introduce without the document spelling it
# out: the 1 in (1 - churn) / 1 ÷ churn, and 100 for percent conversion.
_SCAFFOLD_NUMBERS = {1.0, 100.0}


def _numbers_in(text: str) -> set[float]:
    """Numeric literals in a text as values (commas stripped, % and $ ignored)."""
    return {round(float(n), 6) for n in _NUM_RE.findall(text.replace(",", ""))}


def _grounded(value: float, doc_numbers: set[float], scaffolding: bool = True) -> bool:
    """A number is grounded if the doc states it directly, as a percentage
    (8% ↔ 0.08), or (for expression inputs) it is formula scaffolding (1, 100)."""
    candidates = {round(value, 6), round(value * 100, 6), round(value / 100, 6)}
    return (scaffolding and value in _SCAFFOLD_NUMBERS) or bool(candidates & doc_numbers)


def _normalize_ws(text: str) -> str:
    """Collapse whitespace AND markdown emphasis — models quote content, not
    formatting, so `**bold**`/`` `code` `` must not break substring matching."""
    return re.sub(r"\s+", " ", re.sub(r"[*`_]", "", text)).strip()


def validate_item(item: dict, doc_text: str) -> str | None:
    """Return a rejection reason, or None if the extracted claim is trustworthy.

    Guards against hallucinated extractions AND helpful "corrections": the
    quote must exist in the document; every number the expression uses must
    appear in the document (no invented inputs); and the claimed result must
    literally appear in the quote — measured failure mode: the extractor
    computes the right answer itself and reports it as "claimed", silently
    repairing the very error the audit exists to catch.
    """
    quote = item.get("quote", "")
    expr = item.get("expression", "")
    if not quote or not expr or "claimed" not in item:
        return "missing field"
    if _normalize_ws(quote) not in _normalize_ws(doc_text):
        return "quote not found in document"
    try:
        claimed = float(item["claimed"])
    except (TypeError, ValueError):
        return "claimed result not numeric"
    if not _grounded(claimed, _numbers_in(quote), scaffolding=False):
        return "claimed result not stated in the quote"
    doc_numbers = _numbers_in(doc_text)
    missing = [n for n in _numbers_in(expr) if not _grounded(n, doc_numbers)]
    if missing:
        return f"expression uses numbers absent from document: {missing}"
    return None


def check_claim(item: dict, rel_tolerance: float = 0.2) -> dict | None:
    """Evaluate one validated claim; return a finding dict if it fails.

    Tolerance is generous (20% relative) because documents round aggressively
    ("≈33 months", "~3.6:1"). Real seeded errors are order-of-magnitude wrong,
    so a loose tolerance keeps precision high without costing recall.
    """
    try:
        computed = safe_eval(item["expression"])
    except ValueError as e:
        logger.debug(f"numeric_audit: unevaluable expression skipped: {e}")
        return None
    claimed = float(item["claimed"])
    denom = max(abs(claimed), abs(computed), 1e-9)
    if abs(computed - claimed) / denom <= rel_tolerance:
        return None
    return {
        "kind": "arithmetic",
        "quote": item["quote"],
        "expression": item["expression"],
        "computed": round(computed, 4),
        "claimed": claimed,
    }


# ── extraction call (narrow LLM) ───────────────────────────────────────────

_EXTRACT_PROMPT = """You are a numeric-claims extractor. You do NOT judge whether math is correct — you only convert a document's arithmetic claims into checkable expressions. A separate program does the checking.

From the document below, extract every claim where the document states BOTH the inputs AND a computed result. Typical patterns:
- explicit formulas: "LTV: $168 (24 × $7)"
- ratios: "LTV:CAC ≈ 3.1:1" where LTV and CAC both appear in the document
- churn/lifetime/retention: lifetime = 1/churn; retained after N months = (1-churn)^N
- break-even: users = fixed costs ÷ per-user contribution
- revenue: users × price, GMV × take rate

Rules:
- "quote": copy the sentence(s) stating the claim VERBATIM from the document.
- "expression": plain arithmetic using ONLY numbers that appear in the document (convert percentages to decimals: 8% → 0.08).
- "claimed": the number the DOCUMENT states as the result, copied from your quote. NEVER write your own calculation here — even if you believe the document's number is wrong, report the document's number; the checker decides. An item whose "claimed" does not appear in the quote is discarded.
- Match units: if the document says "~69%" and your expression produces a fraction, write 0.69.
- Skip claims where inputs are not stated anywhere in the document.
- Skip pure targets/assumptions with no computation attached ("CAC target $40").

Example — document says "LTV: $23" and "CAC: $31" and "LTV:CAC ≈ 3.1 : 1":
```json
[{"quote": "LTV:CAC ≈ 3.1 : 1", "expression": "23 / 31", "claimed": 3.1}]
```
(claimed is 3.1 — the document's stated ratio — NOT 0.74, your computation.)

Example — document says "ARPU: $9/month" in one line and "Month-12 target: 400 paying studios → $3,600 MRR" in another. Revenue chains are checkable ACROSS lines (MRR = paying users × ARPU) — the inputs do not need to sit in the quoted sentence, only somewhere in the document:
```json
[{"quote": "Month-12 target: 400 paying studios → $3,600 MRR", "expression": "400 * 9", "claimed": 3600}]
```

Example — document says "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months". This ONE sentence yields TWO checkable claims (lifetime = 1/churn; retained = (1-churn)^12):
```json
[{"quote": "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months", "expression": "1 / 0.05", "claimed": 20},
 {"quote": "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months", "expression": "(1 - 0.05) ** 12", "claimed": 0.54}]
```
Churn/lifetime/retention chains are a REQUIRED extraction whenever a document states them — do not skip them.

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"quote": "...", "expression": "7 * 24", "claimed": 168}]
```
If the document contains no checkable claims, respond with an empty array."""


def _parse_items(reply: str) -> list[dict]:
    """Pull the JSON array out of a reply; tolerate missing fences."""
    text = reply
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        text = m.group(1) if m else text
    else:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        text = m.group(0) if m else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


async def numeric_audit(
    docs: dict[str, str], samples: int = 2, rel_tolerance: float = 0.2
) -> list[dict]:
    """Run the numeric micro-pass over a document bundle.

    Multiple extraction samples raise recall (a claim missed once may be
    caught the second time); code-side validation keeps precision (a
    hallucinated extraction can't survive the quote/number checks). Findings
    are deduplicated by (doc, claimed, rounded computed).
    """
    findings: list[dict] = []
    seen: set[tuple] = set()
    for doc_key, doc_text in docs.items():
        if not doc_text or not doc_text.strip():
            continue
        for _ in range(samples):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": _EXTRACT_PROMPT},
                        {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                    ],
                    model_tier=2,
                    temperature=0.3,
                    max_tokens=2048,
                    role="audit",
                    think=False,
                )
            except Exception as e:
                logger.warning(f"numeric_audit extraction failed for {doc_key}: {e}")
                continue
            for item in _parse_items(reply):
                reason = validate_item(item, doc_text)
                if reason:
                    logger.debug(f"numeric_audit: rejected extraction ({reason}): {item}")
                    continue
                finding = check_claim(item, rel_tolerance)
                if finding is None:
                    continue
                key = (doc_key, finding["claimed"], round(finding["computed"], 2))
                if key in seen:
                    continue
                seen.add(key)
                findings.append({"doc": doc_key, **finding})
    return findings


# ── pass 2: evidence-source matching ───────────────────────────────────────
#
# Targets fabricated first-party evidence ("our 200-freelancer beta converted
# at 34%") — the most dangerous measured local-model failure class, and one
# the dev-set DA prompt upgrade showed even frontier needs explicit duties
# for. Narrow extraction lists the claims; a narrow per-claim verification
# question checks them against the project's other documents. External
# benchmarks ("industry range 2-10%") are out of scope by design — they are
# not verifiable inside the bundle and extracting them would only buy FPs.

_EVIDENCE_EXTRACT_PROMPT = """You are an evidence-claims extractor. You do NOT judge claims — you only list them. A separate check verifies each one.

From the document below, extract every FIRST-PARTY empirical claim: a statement that this project's own pilot, beta, test, launch, or measurement has ALREADY HAPPENED and produced results. Signals: "our pilot/beta/test", past-tense results ("converted at", "cut costs by", "achieved", "sustained"), specific counts of the project's own users/customers/partners presented as accomplished fact.

Do NOT extract:
- industry benchmarks or third-party statistics ("industry range 2-10%", "the market spends $X")
- targets, plans, and projections ("we will reach", "month-12 target", "expected to")
- product descriptions and feature statements

Rules:
- "quote": copy the claiming sentence VERBATIM from the document.
- "asserts": one short sentence stating what evidence the claim presupposes exists.

Worked examples (fictional studio-booking product) — extracted vs NOT extracted:
- "Our closed beta of 90 studios converted at 18%" → EXTRACT (past result asserted as fact)
- "Month 1-2: onboard 40 studios from local networks, weekly feedback loop" → do NOT extract (a launch-phase PLAN, nothing has happened yet)
- "Month-12 target: 500 paying studios → $4,500 MRR" → do NOT extract (a target)
- "LTV:CAC ≈ 3.1 : 1 — healthy" → do NOT extract (a computation, not an empirical event)
- "costs cross MRR at roughly month 13 at current assumptions" → do NOT extract (a projection)

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"quote": "...", "asserts": "a 90-studio closed beta was run and converted at 18%"}]
```
If the document contains no first-party empirical claims, respond with an empty array."""

_EVIDENCE_CLASSIFY_PROMPT = """Answer one narrow question about one sentence from a project document.

Sentence: "{quote}"

Does this sentence assert that an event ALREADY HAPPENED and produced measured results (a completed pilot/beta/test/launch with numbers)? Plans, launch-phase descriptions, targets, projections, and computed metrics are NOT completed events.

Respond with ONLY a fenced JSON object:
```json
{{"completed_claim": true/false}}
```"""

_EVIDENCE_VERIFY_PROMPT = """You verify one claim against a project's source documents. Answer ONLY from the sources given — no outside knowledge, no charity.

The claim (from {claim_doc}) presupposes: {asserts}
Claim text: "{quote}"

Question: do the sources explicitly state that this event/result has actually happened (not merely planned, proposed, or targeted)? A plan to run a pilot does NOT support a claim that a pilot produced results.

Worked example (fictional): claim says "our 40-studio beta converted at 18%"; the sources only say "Month 1-2: onboard 40 studios from local networks". That is a PLAN — nothing states the beta ran or produced 18%. Correct answer: {{"supported": false, "source": "none"}}. Only an explicit statement that the event occurred WITH results counts as support.

Respond with ONLY a fenced JSON object:
```json
{{"supported": true/false, "source": "<doc key that states it, or \\"none\\">"}}
```"""


def _parse_json_object(reply: str) -> dict | None:
    text = reply
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        text = m.group(0) if m else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_verdict(reply: str) -> dict | None:
    """Verdict object with a boolean 'supported' field, or None."""
    data = _parse_json_object(reply)
    return data if data is not None and isinstance(data.get("supported"), bool) else None


def _parse_verdict_key(reply: str, key: str) -> bool | None:
    """A single boolean field from a JSON verdict, or None if unparseable."""
    data = _parse_json_object(reply)
    value = data.get(key) if data else None
    return value if isinstance(value, bool) else None


def merge_evidence_votes(verdicts: list[dict | None]) -> bool:
    """True → flag as unsupported. Majority of valid votes, ties withhold.

    Unanimity was tried first and proved fragile: a single noisy "supported"
    vote vetoed a real finding (measured — the A2 fabricated-beta claim was
    extracted, gated in, then lost at verify). Majority absorbs single-vote
    noise in both directions — the Phase 1 self-consistency rule applied
    here. No valid votes → no finding (an empty verdict must not manufacture
    one)."""
    valid = [v for v in verdicts if v is not None]
    unsupported = sum(1 for v in valid if not v["supported"])
    return unsupported * 2 > len(valid)


async def evidence_audit(
    docs: dict[str, str],
    audit_keys: tuple[str, ...] | None = None,
    samples: int = 3,
    votes: int = 3,
    stats: dict | None = None,
) -> list[dict]:
    """Run the evidence micro-pass: extract first-party empirical claims from
    the audited docs, verify each against ALL other docs in the bundle.

    Pass a dict as `stats` to receive per-stage counts (extracted → gated →
    flagged) — without it, a zero-finding run is indistinguishable from a
    run whose extraction silently returned nothing.
    """
    audit_keys = audit_keys or tuple(docs)
    claims: list[dict] = []
    seen_quotes: set[str] = set()
    for doc_key in audit_keys:
        doc_text = docs.get(doc_key) or ""
        if not doc_text.strip():
            continue
        for _ in range(samples):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": _EVIDENCE_EXTRACT_PROMPT},
                        {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                    ],
                    model_tier=2,
                    temperature=0.3,
                    max_tokens=1536,
                    role="audit",
                    think=False,
                )
            except Exception as e:
                logger.warning(f"evidence_audit extraction failed for {doc_key}: {e}")
                continue
            for item in _parse_items(reply):
                quote = item.get("quote", "")
                if not quote or not item.get("asserts"):
                    continue
                if _normalize_ws(quote) not in _normalize_ws(doc_text):
                    logger.debug(f"evidence_audit: quote not in doc, rejected: {quote!r}")
                    continue
                key = _normalize_ws(quote).lower()
                # containment dedupe: a shorter/longer variant of an already-
                # extracted quote is the same claim
                if any(key in s or s in key for s in seen_quotes):
                    continue
                seen_quotes.add(key)
                claims.append({"doc": doc_key, "quote": quote, "asserts": item["asserts"]})

    # classification gate: only claims that narrowly classify as
    # completed-result assertions proceed (the broad extractor over-extracts
    # plans/targets — the distinction is delegated to a narrow question,
    # mirroring the Phase 1 instruction-vs-question gate)
    gated: list[dict] = []
    for claim in claims:
        votes_c: list[bool] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[{
                        "role": "user",
                        "content": _EVIDENCE_CLASSIFY_PROMPT.format(quote=claim["quote"]),
                    }],
                    model_tier=2,
                    temperature=0.3,
                    max_tokens=256,
                    role="audit",
                    think=False,
                )
                verdict = _parse_verdict_key(reply, "completed_claim")
                if verdict is not None:
                    votes_c.append(verdict)
            except Exception as e:
                logger.warning(f"evidence_audit classify failed: {e}")
        if votes_c and sum(votes_c) * 2 > len(votes_c):  # majority, ties drop
            gated.append(claim)
        else:
            logger.debug(f"evidence_audit: gated out (not a completed claim): {claim['quote']!r}")

    findings: list[dict] = []
    for claim in gated:
        sources = "\n\n".join(
            f"=== {key} ===\n{text[:4000]}"
            for key, text in docs.items()
            if key != claim["doc"] and text and text.strip()
        )
        prompt = _EVIDENCE_VERIFY_PROMPT.format(
            claim_doc=claim["doc"], asserts=claim["asserts"], quote=claim["quote"]
        )
        verdicts: list[dict | None] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Sources:\n\n{sources}"},
                    ],
                    model_tier=2,
                    temperature=0.3,
                    max_tokens=512,
                    role="audit",
                    think=False,
                )
                verdicts.append(_parse_verdict(reply))
            except Exception as e:
                logger.warning(f"evidence_audit verify failed: {e}")
                verdicts.append(None)
        if merge_evidence_votes(verdicts):
            findings.append({
                "kind": "unsupported-evidence",
                "doc": claim["doc"],
                "quote": claim["quote"],
                "asserts": claim["asserts"],
            })
    if stats is not None:
        stats.update({
            "claims_extracted": len(claims),
            "claims_gated_in": len(gated),
            "findings": len(findings),
            "extracted_quotes": [c["quote"][:90] for c in claims],
        })
    return findings


# ── pass 3: checklist absence scan ─────────────────────────────────────────
#
# Targets missing-critical defects (a load-bearing section silently absent).
# Absence is exactly what open-ended review is worst at — you cannot quote
# what isn't there — so the scan inverts it into narrow presence questions
# over a fixed checklist (the micro-pass form of the absence-scan duty that
# took the frontier DA prompt from 77% to 100% on the dev set). Two stages,
# both 3-vote majority: an applicability gate (is this topic critical for
# THIS product?) keeps the checklist from firing on products it doesn't
# apply to; a presence scan over the SPEC docs only — research inputs serve
# as applicability context, because "research flags the concern, no spec
# document addresses it" is precisely the defect.
#
# The checklist is deliberately short. Every item added is an FP surface on
# products where the topic is only marginally relevant; grow it item by
# item, each with measurement.

ABSENCE_CHECKLIST = (
    {
        "key": "privacy-compliance",
        "desc": "handling of personal/user data: privacy commitments, data protection, regulatory compliance (e.g. GDPR/KVKK), data retention or deletion",
    },
    {
        "key": "legal-consent-safety",
        "desc": "consent, liability, safety, or legal obligations created by the product's operation (e.g. tracking people, serving minors, brokering dangerous goods, handling money)",
    },
)

_ABSENCE_APPLICABLE_PROMPT = """Answer one narrow question about a software product.

Product context:
{context}

Topic: {desc}

Is this topic a CRITICAL concern that this product's specification must address — one whose absence a reviewer should flag? Answer strictly for this product, not in general.

Respond with ONLY a fenced JSON object:
```json
{{"critical": true/false}}
```"""

_ABSENCE_PRESENT_PROMPT = """Answer one narrow question about a set of specification documents.

Topic: {desc}

Do the documents below SUBSTANTIVELY address this topic — a dedicated section, or explicit commitments/mechanisms? An incidental word match does not count.

Rules:
- If addressed: "quote" must be a VERBATIM sentence from the documents proving it.
- If not addressed: "quote" is "".

Respond with ONLY a fenced JSON object:
```json
{{"addressed": true/false, "quote": "..."}}
```"""


async def absence_audit(
    docs: dict[str, str],
    brief: dict | None = None,
    audit_keys: tuple[str, ...] | None = None,
    votes: int = 3,
    stats: dict | None = None,
) -> list[dict]:
    """Run the absence micro-pass: for each checklist topic, gate on
    applicability (brief + full bundle as context), then scan the audited
    docs for substantive presence. Flag topics that are critical but absent."""
    audit_keys = audit_keys or tuple(docs)
    spec_text = "\n\n".join(
        f"=== {key} ===\n{docs[key]}" for key in audit_keys if docs.get(key, "").strip()
    )
    context = json.dumps(brief, ensure_ascii=False) if brief else ""
    extra = "\n\n".join(
        f"=== {key} (research input) ===\n{text[:2500]}"
        for key, text in docs.items()
        if key not in audit_keys and text and text.strip()
    )
    if extra:
        context = f"{context}\n\n{extra}" if context else extra

    findings: list[dict] = []
    applicable_count = 0
    for item in ABSENCE_CHECKLIST:
        votes_a: list[bool] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[{
                        "role": "user",
                        "content": _ABSENCE_APPLICABLE_PROMPT.format(context=context, desc=item["desc"]),
                    }],
                    model_tier=2, temperature=0.3, max_tokens=256,
                    role="audit", think=False,
                )
                v = _parse_verdict_key(reply, "critical")
                if v is not None:
                    votes_a.append(v)
            except Exception as e:
                logger.warning(f"absence_audit applicability failed: {e}")
        if not (votes_a and sum(votes_a) * 2 > len(votes_a)):  # majority critical
            continue
        applicable_count += 1

        votes_p: list[bool] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": _ABSENCE_PRESENT_PROMPT.format(desc=item["desc"])},
                        {"role": "user", "content": f"Documents:\n\n{spec_text}"},
                    ],
                    model_tier=2, temperature=0.3, max_tokens=512,
                    role="audit", think=False,
                )
                data = _parse_json_object(reply)
                addressed = data.get("addressed") if data else None
                if not isinstance(addressed, bool):
                    continue
                if addressed:
                    quote = data.get("quote", "")
                    # an "addressed" vote must prove itself with a real quote
                    if not quote or _normalize_ws(quote) not in _normalize_ws(spec_text):
                        logger.debug(f"absence_audit: addressed-vote without valid quote dropped ({item['key']})")
                        continue
                votes_p.append(addressed)
            except Exception as e:
                logger.warning(f"absence_audit presence failed: {e}")
        absent = sum(1 for v in votes_p if not v)
        if votes_p and absent * 2 > len(votes_p):  # majority says absent
            findings.append({
                "kind": "missing-critical",
                "topic": item["key"],
                "detail": f"No spec document substantively addresses: {item['desc']}",
            })
    if stats is not None:
        stats.update({
            "checklist_items": len(ABSENCE_CHECKLIST),
            "applicable_items": applicable_count,
            "findings": len(findings),
        })
    return findings


# ── pass 4: cross-document consistency ─────────────────────────────────────
#
# Targets cross-doc-inconsistency (and same-doc value drift): the same
# quantity stated with different values in different places ($8/van in the
# PRD, $15/van in the GTM). Narrow extraction turns each doc's key
# quantitative facts into (concept, value, unit) rows; CODE pairs same-unit
# rows whose values disagree; a narrow same-quantity question (3-vote
# majority) decides whether a disagreeing pair really talks about the same
# thing. The LLM never decides "is this inconsistent" — code does, from
# values it validated.

_FACTS_EXTRACT_PROMPT = """You are a quantitative-facts extractor. You do NOT judge consistency — you only list facts. A separate program compares them.

From the document below, extract the KEY quantitative facts a reviewer would cross-check: prices, fees/take rates, churn/conversion/retention rates, unit costs, headline targets (users, GMV, MRR), team size, timeline length.

Rules:
- "quote": copy the stating sentence VERBATIM from the document.
- "concept": a short generic label for what the value measures (e.g. "pro plan monthly price", "take rate", "monthly churn", "month-12 paying users target").
- "value": the number, and "unit": a CANONICAL unit string. Use exactly these forms where they apply: "USD/month", "USD/<thing>/month" (e.g. "USD/seat/month"), "USD", "percent", "users", "months", "engineers". Percentages: value 8, unit "percent" (not 0.08).
- One fact per row; skip derived commentary (ratios, LTV math) — pass those over.
- At most 8 facts; prefer the ones most likely to be restated in other documents.

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"quote": "Studio plan: $9/month — unlimited bookings", "concept": "studio plan monthly price", "value": 9, "unit": "USD/month"}]
```"""

_SAME_QUANTITY_PROMPT = """Answer one narrow question about two statements from the same project's documents.

Statement A (from {doc_a}): "{quote_a}"
Statement B (from {doc_b}): "{quote_b}"

Do A and B refer to the SAME quantity — the same price, rate, metric, or target of the same thing? IGNORE whether the stated numbers match: you are identifying what is being measured, not checking agreement. (If the same quantity is stated with different numbers, that is exactly what a later check needs to know.) A future-date growth target and a computed break-even threshold are DIFFERENT quantities even when both count the same unit.

Both sides (fictional studio-booking product):
- "$6 per seat per month" (PRD pricing) vs "Self-serve at $9/seat/month" (GTM) → SAME quantity (both are the product's per-seat subscription price), even though the numbers differ.
- "Only paid plan: Studio at $9/month" vs "ARPU: $13/month" → SAME quantity here (with a single paid plan and no discounts, paid-user ARPU and the plan price are the same number by definition).
- "LTV: $96" vs "CAC: $31" → NOT the same quantity (two different metrics that merely share a unit).
- "monthly churn 4%" vs "trial-to-paid conversion 12%" → NOT the same quantity.
- "$6 per seat per month" vs "average studio revenue $54/month" → NOT the same quantity (different denominators: per-seat vs per-studio; one is derived from the other).
- "Month-12 target: 400 studios" vs "break-even at ~150 studios" → NOT the same quantity (a growth target vs a break-even threshold).

Respond with ONLY a fenced JSON object:
```json
{{"same_quantity": true/false}}
```"""


def _fact_valid(item: dict, doc_text: str) -> bool:
    quote, concept, unit = item.get("quote", ""), item.get("concept"), item.get("unit")
    if not quote or not concept or not unit:
        return False
    if _normalize_ws(quote) not in _normalize_ws(doc_text):
        return False
    try:
        value = float(item["value"])
    except (TypeError, ValueError):
        return False
    return _grounded(value, _numbers_in(quote), scaffolding=False)


def _unit_family(unit: str) -> tuple[str, str]:
    """Coarse unit family for pairing: (base, period). Extraction unit tags
    drift between samples ("USD/van/month" vs "USD/month" for the same
    price), so exact-string matching silently drops real pairs — pair by
    family and let the narrow same-quantity question handle the per-what
    distinction."""
    tokens = [t.strip() for t in unit.lower().split("/") if t.strip()]
    if not tokens:
        return ("", "")
    return (tokens[0], tokens[-1] if len(tokens) > 1 else "")


# PARKED CLASS — context-established identities (dev defect A4: ARPU vs the
# single paid plan's price). Exhaustively measured, 6 configurations:
# bare question 8B/35B (blind to the identity — correctly, given the info);
# ±250-char context 8B (catches it, 10 clean FPs) / 35B (still blind, 2 FPs);
# unanimous context-CONFIRMATION layer on bare-rejected pairs (still blind
# AND +4 clean FPs); recasting as a numeric revenue-chain check (extractor
# picks the self-consistent rate, catch is luck). The frozen config is the
# bare question. Durable fix: distillation (Phase 4) or the open-critique
# pass; not more prompt surgery here.
def is_derived(a: dict, b: dict, fact_values: list[float], rel_tolerance: float = 0.05) -> bool:
    """True when one value is (approximately) the other times some stated
    fact — e.g. $120/fleet = $8/van × 15 vans (avg fleet size). Such pairs
    are DERIVATIONS, not inconsistencies; measured as the pass's main FP
    source. Code decides — no vote involved."""
    va, vb = float(a["value"]), float(b["value"])
    lo, hi = sorted((abs(va), abs(vb)))
    if lo == 0:
        return False
    for f in fact_values:
        if f <= 1 or f in (va, vb):
            continue
        if abs(hi - lo * f) / hi <= rel_tolerance:
            return True
    return False


def candidate_pairs(facts: list[dict], rel_tolerance: float = 0.1, cap: int = 30) -> list[tuple[dict, dict]]:
    """Code-side pairing: same unit FAMILY, values disagreeing beyond
    tolerance. Concept-token overlap ranks pairs first (likely same quantity),
    but is not required — ARPU vs price share no token yet must be compared."""
    def overlap(a: dict, b: dict) -> int:
        stop = {"the", "a", "of", "per", "monthly", "plan", "target"}
        ta = {w for w in re.findall(r"[a-z0-9]+", a["concept"].lower()) if w not in stop}
        tb = {w for w in re.findall(r"[a-z0-9]+", b["concept"].lower()) if w not in stop}
        return len(ta & tb)

    pairs = []
    for i in range(len(facts)):
        for j in range(i + 1, len(facts)):
            a, b = facts[i], facts[j]
            if _unit_family(a["unit"]) != _unit_family(b["unit"]):
                continue
            va, vb = float(a["value"]), float(b["value"])
            if abs(va - vb) / max(abs(va), abs(vb), 1e-9) <= rel_tolerance:
                continue
            pairs.append((overlap(a, b), a, b))
    pairs.sort(key=lambda t: -t[0])
    return [(a, b) for _, a, b in pairs[:cap]]


async def consistency_audit(
    docs: dict[str, str],
    audit_keys: tuple[str, ...] | None = None,
    samples: int = 2,
    votes: int = 3,
    stats: dict | None = None,
) -> list[dict]:
    """Run the cross-document consistency micro-pass."""
    audit_keys = audit_keys or tuple(docs)
    facts: list[dict] = []
    seen: set[tuple] = set()
    for doc_key in audit_keys:
        doc_text = docs.get(doc_key) or ""
        if not doc_text.strip():
            continue
        for _ in range(samples):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": _FACTS_EXTRACT_PROMPT},
                        {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                    ],
                    model_tier=2, temperature=0.3, max_tokens=2048,
                    role="audit", think=False,
                )
            except Exception as e:
                logger.warning(f"consistency_audit extraction failed for {doc_key}: {e}")
                continue
            for item in _parse_items(reply):
                if not _fact_valid(item, doc_text):
                    continue
                key = (doc_key, round(float(item["value"]), 4), item["unit"])
                if key in seen:
                    continue
                seen.add(key)
                facts.append({"doc": doc_key, "quote": item["quote"],
                              "concept": item["concept"], "value": float(item["value"]),
                              "unit": item["unit"]})

    fact_values = [f["value"] for f in facts]
    pairs = [(a, b) for a, b in candidate_pairs(facts) if not is_derived(a, b, fact_values)]
    findings: list[dict] = []
    for a, b in pairs:
        votes_s: list[bool] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[{
                        "role": "user",
                        "content": _SAME_QUANTITY_PROMPT.format(
                            doc_a=a["doc"], quote_a=a["quote"],
                            doc_b=b["doc"], quote_b=b["quote"],
                        ),
                    }],
                    model_tier=2, temperature=0.3, max_tokens=256,
                    role="audit", think=False,
                )
                v = _parse_verdict_key(reply, "same_quantity")
                if v is not None:
                    votes_s.append(v)
            except Exception as e:
                logger.warning(f"consistency_audit same-quantity failed: {e}")
        if votes_s and sum(votes_s) * 2 > len(votes_s):  # bare majority flags
            findings.append({
                "kind": "cross-doc-inconsistency",
                "doc": f"{a['doc']} vs {b['doc']}",
                "quote": f"{a['quote']}  ⇄  {b['quote']}",
                "values": [a["value"], b["value"]],
                "unit": a["unit"],
            })
    if stats is not None:
        stats.update({
            "facts_extracted": len(facts),
            "pairs_compared": len(pairs),
            "findings": len(findings),
            "pairs_detail": [
                f"{a['doc']}[{a['concept']}={a['value']:g}] vs {b['doc']}[{b['concept']}={b['value']:g}] ({a['unit']})"
                for a, b in pairs
            ],
            "facts_detail": [
                f"{f['doc']}[{f['concept']}={f['value']:g} {f['unit']}]" for f in facts
            ],
        })
    return findings


def format_numeric_findings(findings: list[dict]) -> str:
    """Render findings in the DA report's evidence-first style."""
    if not findings:
        return ""
    lines = ["### Numeric audit (computed, not opined)"]
    for f in findings:
        lines.append(
            f"- **{f['doc']}** — the document claims **{f['claimed']:g}** but its own "
            f"inputs compute to **{f['computed']:g}** (`{f['expression']}`). "
            f'Quote: "{f["quote"]}"'
        )
    return "\n".join(lines)
