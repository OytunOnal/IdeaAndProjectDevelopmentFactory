"""Seeded-defect eval runner for the Devil's Advocate and consistency checker.

Loads a golden project's CLEAN spec docs, optionally applies the defect
patches from the manifest (DEFECTED variant), runs the real agent node, and
saves the generated report for judging (see fixtures/seeded_defects/JUDGING.md).

Usage (from backend/, with LLM_FORCE_PROVIDER etc. set as desired):
    python -m evals.defect_runner                        # everything
    python -m evals.defect_runner --project invoicefox --variant defected --agent da
    MODEL_LABEL=qwen3-8b-thinkon python -m evals.defect_runner
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import yaml

from app.agents.quality import consistency_checker_node, devils_advocate_node
from app.config import settings

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
FIXTURES = FIXTURES_ROOT / "seeded_defects"  # dev set (back-compat alias)
RESULTS = Path(__file__).parent / "results" / "defects"

SPEC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")
PROJECTS = ("invoicefox", "fleetsense")  # dev set (back-compat alias)

# The held-out set is SEALED — see fixtures/heldout_defects/HELDOUT.md before
# running with --set heldout, and log the exposure there.
SETS = {
    "dev": {"dir": "seeded_defects", "projects": ("invoicefox", "fleetsense")},
    "heldout": {"dir": "heldout_defects", "projects": ("prepnest", "kilnshare")},
}

BRIEFS = {
    "invoicefox": {
        "confirmed": True,
        "problem_statement": "Freelancers lose income to late or unpaid invoices.",
        "value_proposition": "A polite, automated invoice-chasing assistant.",
        "target_users": [{"type": "solo freelancers", "priority": "primary"}],
        "core_features": ["invoice tracking", "automated reminders", "Stripe links"],
        "revenue_model": "freemium subscription",
        "domain_category": "fintech-saas",
    },
    "fleetsense": {
        "confirmed": True,
        "problem_statement": "Small delivery fleets plan routes by hand and lose driver-hours daily.",
        "value_proposition": "Affordable route optimization with live tracking for 5-50 van fleets.",
        "target_users": [{"type": "dispatchers", "priority": "primary"}],
        "core_features": ["route optimization", "live map", "driver app"],
        "revenue_model": "per-van subscription",
        "domain_category": "logistics-saas",
    },
    "prepnest": {
        "confirmed": True,
        "problem_statement": "High-schoolers prepping for entrance exams get stuck on single concepts; hourly tutoring is unaffordable.",
        "value_proposition": "15-minute on-demand micro-tutoring video sessions with vetted university-student tutors.",
        "target_users": [
            {"type": "high-school students (minors)", "priority": "primary"},
            {"type": "parents (payer)", "priority": "secondary"},
        ],
        "core_features": ["stuck-concept booking", "micro video sessions", "question bank + parent digest"],
        "revenue_model": "freemium subscription",
        "domain_category": "consumer-edtech",
    },
    "kilnshare": {
        "confirmed": True,
        "problem_statement": "Hobbyist makers can't justify owning expensive workshop equipment that sits idle at owners' homes 90% of the time.",
        "value_proposition": "Safety-gated P2P marketplace for renting kilns, laser cutters, and 3D printers with escrow and damage protection.",
        "target_users": [
            {"type": "hobbyist makers (renters)", "priority": "primary"},
            {"type": "equipment owners", "priority": "secondary"},
        ],
        "core_features": ["listings + booking", "escrow payments + deposits", "safety certification gate"],
        "revenue_model": "commission (15% take rate)",
        "domain_category": "p2p-marketplace",
    },
}


def load_bundle(project: str, variant: str, manifest: list[dict], fixtures: Path = FIXTURES) -> dict[str, str]:
    docs = {
        key: (fixtures / project / f"{key}.md").read_text(encoding="utf-8")
        for key in SPEC_KEYS
    }
    if variant == "defected":
        for defect in (d for d in manifest if d["project"] == project):
            doc, find = defect["doc"], defect["patch"]["find"]
            count = docs[doc].count(find)
            if count != 1:
                raise SystemExit(
                    f"Fixture drift: patch {defect['id']} matches {count}x in {project}/{doc}"
                )
            docs[doc] = docs[doc].replace(find, defect["patch"]["replace"])
    return docs


def build_state(project: str, docs: dict[str, str]) -> dict:
    return {
        "current_phase": "quality",
        "pipeline_status": "running",
        "project_name": project,
        "idea_brief": BRIEFS[project],
        "approved_docs": list(SPEC_KEYS),
        "messages": [],
        **docs,
    }


def model_label() -> str:
    if os.environ.get("MODEL_LABEL"):
        return os.environ["MODEL_LABEL"]
    if settings.llm_force_provider == "ollama":
        think = settings.ollama_think or "auto"
        return f"{settings.ollama_model_fast.replace(':', '-')}_think-{think}"
    return "frontier"


async def run_one(project: str, variant: str, agent: str, manifest: list[dict], fixtures: Path = FIXTURES) -> None:
    node = devils_advocate_node if agent == "da" else consistency_checker_node
    out_key = "devils_advocate" if agent == "da" else "consistency_report"

    state = build_state(project, load_bundle(project, variant, manifest, fixtures))
    t0 = time.perf_counter()
    result = await node(state)
    seconds = round(time.perf_counter() - t0, 1)

    value = result.get(out_key)
    report = value.get("report") if isinstance(value, dict) else (value or "")

    outdir = RESULTS / model_label()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{project}_{variant}_{agent}"
    (outdir / f"{stem}.md").write_text(report or "(EMPTY REPORT)", encoding="utf-8")
    (outdir / f"{stem}.meta.json").write_text(json.dumps({
        "project": project, "variant": variant, "agent": agent,
        "model_label": model_label(), "seconds": seconds,
        "report_chars": len(report or ""),
        "defect_ids": [d["id"] for d in manifest if d["project"] == project] if variant == "defected" else [],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2), encoding="utf-8")
    print(f"  [{model_label()}] {stem}: {len(report or '')} chars in {seconds}s")


async def main() -> None:
    all_projects = [p for s in SETS.values() for p in s["projects"]]
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="dev",
                    help="heldout is SEALED — read fixtures/heldout_defects/HELDOUT.md first")
    ap.add_argument("--project", choices=[*all_projects, "both"], default="both")
    ap.add_argument("--variant", choices=["clean", "defected", "both"], default="both")
    ap.add_argument("--agent", choices=["da", "consistency", "both"], default="both")
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
    agents = ("da", "consistency") if args.agent == "both" else (args.agent,)

    runs = [(p, v, a) for p in projects for v in variants for a in agents]
    print(f"set={args.set}  model={model_label()}  runs={len(runs)}")
    for p, v, a in runs:
        await run_one(p, v, a, manifest, fixtures)
    print("Done — reports under", RESULTS / model_label())


if __name__ == "__main__":
    asyncio.run(main())
