"""Generator-role eval runner (Phase 2 of the local migration).

Fixed-context design: every model generates each spec document from the SAME
golden inputs (brief + research fixtures; the golden clean PRD/GTM serve as
inputs for downstream docs). This isolates per-role generation quality —
no chained error compounding across models.

Usage (from backend/, env selects the model as in defect_runner):
    MODEL_LABEL=frontier python -m evals.gen_runner
    LLM_FORCE_PROVIDER=ollama OLLAMA_MODEL_QUALITY=qwen3:8b OLLAMA_MODEL_FAST=qwen3:8b \
        OLLAMA_THINK=on MODEL_LABEL=qwen3-8b python -m evals.gen_runner
"""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path

from app.agents.common import brief_context, docs_context, prior_adjustments_blocklist
from app.agents.llm import call_llm
from app.agents.specification import SPEC_AGENTS
from app.config import settings
from evals.defect_runner import BRIEFS, PROJECTS

FIXTURES = Path(__file__).parent / "fixtures" / "seeded_defects"
RESULTS = Path(__file__).parent / "results" / "generators"

INPUT_KEYS = (
    "market_research", "competitor_analysis", "tech_feasibility",
    "prd", "gtm_strategy",  # golden clean docs as fixed inputs for downstream roles
)

# Structure contracts distilled from each generator prompt — code-checkable.
REQUIRED_HEADINGS = {
    "prd": ["vision", "target users", "feature", "user stories", "mvp", "success metrics"],
    "architecture": ["overview", "api", "schema|database", "infrastructure"],
    "ux_design": ["flow", "screen", "design system", "interaction"],
    "gtm_strategy": ["launch", "channel|acquisition", "1000|1,000", "content|partnership"],
    "financial_model": ["revenue|pricing", "projection", "unit economics", "break-even|break even", "funding", "sensitivity"],
}


def structure_score(doc_key: str, text: str) -> dict:
    lower = text.lower()
    required = REQUIRED_HEADINGS[doc_key]
    found = [pat for pat in required if re.search(pat, lower)]
    return {
        "headings_found": len(found),
        "headings_required": len(required),
        "missing": [p for p in required if p not in found],
        "words": len(text.split()),
        "has_mermaid": "```mermaid" in lower,
    }


def build_state(project: str) -> dict:
    state: dict = {
        "project_name": project,
        "idea_brief": BRIEFS[project],
    }
    for key in INPUT_KEYS:
        path = FIXTURES / project / f"{key}.md"
        if path.exists():
            state[key] = path.read_text(encoding="utf-8")
    return state


def model_label() -> str:
    if os.environ.get("MODEL_LABEL"):
        return os.environ["MODEL_LABEL"]
    if settings.llm_force_provider == "ollama":
        return settings.ollama_model_fast.replace(":", "-")
    return "frontier"


async def generate_one(project: str, agent_id: str) -> None:
    spec = SPEC_AGENTS[agent_id]
    doc_key = spec["output_key"]
    state = build_state(project)
    user_content = (
        f"{brief_context(state)}\n\n---\n\n{docs_context(state, spec['context'])}\n\n---\n\n"
        f"Write the {spec['title']} for this project now."
        + prior_adjustments_blocklist(state)
    )
    t0 = time.perf_counter()
    try:
        document = await call_llm(
            messages=[
                {"role": "system", "content": spec["prompt"]},
                {"role": "user", "content": user_content},
            ],
            model_tier=spec["tier"],
            temperature=0.5,
            max_tokens=int(os.environ.get("GEN_MAX_TOKENS", "8192")),  # mirrors production (specification.py)
        )
        error = None
    except Exception as exc:
        document, error = "", f"{type(exc).__name__}: {exc}"
    seconds = round(time.perf_counter() - t0, 1)

    outdir = RESULTS / model_label()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{project}_{doc_key}"
    (outdir / f"{stem}.md").write_text(document or "(EMPTY)", encoding="utf-8")
    meta = {
        "project": project, "doc": doc_key, "model_label": model_label(),
        "tier": spec["tier"], "seconds": seconds, "chars": len(document),
        "error": error, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "structure": structure_score(doc_key, document) if document else None,
    }
    (outdir / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    s = meta["structure"]
    shape = f"{s['headings_found']}/{s['headings_required']} headings, {s['words']}w" if s else "EMPTY"
    print(f"  [{model_label()}] {stem}: {shape} in {seconds}s" + (f"  ERROR: {error}" if error else ""))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", choices=[*PROJECTS, "both"], default="both")
    ap.add_argument("--agent", choices=[*SPEC_AGENTS, "all"], default="all")
    args = ap.parse_args()
    projects = PROJECTS if args.project == "both" else (args.project,)
    agents = list(SPEC_AGENTS) if args.agent == "all" else [args.agent]
    runs = [(p, a) for p in projects for a in agents]
    print(f"model={model_label()}  generations={len(runs)}")
    for p, a in runs:
        await generate_one(p, a)
    print("Done —", RESULTS / model_label())


if __name__ == "__main__":
    asyncio.run(main())
