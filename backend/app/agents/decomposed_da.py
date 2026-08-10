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
    """Collapse whitespace AND formatting punctuation — models quote content,
    not formatting: `**bold**`, heading markers, list bullets, and label
    colons must not break substring matching (measured: a valid absurd-target
    candidate was rejected for three rounds because the model wrote
    "Targets: X" where the doc had "## Targets\\n- X")."""
    return re.sub(r"\s+", " ", re.sub(r"[*`_#:;|•–—-]", "", text)).strip()


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


def cross_line_inputs(item: dict) -> list[float]:
    """Expression inputs that do NOT appear in the claim's own quote —
    i.e. the model pulled them from elsewhere in the document. Scaffolding
    constants don't count."""
    quote_numbers = _numbers_in(item.get("quote", ""))
    return [n for n in _numbers_in(item.get("expression", ""))
            if not _grounded(n, quote_numbers, scaffolding=True)]


def sentence_with_number(doc_text: str, value: float) -> str:
    """First document line containing the value (percent variants included) —
    used to show a chain-confirmation judge where an outside input came from."""
    for line in doc_text.splitlines():
        if _grounded(value, _numbers_in(line), scaffolding=False):
            return line.strip()
    return ""


_CHAIN_CONFIRM_PROMPT = """Answer one narrow question about an arithmetic claim in a document.

The document claims: "{quote}" (stated result: {claimed}).
A checker built the computation `{expression}` using inputs from OTHER lines of the same document:
{sources}

Is `{expression}` the computation this claim itself describes — do the input quantities' TYPES match what the claimed result measures? (Fictional example of a mismatch: the claim states a per-renter CONTRIBUTION, but the chained input is the platform's per-booking REVENUE — related numbers, wrong computation.)

Respond with ONLY a fenced JSON object:
```json
{{"matches": true/false}}
```"""


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
                # cross-line chain confirmation (measured held-out FP class):
                # when inputs came from other lines, the model may have chained
                # a related-but-wrong rate (revenue vs contribution) — a narrow
                # type-match vote gates the finding; in-quote claims skip this
                outside = cross_line_inputs(item)
                if outside:
                    sources = "\n".join(
                        f'- {v:g}: "{sentence_with_number(doc_text, v)}"' for v in outside
                    )
                    votes_m: list[bool] = []
                    for _ in range(3):
                        try:
                            reply_c = await call_llm(
                                messages=[{
                                    "role": "user",
                                    "content": _CHAIN_CONFIRM_PROMPT.format(
                                        quote=item["quote"], claimed=item["claimed"],
                                        expression=item["expression"], sources=sources,
                                    ),
                                }],
                                model_tier=2, temperature=0.3, max_tokens=256,
                                role="audit", think=False,
                            )
                            v = _parse_verdict_key(reply_c, "matches")
                            if v is not None:
                                votes_m.append(v)
                        except Exception as e:
                            logger.warning(f"numeric_audit chain-confirm failed: {e}")
                    if not (votes_m and sum(votes_m) * 2 > len(votes_m)):
                        logger.debug(f"numeric_audit: cross-line chain not confirmed, dropped: {item}")
                        continue
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
def is_derived(a: dict, b: dict, facts: list[dict], rel_tolerance: float = 0.05) -> bool:
    """True when one value is (approximately) the other times some stated
    COUNT-like fact — e.g. $120/fleet = $8/van × 15 vans (avg fleet size).
    Such pairs are DERIVATIONS, not inconsistencies; measured as the pass's
    main FP source. Code decides — no vote involved.

    Multiplier candidates are restricted to facts whose unit family differs
    from the pair's (a money pair is multiplied by a count, never by another
    money value). Measured edge this fixes: a fleet COUNT of 120 and a fleet
    revenue of $120 collide numerically — the old value-based exclusion
    disabled the guard exactly when the multiplier equaled a pair value."""
    va, vb = float(a["value"]), float(b["value"])
    lo, hi = sorted((abs(va), abs(vb)))
    if lo == 0:
        return False
    pair_family = _unit_family(a["unit"])
    cross_unit = [float(f["value"]) for f in facts
                  if _unit_family(f["unit"]) != pair_family and float(f["value"]) > 1]
    same_unit = [float(f["value"]) for f in facts
                 if _unit_family(f["unit"]) == pair_family]
    for f in cross_unit:
        # one-factor: the larger value = the smaller × a stated count
        if abs(hi - lo * f) / hi <= rel_tolerance:
            return True
        # two-factor: the larger value = a stated count × another same-family
        # fact (e.g. $14,400 MRR = 120 fleets × $120/fleet, where neither
        # factor is the pair's other member) — extraction variance means the
        # one-factor route's exact multiplier isn't always in the fact list
        for g in same_unit:
            if g in (va, vb):
                continue
            if abs(hi - f * g) / hi <= rel_tolerance:
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
            # degenerate self-pair guard (measured on held-out): two extraction
            # variants of the SAME sentence must not be compared against each
            # other — same doc + overlapping quotes is the same statement
            qa, qb = _normalize_ws(a["quote"]).lower(), _normalize_ws(b["quote"]).lower()
            if a["doc"] == b["doc"] and (qa in qb or qb in qa):
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

    pairs = [(a, b) for a, b in candidate_pairs(facts) if not is_derived(a, b, facts)]
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


