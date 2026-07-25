"""Packaging-phase agents: implementation roadmap + final document set."""

import logging

from app.agents.common import (
    DOC_TITLES,
    agent_message,
    docs_context,
    emit_progress,
    get_doc,
)
from app.agents.llm import call_llm
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)


PLANNING_PROMPT = """You are the Planning Agent of ProjectFactory. You turn the specifications into an actionable implementation plan.

Produce a development roadmap in markdown covering:

1. **Phased Roadmap** — MVP → v1.0 → v1.1 with milestones, deliverables, and timeline estimates.
2. **MVP Sprint Plan** — 2-week sprints with goals and the user stories assigned to each.
3. **Resources** — solo-developer timeline vs small-team timeline; required tools/services with rough monthly cost.
4. **Risk-Adjusted Timeline** — optimistic/expected/pessimistic, informed by the Devil's Advocate risks.

Be concrete: name the stories, name the tools, give week numbers. Max ~900 words."""


async def planning_agent_node(state: ProjectState) -> ProjectState:
    await emit_progress(state, "planning_agent", "🗺️ Building the implementation roadmap...")
    docs = docs_context(
        state,
        ["prd", "architecture", "tech_feasibility", "devils_advocate"],
        max_chars=3500,
    )

    try:
        roadmap = await call_llm(
            messages=[
                {"role": "system", "content": PLANNING_PROMPT},
                {"role": "user", "content": docs + "\n\nWrite the development roadmap now."},
            ],
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.4,
            max_tokens=4096,
        )
    except Exception as e:
        logger.error(f"planning_agent failed: {e}", exc_info=True)
        return {
            **state,
            "messages": agent_message(
                state, "planning_agent",
                f"🗺️ Roadmap generation failed: {e}. Send any message to retry.",
            ),
            "pipeline_status": "waiting_for_user",
            "current_agent": "planning_agent",
        }

    return {
        **state,
        "implementation_roadmap": roadmap,
        "messages": agent_message(
            state, "planning_agent", f"🗺️ **Implementation Roadmap**\n\n{roadmap}"
        ),
        "current_agent": "planning_agent",
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


# filename → state key for the final document set
FILE_MAP = {
    "01_RESEARCH/market_research.md": "market_research",
    "01_RESEARCH/competitor_analysis.md": "competitor_analysis",
    "01_RESEARCH/tech_feasibility.md": "tech_feasibility",
    "02_PRODUCT/prd.md": "prd",
    "03_DESIGN/ux_specification.md": "ux_design",
    "04_TECH/architecture.md": "architecture",
    "05_PLANNING/gtm_strategy.md": "gtm_strategy",
    "05_PLANNING/financial_model.md": "financial_model",
    "05_PLANNING/development_roadmap.md": "implementation_roadmap",
    "06_QUALITY/quality_review.md": "quality_feedback",
    "06_QUALITY/devils_advocate.md": "devils_advocate",
    "06_QUALITY/consistency_report.md": "consistency_report",
}


async def doc_formatter_node(state: ProjectState) -> ProjectState:
    """Assemble all produced documents into the final file set (no LLM needed)."""
    await emit_progress(state, "doc_formatter", "📦 Assembling the final document set...")

    files: dict[str, str] = {}
    for path, key in FILE_MAP.items():
        doc = get_doc(state, key)
        if not doc:
            continue
        content = f"# {DOC_TITLES.get(key, key)}\n\n{doc}\n"
        # Research documents carry their cited sources
        value = state.get(key)
        if isinstance(value, dict) and value.get("sources"):
            sources = "\n".join(f"- {u}" for u in value["sources"])
            content += f"\n---\n\n## Sources\n\n{sources}\n"
        files[path] = content

    files["INDEX.md"] = _build_index(state, files)

    score = state.get("quality_score")
    score_text = f"{score}/100" if score is not None else "n/a"

    return {
        **state,
        "project_files": files,
        "current_phase": "completed",
        "messages": agent_message(
            state, "doc_formatter",
            f"📦 **Project packaged!** {len(files)} documents generated "
            f"(quality score: {score_text}).\n\n"
            + "\n".join(f"- `{p}`" for p in sorted(files)),
        ),
        "current_agent": "doc_formatter",
        "pipeline_status": "waiting_for_user",
        "pending_decision": None,
    }


def _build_index(state: ProjectState, files: dict[str, str]) -> str:
    brief = state.get("idea_brief", {})
    score = state.get("quality_score")
    listing = "\n".join(f"- [{p}]({p})" for p in sorted(files) if p != "INDEX.md")

    return (
        f"# {state.get('project_name', 'Project')}\n\n"
        f"> {brief.get('value_proposition', '')}\n\n"
        f"**Problem:** {brief.get('problem_statement', '—')}\n\n"
        f"**Category:** {brief.get('domain_category', '—')} · "
        f"**Revenue model:** {brief.get('revenue_model', '—')} · "
        f"**Quality score:** {f'{score}/100' if score is not None else 'n/a'}\n\n"
        f"## Documents\n\n{listing}\n\n"
        "---\n\nGenerated by ProjectFactory — an AI multi-agent specification pipeline.\n"
    )
