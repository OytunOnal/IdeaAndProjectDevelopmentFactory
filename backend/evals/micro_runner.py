"""Micro-pass eval runner (Phase 3, decomposed DA).

Runs a single micro-pass over a fixture bundle (clean or defected) and
reports findings, so each pass's recall/precision can be measured in
isolation before composition. Development happens on --set dev ONLY; the
held-out set is sealed (fixtures/heldout_defects/HELDOUT.md).

Usage (from backend/, model selected via env like the other runners):
    LLM_FORCE_PROVIDER=ollama OLLAMA_MODEL_QUALITY=qwen3:8b OLLAMA_MODEL_FAST=qwen3:8b \
        MODEL_LABEL=qwen3-8b python -m evals.micro_runner --pass numeric
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import yaml

from app.agents.decomposed_da import (
    absence_audit,
    consistency_audit,
    critique_audit,
    evidence_audit,
    numeric_audit,
    run_decomposed_da,
    scope_audit,
)
from evals.defect_runner import BRIEFS, FIXTURES_ROOT, SETS, load_bundle, model_label

RESULTS = Path(__file__).parent / "results" / "micro"

RESEARCH_KEYS = ("market_research", "competitor_analysis", "tech_feasibility")

PASSES = ("numeric", "evidence", "absence", "consistency", "scope", "critique", "full")

# Defect types each pass is RESPONSIBLE for (recall is scored against these
# only; other defect types are other passes' jobs).
PASS_SCOPE = {
    "numeric": ("arithmetic-error", "impossible-math"),
    "evidence": ("fabricated-evidence",),
    "absence": ("missing-critical",),
    "consistency": ("cross-doc-inconsistency",),
    "critique": ("internal-contradiction", "infeasible-tech", "absurd-target",
                 "audience-mismatch", "infeasible-plan"),
    "scope": ("out-of-scope-reference",),
    "full": None,  # composed run: in scope = every defect type
}


async def run_one(pass_name: str, project: str, variant: str, manifest: list[dict], fixtures: Path) -> dict:
    docs = load_bundle(project, variant, manifest, fixtures)
    t0 = time.perf_counter()
    stats: dict = {}
    report = None
    if pass_name == "full":
        research = {
            key: path.read_text(encoding="utf-8")
            for key in RESEARCH_KEYS
            if (path := fixtures / project / f"{key}.md").exists()
        }
        findings, report = await run_decomposed_da(
            {**research, **docs}, brief=BRIEFS[project], audit_keys=tuple(docs), stats=stats
        )
    elif pass_name == "evidence":
        # research docs join the bundle as verification sources; only the
        # spec docs (the defect surface) are audited for claims
        research = {
            key: path.read_text(encoding="utf-8")
            for key in RESEARCH_KEYS
            if (path := fixtures / project / f"{key}.md").exists()
        }
        findings = await evidence_audit({**research, **docs}, audit_keys=tuple(docs), stats=stats)
    elif pass_name == "consistency":
        findings = await consistency_audit(docs, stats=stats)
    elif pass_name == "scope":
        findings = await scope_audit(docs, stats=stats)
    elif pass_name == "critique":
        judge_tier = int(os.environ.get("CRITIQUE_JUDGE_TIER", "2"))
        c_samples = int(os.environ.get("CRITIQUE_SAMPLES", "3"))
        c_repeats = int(os.environ.get("CRITIQUE_REPEATS", "1"))
        findings = await critique_audit(
            docs, samples=c_samples, judge_tier=judge_tier, repeats=c_repeats, stats=stats
        )
    elif pass_name == "absence":
        research = {
            key: path.read_text(encoding="utf-8")
            for key in RESEARCH_KEYS
            if (path := fixtures / project / f"{key}.md").exists()
        }
        findings = await absence_audit(
            {**research, **docs}, brief=BRIEFS[project], audit_keys=tuple(docs), stats=stats
        )
    else:
        findings = await numeric_audit(docs)
    seconds = round(time.perf_counter() - t0, 1)

    scope = PASS_SCOPE[pass_name]
    in_scope = [
        d for d in manifest
        if d["project"] == project and (scope is None or d["type"] in scope)
    ]
    result = {
        "pass": pass_name, "project": project, "variant": variant,
        "model_label": model_label(), "seconds": seconds,
        "findings": findings,
        "stage_stats": stats or None,
        "in_scope_defects": [d["id"] for d in in_scope] if variant == "defected" else [],
    }
    outdir = RESULTS / model_label()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{pass_name}_{project}_{variant}"
    (outdir / f"{stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if report is not None:
        (outdir / f"{stem}_report.md").write_text(report, encoding="utf-8")

    if "claims_extracted" in stats:
        stage = f"  [extracted {stats['claims_extracted']} → gated {stats['claims_gated_in']}]"
    elif "applicable_items" in stats:
        stage = f"  [checklist {stats['checklist_items']} → applicable {stats['applicable_items']}]"
    elif "facts_extracted" in stats:
        stage = f"  [facts {stats['facts_extracted']} → pairs {stats['pairs_compared']}]"
    elif "merged" in stats:
        stage = ("  [num {numeric} + evid {evidence} + abs {absence} + cons {consistency}"
                 " + scope {scope} + crit {critique} → {merged}]").format(**stats)
    elif "excluded_features" in stats:
        stage = f"  [excluded features {stats['excluded_features']}]"
    elif "candidates" in stats:
        stage = f"  [candidates {stats['candidates']}]"
    else:
        stage = ""
    print(f"  [{model_label()}] {stem}: {len(findings)} findings in {seconds}s{stage}")
    for f in findings:
        if "computed" in f:
            print(f"      {f['doc']}: claimed {f['claimed']:g}, computed {f['computed']:g}  ({f['expression']})")
        elif "quote" in f:
            print(f"      {f['doc']}: {f['kind']} — {f['quote'][:100]!r}")
        else:
            print(f"      {f['kind']}: {f['topic']}")
    if variant == "defected" and in_scope:
        print(f"      in-scope defects to catch: {[d['id'] for d in in_scope]}")
    return result


async def main() -> None:
    all_projects = [p for s in SETS.values() for p in s["projects"]]
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="pass_name", choices=PASSES, default="numeric")
    ap.add_argument("--set", choices=list(SETS), default="dev",
                    help="heldout is SEALED — read fixtures/heldout_defects/HELDOUT.md first")
    ap.add_argument("--project", choices=[*all_projects, "both"], default="both")
    ap.add_argument("--variant", choices=["clean", "defected", "both"], default="both")
    args = ap.parse_args()

    fixtures = FIXTURES_ROOT / SETS[args.set]["dir"]
    set_projects = SETS[args.set]["projects"]
    manifest = yaml.safe_load((fixtures / "manifest.yaml").read_text(encoding="utf-8"))
    if args.project == "both":
        projects = set_projects
    elif args.project in set_projects:
        projects = (args.project,)
    else:
        raise SystemExit(f"--project {args.project} is not in set '{args.set}' {set_projects}")
    variants = ("clean", "defected") if args.variant == "both" else (args.variant,)

    runs = [(p, v) for p in projects for v in variants]
    print(f"pass={args.pass_name}  set={args.set}  model={model_label()}  runs={len(runs)}")
    for p, v in runs:
        await run_one(args.pass_name, p, v, manifest, fixtures)
    print("Done —", RESULTS / model_label())


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    asyncio.run(main())
