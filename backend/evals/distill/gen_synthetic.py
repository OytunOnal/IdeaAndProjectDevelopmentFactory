"""Phase 4 step 1 — synthetic training-data generation (LOCAL_MIGRATION_PLAN.md).

Produces the raw material for distillation: synthetic projects (brief + 5
spec docs, generated LOCALLY on the measured generator model), then
self-labeled defect variants — the model is asked to plant a defect of a
given class and return the planted quote, which code verifies against the
rewritten document. Ground truth comes free with generation.

Domains are deliberately disjoint from BOTH fixture sets (dev:
fintech-SaaS/logistics; held-out: minor-edtech/P2P-equipment) — training
data must never overlap the sets that judge it. Train/eval splits are made
by PROJECT, never by document.

Usage (from backend/, local models via env as usual):
    LLM_FORCE_PROVIDER=ollama OLLAMA_MODEL_QUALITY=qwen3.6:35b OLLAMA_MODEL_FAST=qwen3:8b \
        python -m evals.distill.gen_synthetic --projects 3 --defects-per-project 4
"""

import argparse
import asyncio
import json
import random
import re
import time
from pathlib import Path

from app.agents.common import brief_context, docs_context
from app.agents.llm import call_llm
from app.agents.specification import SPEC_AGENTS

DATA = Path(__file__).parent / "data"

SPEC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")

# 20 seed domains, disjoint from dev (fintech-SaaS, logistics-SaaS) and
# held-out (consumer-edtech/minors, P2P equipment marketplace).
SEED_IDEAS = [
    ("plantpulse", "IoT-free houseplant care tracker: photo-based health checks and watering schedules for plant owners"),
    ("crewshift", "shift scheduling for small restaurants: swap requests, availability, and labor-cost view for owners"),
    ("briefbox", "a tool for freelance designers to collect structured creative briefs from clients before a project starts"),
    ("courtly", "amateur sports league organizer: fixtures, standings, and venue booking for local leagues"),
    ("mendhub", "repair-shop management for independent phone/laptop repair shops: intake, status tracking, customer notifications"),
    ("tastetrail", "a city food-discovery app built around resident-curated tasting routes instead of reviews"),
    ("chorusdesk", "choir and amateur orchestra management: sheet music distribution, attendance, part assignments"),
    ("packlight", "trip packing assistant that generates packing lists from destination weather and trip type"),
    ("vetvisit", "mobile vet appointment booking for pet owners with vaccination records and reminders"),
    ("solarsizer", "rooftop solar estimation for homeowners: roof photo + bill → system size and payback estimate"),
    ("draftmate", "contract first-draft assistant for freelancers: templates with guided clause choices, no legal advice"),
    ("queuecast", "virtual queue system for barbershops and salons: walk-in tickets, live wait estimates"),
    ("groundskeep", "maintenance scheduling for community gardens: plots, shared tools, volunteer shifts"),
    ("recitehall", "practice-tracking app for adult music students with teacher feedback loops"),
    ("floatplan", "small-marina slip management: berth assignments, billing, waitlists"),
    ("bakebatch", "production planning for home bakeries: orders, batch schedules, ingredient purchasing"),
    ("wardwatch", "hospital visitor coordination: visit slots, updates for family members, no medical data"),
    ("stagehand", "tech-rider and stage-plot builder for small touring bands and venues"),
    ("tutorledger", "invoicing and session tracking for private tutors of adult learners"),
    ("hikeherd", "group-hike organization: difficulty-matched groups, checkpoints, emergency contacts"),
]

DEFECT_TYPES = {
    "internal-contradiction": "State something in one place and clearly contradict it elsewhere in the SAME document (e.g. a limit that another section says doesn't exist).",
    "arithmetic-error": "Change ONE number so a stated computation no longer follows from its own inputs (e.g. an LTV, ratio, retention, or break-even figure that contradicts the stated inputs).",
    "fabricated-evidence": "Insert a first-party empirical claim that nothing supports — a pilot/beta/test that supposedly ALREADY produced specific results, while the plans show it hasn't happened.",
    "absurd-target": "Replace a sane target with one that is impossible at the stated resources/timeline (keep the wording confident and matter-of-fact).",
    "audience-mismatch": "Insert a design/interface choice that directly contradicts the document's own stated audience.",
    "infeasible-plan": "Replace the team/timeline plan with one that cannot deliver the stated scope (drastically undersized team or timeline).",
    "infeasible-tech": "Insert a technical component that cannot work as described or is wildly disproportionate to the product.",
}

# Which docs each defect type can be planted into (mirrors the fixture sets).
DEFECT_TARGET_DOCS = {
    "internal-contradiction": ("prd", "architecture", "financial_model"),
    "arithmetic-error": ("financial_model",),
    "fabricated-evidence": ("gtm_strategy",),
    "absurd-target": ("gtm_strategy", "prd"),
    "audience-mismatch": ("ux_design",),
    "infeasible-plan": ("architecture",),
    "infeasible-tech": ("architecture",),
}

