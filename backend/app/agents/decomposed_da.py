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
- explicit formulas: "LTV: $144 (12 × $12)"
- ratios: "LTV:CAC ≈ 3.6:1" where LTV and CAC both appear in the document
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

Example — document says "LTV: $35" and "CAC: $40" and "LTV:CAC ≈ 3.6 : 1":
```json
[{"quote": "LTV:CAC ≈ 3.6 : 1", "expression": "35 / 40", "claimed": 3.6}]
```
(claimed is 3.6 — the document's stated ratio — NOT 0.875, your computation.)

Example — document says "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months". This ONE sentence yields TWO checkable claims (lifetime = 1/churn; retained = (1-churn)^12):
```json
[{"quote": "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months", "expression": "1 / 0.05", "claimed": 20},
 {"quote": "Monthly churn: 5% → average lifetime ≈ 20 months → ~54% retained after 12 months", "expression": "(1 - 0.05) ** 12", "claimed": 0.54}]
```
Churn/lifetime/retention chains are a REQUIRED extraction whenever a document states them — do not skip them.

Respond with ONLY a fenced JSON array (no commentary):
```json
[{"quote": "...", "expression": "12 * 12", "claimed": 144}]
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
