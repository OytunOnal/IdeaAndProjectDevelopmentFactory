"""Golden-intent eval runner.

Feeds each fixture case through the REAL discussion code path
(deterministic shortcuts + LLM action parsing + apply_discussion_action)
by building a minimal fake state and calling the actual discussion node,
then classifies the observed state diff and compares it to the expectation.

Usage (from backend/):
    python -m evals.eval_runner                 # full set
    python -m evals.eval_runner --limit 5       # smoke test
    python -m evals.eval_runner --tag regression
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import yaml

from app.agents.research import research_discussion_node
from app.agents.specification import review_discussion_node

FIXTURES = Path(__file__).parent / "fixtures" / "golden_intents.yaml"
RESULTS_DIR = Path(__file__).parent / "results"

STUB = "# {title}\n\nRealistic-enough stub content for eval purposes.\n\n## Recommended Adjustments\n\nNone — the current direction holds up.\n"

RESEARCH_KEYS = ("market_research", "competitor_analysis", "tech_feasibility")
SPEC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")
QUALITY_KEYS = ("devils_advocate", "consistency_report")


def build_state(context: dict, message: str) -> dict:
    """Minimal ProjectState that puts the pipeline at the case's gate."""
    phase = context.get("phase", "specification")
    gate = context.get("gate_doc")

    state: dict = {
        "current_phase": phase,
        "pipeline_status": "running",
        "project_name": "EvalProject",
        "idea_brief": {
            "confirmed": True,
            "problem_statement": "Freelancers lose income to unpaid invoices.",
            "value_proposition": "Automated, polite invoice-chasing assistant.",
            "target_users": [{"type": "freelancers", "priority": "primary"}],
            "core_features": ["invoice tracking", "auto reminders"],
            "revenue_model": "subscription",
            "domain_category": "fintech-saas",
        },
        "approved_docs": [],
        "messages": [
            {"id": "m1", "role": "agent", "agent_id": "orchestrator",
             "content": "Document ready — awaiting your review.", "timestamp": ""},
            {"id": "m2", "role": "user", "content": message, "timestamp": ""},
        ],
    }

    # Materialize every doc that must exist BEFORE this gate, so cross-doc
    # revise/reopen targets resolve. Docs up to and including the gate exist;
    # everything before the gate (and earlier phases) is approved.
    def add(key: str, as_dict: bool) -> None:
        content = STUB.format(title=key.replace("_", " ").title())
        state[key] = {"completed": True, "report": content} if as_dict else content

    phase_order = {"discovery": 0, "specification": 1, "quality": 2,
                   "packaging": 3, "completed": 4}
    p = phase_order.get(phase, 1)

    if p >= 1 or phase == "discovery":
        for k in RESEARCH_KEYS:
            add(k, as_dict=True)
            if p >= 1 or k != gate:
                state["approved_docs"].append(k)
    if p >= 2 or phase == "specification":
        for k in SPEC_KEYS:
            add(k, as_dict=False)
            if p >= 2 or k != gate:
                state["approved_docs"].append(k)
    if p >= 3 or phase == "quality":
        for k in QUALITY_KEYS:
            add(k, as_dict=False)
            if p >= 3 or k != gate:
                state["approved_docs"].append(k)
        state["quality_feedback"] = STUB.format(title="Quality Review")
    if p >= 3:
        state["implementation_roadmap"] = STUB.format(title="Roadmap")

    # The gate doc itself must exist and NOT be approved
    if gate:
        in_research = gate in RESEARCH_KEYS
        add(gate, as_dict=in_research)
        state["approved_docs"] = [k for k in state["approved_docs"] if k != gate]

    return state