_PLANT_PROMPT = """You are a defect-seeding tool for an evaluation dataset. Rewrite the document below, planting EXACTLY ONE defect of this class:

{defect_desc}

Rules:
- Change as LITTLE as possible — ideally one sentence inserted or one sentence/number replaced. Everything else stays byte-identical.
- The defect must be substantive (a reviewer should flag it), but written in the document's confident tone — no winking.
- Return ONLY a fenced JSON object with the FULL rewritten document and the planted sentence copied VERBATIM from it:

```json
{{"document": "<full rewritten document>", "planted_quote": "<the flawed sentence exactly as it appears in the document>", "note": "<one line: what makes it a defect>"}}
```"""


def _parse_plant(reply: str) -> dict | None:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", reply, re.DOTALL)
    text = m.group(1) if m else reply
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    doc, quote = data.get("document"), data.get("planted_quote")
    if not doc or not quote or not isinstance(doc, str) or not isinstance(quote, str):
        return None
    return data


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*`_#:;|•–—-]", "", text)).strip()


async def gen_brief(name: str, idea: str) -> dict:
    reply = await call_llm(
        messages=[{
            "role": "user",
            "content": (
                "Create a confirmed idea brief for this product concept as a fenced "
                "JSON object with keys: problem_statement, value_proposition, "
                "target_users (list of {type, priority}), core_features (list of 3), "
                f"revenue_model, domain_category.\n\nConcept: {idea}"
            ),
        }],
        model_tier=2, temperature=0.6, max_tokens=1024, role="audit", think=False,
    )
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", reply, re.DOTALL)
    try:
        brief = json.loads(m.group(1) if m else reply)
    except json.JSONDecodeError:
        brief = {"problem_statement": idea, "value_proposition": idea,
                 "target_users": [], "core_features": [], "revenue_model": "",
                 "domain_category": "synthetic"}
    brief["confirmed"] = True
    return brief


async def gen_docs(name: str, brief: dict) -> dict[str, str]:
    """Generate the 5 spec docs with the production generator prompts (the
    measured local generator path — tier per SPEC_AGENTS, quality model)."""
    state: dict = {"project_name": name, "idea_brief": brief}
    docs: dict[str, str] = {}
    for agent_id, spec in SPEC_AGENTS.items():
        user_content = (
            f"{brief_context(state)}\n\n---\n\n{docs_context(state, spec['context'])}"
            f"\n\n---\n\nWrite the {spec['title']} for this project now."
        )
        doc = await call_llm(
            messages=[
                {"role": "system", "content": spec["prompt"]},
                {"role": "user", "content": user_content},
            ],
            model_tier=spec["tier"], temperature=0.6, max_tokens=8192, role="spec",
        )
        docs[spec["output_key"]] = doc
        state[spec["output_key"]] = doc
    return docs


async def plant_defect(doc_key: str, doc_text: str, defect_type: str) -> dict | None:
    """Ask the model to plant one defect; code-verify the planted quote."""
    reply = await call_llm(
        messages=[
            {"role": "system", "content": _PLANT_PROMPT.format(defect_desc=DEFECT_TYPES[defect_type])},
            {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
        ],
        model_tier=1, temperature=0.7, max_tokens=8192, role="audit",
    )
    data = _parse_plant(reply)
    if data is None:
        return None
    if _ws(data["planted_quote"]) not in _ws(data["document"]):
        return None  # self-label failed verification — discard
    # sanity: the rewrite must still resemble the original (no full rewrite)
    if len(data["document"]) < 0.6 * len(doc_text):
        return None
    return {"doc": doc_key, "type": defect_type,
            "document": data["document"], "planted_quote": data["planted_quote"],
            "note": data.get("note", "")}


async def build_project(name: str, idea: str, defects_per_project: int, rng: random.Random) -> None:
    outdir = DATA / "projects" / name
    if (outdir / "brief.json").exists():
        print(f"  [{name}] exists — skipped")
        return
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    brief = await gen_brief(name, idea)
    (outdir / "brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    docs = await gen_docs(name, brief)
    for key, text in docs.items():
        (outdir / f"{key}.md").write_text(text, encoding="utf-8")

    planted: list[dict] = []
    types = rng.sample(list(DEFECT_TYPES), k=min(defects_per_project, len(DEFECT_TYPES)))
    for defect_type in types:
        doc_key = rng.choice(DEFECT_TARGET_DOCS[defect_type])
        result = await plant_defect(doc_key, docs[doc_key], defect_type)
        if result is None:
            print(f"  [{name}] plant failed for {defect_type} — skipped")
            continue
        stem = f"defect_{defect_type}_{doc_key}"
        (outdir / f"{stem}.md").write_text(result["document"], encoding="utf-8")
        planted.append({k: result[k] for k in ("doc", "type", "planted_quote", "note")}
                       | {"file": f"{stem}.md"})
    (outdir / "defects.json").write_text(json.dumps(planted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [{name}] 5 docs + {len(planted)}/{len(types)} defects in {time.perf_counter() - t0:.0f}s")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", type=int, default=3, help="how many seed projects to build this run")
    ap.add_argument("--defects-per-project", type=int, default=4)
    ap.add_argument("--seed", type=int, default=41, help="rng seed (defect type/doc choices)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    todo = [s for s in SEED_IDEAS if not (DATA / "projects" / s[0] / "brief.json").exists()]
    todo = todo[: args.projects]
    print(f"building {len(todo)} synthetic project(s): {[n for n, _ in todo]}")
    for name, idea in todo:
        await build_project(name, idea, args.defects_per_project, rng)
    print("Done —", DATA / "projects")


if __name__ == "__main__":
    asyncio.run(main())