# ── pass 5: open critique ──────────────────────────────────────────────────
#
# The one deliberately broad pass, for defect classes narrow questions can't
# enumerate: internal contradictions, technically infeasible components,
# absurd targets, audience mismatches, unrealistic plans. Two design moves
# keep a small model viable where the monolithic DA failed: (1) the scope is
# per-DOCUMENT (short context — the regime the model measures well in) and
# excludes everything passes 1-4 own (no math, no evidence, no absence, no
# cross-doc checks); (2) every candidate issue must quote the document
# verbatim (code-checked) and then survive an adversarial verification vote
# (3-vote majority on "is this a genuine flaw?") before becoming a finding.

_CRITIQUE_PROMPT = """You are a focused reviewer of ONE specification document. Other checks already handle arithmetic, fabricated evidence, missing sections, and cross-document consistency — do NOT report those. You look ONLY for these flaw types within this document:

All examples below are from a FICTIONAL studio-booking product — patterns, not content to look for:

1. INTERNAL CONTRADICTION — the document claims X in one place and not-X in another (e.g. "all booking data stays on the studio's own server" alongside "our cloud dashboard aggregates every studio's bookings").
2. INFEASIBLE TECHNOLOGY — a component that cannot work as described or is wildly disproportionate (e.g. "renders a full 3D walkthrough by training a neural radiance field live on the visitor's phone").
3. ABSURD TARGET — a goal impossible at the stated resources/timeline (e.g. "capture 60% of all studios nationwide within 8 weeks purely by word of mouth").
4. AUDIENCE MISMATCH — a design choice that contradicts the document's own stated audience (e.g. "the seniors-focused fitness app uses 8px fonts and gesture-only navigation").
5. INFEASIBLE PLAN — team/timeline/scope combinations that cannot deliver (e.g. "a two-person team ships native iOS, Android, web, and smart-TV apps simultaneously in their first month").

Rules:
- "quote": copy the flawed sentence(s) VERBATIM from the document.
- "issue": one sentence naming the flaw concretely.
- "category": one of internal-contradiction | infeasible-tech | absurd-target | audience-mismatch | infeasible-plan.
- Report REAL flaws only — do not manufacture criticism of a sound document. An empty array is a valid, common answer.
- At most 4 issues; severity over quantity.

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"quote": "...", "issue": "...", "category": "..."}]
```"""

_CRITIQUE_VERIFY_PROMPT = """You are a referee judging one proposed review finding. You have two duties of EQUAL weight:
- Genuine, serious flaws DO occur in documents and MUST survive your review — waving a real defect through as "defensible" is a failure.
- Manufactured criticism MUST die — a defensible product choice, a stylistic nitpick, or a misreading dressed up as a flaw is also a failure.

Document ({doc_key}):
{doc_text}

Proposed finding ({category}): {issue}
Quoted text: "{quote}"

The bar: would a competent reviewer stake their name on this finding as stated?

Both sides, fictional examples:
- Document says "all booking data stays on the studio's own server" and elsewhere "our cloud dashboard aggregates every studio's bookings" — proposed as internal-contradiction → genuine: true (the two statements cannot both hold; a competent reviewer would flag this).
- Document says "onboarding takes about ten minutes" — proposed as internal-contradiction because another section calls the product "instant to adopt" → genuine: false (marketing phrasing vs a setup estimate is not a contradiction; this is a nitpick).

Respond with ONLY a fenced JSON object:
```json
{{"genuine": true/false}}
```"""

CRITIQUE_CATEGORIES = (
    "internal-contradiction", "infeasible-tech", "absurd-target",
    "audience-mismatch", "infeasible-plan",
)