def observe(before: dict, after: dict | None) -> dict:
    """Classify the pipeline effect of the discussion turn."""
    if not after:
        return {"action": "no_action"}
    if after.get("revision_target"):
        return {"action": "revise", "target": after["revision_target"]}
    if after.get("quality_improve_requested") and not before.get("quality_improve_requested"):
        return {"action": "improve"}
    ba, aa = set(before.get("approved_docs") or []), set(after.get("approved_docs") or [])
    if aa - ba:
        return {"action": "approve", "target": next(iter(aa - ba))}
    if ba - aa:  # a doc lost its approval → its gate was reopened
        return {"action": "reopen", "target": next(iter(ba - aa))}
    pd = after.get("pending_decision") or {}
    if isinstance(pd, dict) and str(pd.get("id", "")).startswith("approve-doc:"):
        reopened = pd["id"].split(":", 1)[1]
        if reopened in ba:
            return {"action": "reopen", "target": reopened}
    return {"action": "no_action"}


def matches(expect: dict, observed: dict, gate: str | None) -> bool:
    ea, et = expect["action"], expect.get("target")
    oa, ot = observed["action"], observed.get("target")
    if ea in ("question", "clarify", "no_state_change"):
        return oa == "no_action"
    if ea == "rewrite":  # system expresses rewrite as revise-on-the-gate-doc
        return oa == "revise" and ot == (et or gate)
    if ea == "revise":
        return oa == "revise" and (et is None or ot == et)
    if ea == "approve":
        return oa == "approve"
    if ea == "reopen":
        return oa == "reopen" and (et is None or ot == et)
    if ea == "improve":
        return oa == "improve"
    return False


async def run_case(case: dict) -> dict:
    phase = case["context"].get("phase", "specification")
    state = build_state(case["context"], case["message"])
    node = research_discussion_node if phase == "discovery" else review_discussion_node
    t0 = time.perf_counter()
    try:
        after = await node(state)
        error = None
    except Exception as exc:  # a crashing case is a failing case, not a crash
        after, error = None, f"{type(exc).__name__}: {exc}"
    observed = observe(state, after)
    ok = error is None and matches(case["expect"], observed, case["context"].get("gate_doc"))
    reply = ""
    if after:
        msgs = after.get("messages") or []
        if msgs and msgs[-1].get("role") == "agent":
            reply = (msgs[-1].get("content") or "")[:200]
    return {
        "id": case["id"], "tags": case.get("tags", []),
        "expected": case["expect"], "observed": observed,
        "ok": ok, "error": error, "reply_head": reply,
        "seconds": round(time.perf_counter() - t0, 1),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", type=str, default=None)
    args = ap.parse_args()

    cases = yaml.safe_load(FIXTURES.read_text(encoding="utf-8"))
    if args.tag:
        cases = [c for c in cases if args.tag in c.get("tags", [])]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} golden-intent cases (real code path, real LLM)...")
    results = []
    for i, case in enumerate(cases, 1):
        r = await run_case(case)
        results.append(r)
        mark = "OK  " if r["ok"] else ("ERR " if r["error"] else "MISS")
        print(f"  [{i:02d}/{len(cases)}] {mark} {r['id']}  "
              f"exp={r['expected']['action']} obs={r['observed']['action']} ({r['seconds']}s)")

    total = len(results)
    passed = sum(r["ok"] for r in results)
    by_tag: dict[str, list] = {}
    for r in results:
        for t in r["tags"]:
            by_tag.setdefault(t, []).append(r["ok"])

    print(f"\nTOTAL: {passed}/{total} ({passed / total:.0%})")
    print("\nBy tag:")
    for tag, oks in sorted(by_tag.items()):
        print(f"  {tag:<16} {sum(oks)}/{len(oks)}")
    fails = [r for r in results if not r["ok"]]
    if fails:
        print("\nFailures:")
        for r in fails:
            print(f"  - {r['id']}: expected {r['expected']}, observed {r['observed']}"
                  + (f" [{r['error']}]" if r["error"] else ""))

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"intents_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({
        "total": total, "passed": passed,
        "by_tag": {t: f"{sum(o)}/{len(o)}" for t, o in by_tag.items()},
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
