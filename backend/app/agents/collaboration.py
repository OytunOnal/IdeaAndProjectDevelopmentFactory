"""Per-document collaboration nodes: approval gates, revisions, improvement.

These nodes implement the review workflow between agents and the user:
- doc_gate: pause after each produced document for approval
- revise_document: rewrite a document based on the user's feedback
- spec_improver: apply the quality reviewer's gap list across the spec docs
"""

import logging

from app.agents.common import (
    DOC_PATHS,
    DOC_TITLES,
    agent_message,
    brief_context,
    doc_gate_card,
    docs_context,
    emit_progress,
    extract_adjustments,
    get_doc,
)
from app.agents.llm import call_llm
from app.agents.research import _AGENTS as RESEARCH_AGENTS
from app.agents.specification import SPEC_AGENTS
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)


def _find_agent(key: str) -> dict | None:
    """Locate the producing agent's spec (prompt/title/emoji) by output key."""
    for agents in (RESEARCH_AGENTS, SPEC_AGENTS):
        for spec in agents.values():
            if spec["output_key"] == key:
                return spec
    return None


async def doc_gate_node(state: ProjectState) -> ProjectState:
    """Present the approval card for the first unapproved document."""
    approved = state.get("approved_docs") or []
    for key in (
        "market_research", "competitor_analysis", "tech_feasibility",
        "prd", "architecture", "ux_design", "gtm_strategy", "financial_model",
    ):
        doc = get_doc(state, key)
        if doc and key not in approved:
            return {
                **state,
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": doc_gate_card(key, bool(extract_adjustments(doc))),
            }

    # Nothing to gate (shouldn't happen) — just continue
    return state


async def revise_document_node(state: ProjectState) -> ProjectState:
    """Rewrite one document according to the user's change request."""
    key = state.get("revision_target")
    spec = _find_agent(key) if key else None
    if not key or not spec:
        return {**state, "revision_target": None, "revision_feedback": None}

    # Feedback comes from the decision card's freeform input, or from the
    # user's follow-up chat message.
    feedback = state.get("revision_feedback")
    if not feedback:
        messages = state.get("messages", [])
        if messages and messages[-1].get("role") == "user":
            feedback = messages[-1]["content"]
    if not feedback:
        return {**state, "pipeline_status": "waiting_for_user"}

    title = DOC_TITLES.get(key, key)
    await emit_progress(
        state, "orchestrator", f"✏️ Revising the {title} based on your feedback..."
    )

    previous = get_doc(state, key) or ""
    context = brief_context(state)

    revision_prompt = (
        spec["prompt"]
        + "\n\nREVISION MODE: The user reviewed your previous version and "
        "requested changes. Rewrite the FULL document applying their feedback. "
        "Do not refuse or say it cannot be done — if the request involves "
        "trade-offs, apply the most viable interpretation and note the "
        "trade-off briefly at the top. Keep everything that was good."
    )
    user_content = (
        f"{context}\n\n---\n\nYOUR PREVIOUS VERSION:\n\n{previous[:12000]}\n\n---\n\n"
        f"USER'S CHANGE REQUEST:\n{feedback}\n\n"
        f"Rewrite the {title} now, applying the request."
    )

    try:
        document = await call_llm(
            messages=[
                {"role": "system", "content": revision_prompt},
                {"role": "user", "content": user_content},
            ],
            model_tier=spec.get("tier", 2),
            api_key=state.get("api_key"),
            temperature=0.5,
            max_tokens=6144,
        )
    except Exception as e:
        logger.error(f"Revision of {key} failed: {e}", exc_info=True)
        return {
            **state,
            "messages": agent_message(
                state, "orchestrator",
                f"✏️ Revision failed: {e}. Send your feedback again to retry.",
            ),
            "pipeline_status": "waiting_for_user",
        }

    # Research docs are dicts; keep their structure, mark as no longer grounded-checked
    old_value = state.get(key)
    if isinstance(old_value, dict):
        new_value = {**old_value, "report": document, "revised": True}
    else:
        new_value = document

    # A revision during the quality phase invalidates the score — re-review
    # once the user approves the revised document.
    quality_reset = {}
    if state.get("current_phase") == "quality":
        quality_reset = {"quality_feedback": None, "quality_review_done": False}

    return {
        **state,
        **quality_reset,
        key: new_value,
        "revision_target": None,
        "revision_feedback": None,
        "messages": agent_message(
            state, "orchestrator",
            f"✏️ **{title} revised** — updated in the files panel "
            f"(`{DOC_PATHS.get(key, key)}`). Take another look.",
        ),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "pending_decision": doc_gate_card(key, bool(extract_adjustments(document))),
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def spec_improver_node(state: ProjectState) -> ProjectState:
    """Apply the quality reviewer's fixes to the affected spec documents.

    Only documents named in the fix list (or the user's explicit targets) are
    rewritten — rewriting healthy documents risks regressing them.
    """
    gaps = state.get("quality_feedback") or ""
    top_fixes = state.get("quality_top_fixes") or []
    if top_fixes:
        gaps = (
            "HIGHEST-IMPACT FIXES (address these first):\n"
            + "\n".join(f"- {f}" for f in top_fixes)
            + "\n\n" + gaps
        )
    focus = state.get("quality_improve_focus")
    if focus:
        gaps = f"USER'S PRIORITY (address this above all else): {focus}\n\n{gaps}"

    # Which documents to touch: explicit targets > fix prefixes > all
    spec_keys = [s["output_key"] for s in SPEC_AGENTS.values()]
    targets = [t for t in (state.get("quality_improve_targets") or []) if t in spec_keys]
    if not targets:
        targets = [k for k in spec_keys
                   if any(f.strip().lower().startswith(f"{k}:") for f in top_fixes)]
    if not targets:
        targets = spec_keys
    improved = []

    for agent_id, spec in SPEC_AGENTS.items():
        key = spec["output_key"]
        if key not in targets:
            continue
        previous = get_doc(state, key)
        if not previous:
            continue

        title = spec["title"]
        await emit_progress(
            state, agent_id, f"🔧 Improving the {title} using the quality review..."
        )

        context = brief_context(state)
        research = docs_context(
            state, ["market_research", "competitor_analysis", "tech_feasibility"],
            max_chars=2000,
        )
        user_content = (
            f"{context}\n\n---\n\n{research}\n\n---\n\n"
            f"YOUR PREVIOUS VERSION:\n\n{previous[:10000]}\n\n---\n\n"
            f"QUALITY REVIEW FINDINGS (address every gap relevant to this document):\n"
            f"{gaps[:4000]}\n\n"
            f"Rewrite the {title}, fixing the relevant gaps. Keep what was good."
        )

        try:
            document = await call_llm(
                messages=[
                    {"role": "system", "content": spec["prompt"]},
                    {"role": "user", "content": user_content},
                ],
                model_tier=spec.get("tier", 2),
                api_key=state.get("api_key"),
                temperature=0.4,
                max_tokens=6144,
            )
            state = {**state, key: document}
            improved.append(title)
        except Exception as e:
            logger.error(f"Improvement of {key} failed: {e}")

    return {
        **state,
        # Clear the review so the quality phase re-scores the improved docs
        "quality_improve_requested": False,
        "quality_improve_focus": None,
        "quality_improve_targets": [],
        "quality_feedback": None,
        "quality_review_done": False,
        "messages": agent_message(
            state, "orchestrator",
            "🔧 **Improvement pass complete** — updated: "
            + (", ".join(improved) if improved else "nothing (all improvements failed)")
            + ". Re-scoring now...",
        ),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + len(improved),
    }