async def critique_audit(
    docs: dict[str, str],
    audit_keys: tuple[str, ...] | None = None,
    samples: int = 3,
    votes: int = 3,
    gen_tier: int = 2,
    judge_tier: int = 2,
    repeats: int = 1,
    stats: dict | None = None,
) -> list[dict]:
    """Run the open-critique micro-pass, optionally as a union ensemble.

    judge_tier routes the verification votes separately from candidate
    generation — measured division of labor: the fast model over-generates
    but never misses a planted flaw among its candidates; the quality model
    generates narrowly but is the only one whose genuineness judgment
    discriminates (fast-model judging rubber-stamped or blanket-refuted in
    every framing tried).

    repeats runs the whole generate+judge cycle independently N times and
    unions the findings (containment-deduped). Measured motive: single-run
    recall oscillates 3-5/6 on dev purely from sampling (different planted
    flaws survive each run) while the FP base holds at 0 — union raises
    recall without a symmetric FP cost."""
    merged: list[dict] = []
    merged_quotes: set[str] = set()
    agg = {"candidates": 0, "candidate_quotes": []}
    for _ in range(max(1, repeats)):
        rep_stats: dict = {}
        findings = await _critique_once(docs, audit_keys, samples, votes, gen_tier, judge_tier, rep_stats)
        agg["candidates"] += rep_stats.get("candidates", 0)
        agg["candidate_quotes"].extend(rep_stats.get("candidate_quotes", []))
        for f in findings:
            key = _normalize_ws(f["quote"]).lower()
            if any(key in s or s in key for s in merged_quotes):
                continue
            merged_quotes.add(key)
            merged.append(f)
    if stats is not None:
        stats.update({**agg, "findings": len(merged), "repeats": max(1, repeats)})
    return merged


