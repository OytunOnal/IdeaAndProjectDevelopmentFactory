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

from app.agents.decomposed_da import numeric_audit
from evals.defect_runner import FIXTURES_ROOT, SETS, load_bundle, model_label

RESULTS = Path(__file__).parent / "results" / "micro"

PASSES = {
    "numeric": numeric_audit,
}

# Defect types each pass is RESPONSIBLE for (recall is scored against these
# only; other defect types are other passes' jobs).
PASS_SCOPE = {
    "numeric": ("arithmetic-error", "impossible-math"),
}


async def run_one(pass_name: str, project: str, variant: str, manifest: list[dict], fixtures: Path) -> dict:
    docs = load_bundle(project, variant, manifest, fixtures)
    t0 = time.perf_counter()
    findings = await PASSES[pass_name](docs)
    seconds = round(time.perf_counter() - t0, 1)

    in_scope = [
        d for d in manifest
        if d["project"] == project and d["type"] in PASS_SCOPE[pass_name]
    ]
    result = {
        "pass": pass_name, "project": project, "variant": variant,
        "model_label": model_label(), "seconds": seconds,
        "findings": findings,
        "in_scope_defects": [d["id"] for d in in_scope] if variant == "defected" else [],
    }
    outdir = RESULTS / model_label()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{pass_name}_{project}_{variant}"
    (outdir / f"{stem}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"  [{model_label()}] {stem}: {len(findings)} findings in {seconds}s")
    for f in findings:
        print(f"      {f['doc']}: claimed {f['claimed']:g}, computed {f['computed']:g}  ({f['expression']})")
    if variant == "defected" and in_scope:
        print(f"      in-scope defects to catch: {[d['id'] for d in in_scope]}")
    return result


async def main() -> None:
    all_projects = [p for s in SETS.values() for p in s["projects"]]
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="pass_name", choices=list(PASSES), default="numeric")
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