async def _critique_once(
    docs: dict[str, str],
    audit_keys: tuple[str, ...] | None,
    samples: int,
    votes: int,
    gen_tier: int,
    judge_tier: int,
    stats: dict | None,
) -> list[dict]:
    """One full generate+judge cycle of the open-critique pass."""
    audit_keys = audit_keys or tuple(docs)
    candidates: list[dict] = []
    seen: set[str] = set()
    for doc_key in audit_keys:
        doc_text = docs.get(doc_key) or ""
        if not doc_text.strip():
            continue
        for _ in range(samples):
            try:
                reply = await call_llm(
                    messages=[
                        {"role": "system", "content": _CRITIQUE_PROMPT},
                        {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                    ],
                    model_tier=gen_tier, temperature=0.7, max_tokens=1536,
                    role="audit", think=False,
                )
            except Exception as e:
                logger.warning(f"critique_audit sampling failed for {doc_key}: {e}")
                continue
            for item in _parse_items(reply):
                quote, issue = item.get("quote", ""), item.get("issue", "")
                category = item.get("category", "")
                if not quote or not issue or category not in CRITIQUE_CATEGORIES:
                    continue
                if _normalize_ws(quote) not in _normalize_ws(doc_text):
                    logger.debug(f"critique_audit: quote not in doc, rejected: {quote!r}")
                    continue
                key = _normalize_ws(quote).lower()
                if any(key in s or s in key for s in seen):
                    continue
                seen.add(key)
                candidates.append({"doc": doc_key, "quote": quote,
                                   "issue": issue, "category": category})

    findings: list[dict] = []
    for cand in candidates:
        votes_g: list[bool] = []
        for _ in range(votes):
            try:
                reply = await call_llm(
                    messages=[{
                        "role": "user",
                        "content": _CRITIQUE_VERIFY_PROMPT.format(
                            doc_key=cand["doc"], doc_text=docs[cand["doc"]],
                            category=cand["category"], issue=cand["issue"],
                            quote=cand["quote"],
                        ),
                    }],
                    model_tier=judge_tier, temperature=0.3, max_tokens=256,
                    role="audit", think=False,
                )
                v = _parse_verdict_key(reply, "genuine")
                if v is not None:
                    votes_g.append(v)
            except Exception as e:
                logger.warning(f"critique_audit verify failed: {e}")
        # 3-vote majority on a TWO-SIDED question. Measured both failure
        # modes on dev: an approval-framed verify rubber-stamped every
        # candidate (7+14 clean FPs); a refute-framed unanimous verify
        # killed all six planted defects. Two-sided policy + majority is
        # the same cure that ended the Phase 1 verifier oscillation.
        if votes_g and sum(votes_g) * 2 > len(votes_g):
            findings.append({"kind": cand["category"], **{k: cand[k] for k in ("doc", "quote", "issue")}})
    if stats is not None:
        stats.update({
            "candidates": len(candidates),
            "findings": len(findings),
            "candidate_quotes": [c["quote"][:90] for c in candidates],
        })
    return findings


# ── pass 6: scope echo ─────────────────────────────────────────────────────
#
# Targets out-of-scope references: the PRD explicitly excludes a feature
# from v1, and another document quietly designs or sells it anyway. Both
# stages are narrow-factual (the measured safe zone for the fast model):
# extract the PRD's exclusion list, then ask per (feature × other doc)
# whether that doc describes the feature as part of the product — with the
# usual guards (verbatim quote required for a positive vote, 3-vote
# majority, mention-as-excluded doesn't count).

_SCOPE_EXTRACT_PROMPT = """You are a scope-list extractor. From the PRD below, extract the features EXPLICITLY EXCLUDED from the current version (v1) — the "Out of scope" / "Won't have" / "Out (v1)" items.

Rules:
- "feature": the excluded item as a short phrase, close to the document's own wording.
- Only items the PRD itself excludes; do not infer.

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"feature": "group study rooms"}, {"feature": "native tablet apps"}]
```
If the PRD has no exclusion list, respond with an empty array."""

_SCOPE_PRESENT_PROMPT = """Answer one narrow question about one specification document.

The product's PRD explicitly EXCLUDES this feature from v1: "{feature}"

Does the document below DESCRIBE OR SPECIFY this feature as part of the product's v1 experience — a flow, screen, plan, or design for it? Mentioning the feature as excluded/future/a competitor's does NOT count; only treating it as something the product ships.

Rules:
- If present: "quote" must be a VERBATIM sentence from the document proving it.
- If not present: "quote" is "".

Respond with ONLY a fenced JSON object:
```json
{{"present": true/false, "quote": "..."}}
```"""


async def scope_audit(
    docs: dict[str, str],
    audit_keys: tuple[str, ...] | None = None,
    prd_key: str = "prd",
    samples: int = 2,
    votes: int = 3,
    stats: dict | None = None,
) -> list[dict]:
    """Run the scope-echo micro-pass: PRD exclusions vs the other docs."""
    audit_keys = audit_keys or tuple(docs)
    prd_text = docs.get(prd_key) or ""
    if not prd_text.strip():
        return []

    features: list[str] = []
    for _ in range(samples):
        try:
            reply = await call_llm(
                messages=[
                    {"role": "system", "content": _SCOPE_EXTRACT_PROMPT},
                    {"role": "user", "content": f"PRD:\n\n{prd_text}"},
                ],
                model_tier=2, temperature=0.3, max_tokens=512,
                role="audit", think=False,
            )
        except Exception as e:
            logger.warning(f"scope_audit extraction failed: {e}")
            continue
        for item in _parse_items(reply):
            feature = item.get("feature", "")
            if not feature or not isinstance(feature, str):
                continue
            key = _normalize_ws(feature).lower()
            if any(key in s or s in key for s in map(str.lower, map(_normalize_ws, features))):
                continue
            features.append(feature)

    findings: list[dict] = []
    for feature in features:
        for doc_key in audit_keys:
            if doc_key == prd_key:
                continue
            doc_text = docs.get(doc_key) or ""
            if not doc_text.strip():
                continue
            votes_p: list[bool] = []
            proof = ""
            for _ in range(votes):
                try:
                    reply = await call_llm(
                        messages=[
                            {"role": "system", "content": _SCOPE_PRESENT_PROMPT.format(feature=feature)},
                            {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                        ],
                        model_tier=2, temperature=0.3, max_tokens=384,
                        role="audit", think=False,
                    )
                    data = _parse_json_object(reply)
                    present = data.get("present") if data else None
                    if not isinstance(present, bool):
                        continue
                    if present:
                        quote = data.get("quote", "")
                        # a positive vote must prove itself with a real quote
                        if not quote or _normalize_ws(quote) not in _normalize_ws(doc_text):
                            logger.debug(f"scope_audit: present-vote without valid quote dropped ({doc_key})")
                            continue
                        proof = quote
                        votes_p.append(True)
                    else:
                        votes_p.append(False)
                except Exception as e:
                    logger.warning(f"scope_audit presence failed: {e}")
            if votes_p and sum(votes_p) * 2 > len(votes_p):  # majority present
                findings.append({
                    "kind": "out-of-scope-reference",
                    "doc": doc_key,
                    "feature": feature,
                    "issue": f'The PRD excludes "{feature}" from v1, but this document specifies it.',
                    "quote": proof,
                })
    if stats is not None:
        stats.update({"excluded_features": len(features), "findings": len(findings)})
    return findings


# ── composition ────────────────────────────────────────────────────────────

_SECTION_ORDER = (
    ("arithmetic", "Numeric audit — computed, not opined"),
    ("unsupported-evidence", "Unsupported evidence"),
    ("missing-critical", "Missing critical coverage"),
    ("cross-doc-inconsistency", "Cross-document inconsistencies"),
    ("out-of-scope-reference", "Scope violations"),
    ("internal-contradiction", "Internal contradictions"),
    ("infeasible-tech", "Technical feasibility"),
    ("infeasible-plan", "Plan feasibility"),
    ("absurd-target", "Target realism"),
    ("audience-mismatch", "Audience fit"),
)


def compose_report(findings: list[dict]) -> str:
    """Render all micro-pass findings as one Devil's Advocate report.

    Deliberately deterministic — no synthesis call. Every line carries its
    evidence (quote or computation), grouped by finding kind; a clean bundle
    yields an honest short report, not manufactured criticism."""
    lines = ["# Devil's Advocate Report", ""]
    total = len(findings)
    if total == 0:
        lines.append(
            "No substantiated findings. Every check in the decomposed review "
            "(numeric audit, evidence audit, absence scan, cross-document "
            "consistency, open critique) came back clean. Absence of findings "
            "is a real result here, not a skipped review."
        )
        return "\n".join(lines)

    lines.append(f"{total} substantiated finding(s). Every finding carries its evidence.\n")
    for kind, title in _SECTION_ORDER:
        section = [f for f in findings if f.get("kind") == kind]
        if not section:
            continue
        lines.append(f"## {title}")
        for f in section:
            if kind == "arithmetic":
                lines.append(
                    f"- **{f['doc']}** — claims **{f['claimed']:g}** but its own inputs "
                    f"compute to **{f['computed']:g}** (`{f['expression']}`). "
                    f"Quote: \"{f['quote']}\""
                )
            elif kind == "unsupported-evidence":
                lines.append(
                    f"- **{f['doc']}** — presupposes evidence no document supports "
                    f"({f['asserts']}). Quote: \"{f['quote']}\""
                )
            elif kind == "missing-critical":
                lines.append(f"- **{f['topic']}** — {f['detail']}")
            elif kind == "cross-doc-inconsistency":
                lines.append(
                    f"- **{f['doc']}** — the same quantity is stated as "
                    f"**{f['values'][0]:g}** and **{f['values'][1]:g}** ({f['unit']}). "
                    f"Quote: \"{f['quote']}\""
                )
            else:  # critique kinds
                lines.append(f"- **{f['doc']}** — {f['issue']} Quote: \"{f['quote']}\"")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


async def run_decomposed_da(
    docs: dict[str, str],
    brief: dict | None = None,
    audit_keys: tuple[str, ...] | None = None,
    stats: dict | None = None,
) -> tuple[list[dict], str]:
    """Run all five micro-passes over a bundle and compose the DA report.

    `docs` may include research documents; `audit_keys` names the spec docs
    under review (defaults to every key). Findings are cross-pass deduped by
    quote containment — passes intentionally overlap on planted-defect
    echoes (redundancy is a recall feature, duplicate lines in the report
    are not)."""
    audit_keys = audit_keys or tuple(docs)
    spec_docs = {k: docs[k] for k in audit_keys if docs.get(k)}

    # Frozen per-pass model routing (dev-set measured): the four narrow
    # passes run on the fast model (tier 2); the open-critique pass needs the
    # quality model (tier 1) for BOTH generation and judging — the fast
    # model's genuineness judgment discriminated in no framing tried.
    per_pass: dict[str, list[dict]] = {}
    per_pass["numeric"] = await numeric_audit(spec_docs)
    per_pass["evidence"] = await evidence_audit(docs, audit_keys=audit_keys)
    per_pass["absence"] = await absence_audit(docs, brief=brief, audit_keys=audit_keys)
    per_pass["consistency"] = await consistency_audit(spec_docs)
    per_pass["scope"] = await scope_audit(spec_docs)
    # repeats=2: single-run critique recall oscillates (3-5 of 6 on dev) from
    # two-layer sampling; the union stabilizes it and the composed clean runs
    # absorb the occasional single FP
    per_pass["critique"] = await critique_audit(spec_docs, gen_tier=1, judge_tier=1, repeats=2)

    merged: list[dict] = []
    seen_quotes: set[str] = set()
    for name in ("numeric", "evidence", "absence", "consistency", "scope", "critique"):
        for f in per_pass[name]:
            quote = f.get("quote", "")
            if quote:
                key = _normalize_ws(quote).lower()
                if any(key in s or s in key for s in seen_quotes):
                    continue
                seen_quotes.add(key)
            merged.append(f)
    if stats is not None:
        stats.update({name: len(fs) for name, fs in per_pass.items()})
        stats["merged"] = len(merged)
    return merged, compose_report(merged)


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
