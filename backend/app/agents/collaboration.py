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
    consume_adjustments,
    current_gate_card,
    doc_gate_card,
    docs_context,
    emit_progress,
    extract_adjustments,
    get_doc,
)
from app.agents.llm import call_llm
from app.agents.quality import CONSISTENCY_PROMPT, DEVILS_ADVOCATE_PROMPT
from app.agents.research import _AGENTS as RESEARCH_AGENTS
from app.agents.specification import SPEC_AGENTS
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)

# Quality reports are revisable documents too ("Request changes" on their gates)
_QUALITY_REPORTS = {
    "devils_advocate": {
        "prompt": DEVILS_ADVOCATE_PROMPT,
        "output_key": "devils_advocate",
        "title": "Devil's Advocate Report",
        "emoji": "😈",
        "tier": 2,
    },
    "consistency_report": {
        "prompt": CONSISTENCY_PROMPT,
        "output_key": "consistency_report",
        "title": "Consistency Report",
        "emoji": "🧩",
        "tier": 2,
    },
}


def _find_agent(key: str) -> dict | None:
    """Locate the producing agent's spec (prompt/title/emoji) by output key."""
    from app.agents.packaging import PLANNING_PROMPT  # local import: avoids cycle

    packaging_docs = {
        "planning_agent": {
            "prompt": PLANNING_PROMPT,
            "output_key": "implementation_roadmap",
            "title": "Implementation Roadmap",
            "emoji": "🗺️",
            "tier": 2,
        },
    }
    for agents in (RESEARCH_AGENTS, SPEC_AGENTS, _QUALITY_REPORTS, packaging_docs):
        for spec in agents.values():
            if spec["output_key"] == key:
                return spec
    return None


async def doc_gate_node(state: ProjectState) -> ProjectState:
    """Present the approval card for the document currently awaiting review."""
    card = current_gate_card(state)
    if card:
        return {
            **state,
            "current_agent": "orchestrator",
            "pipeline_status": "running",
            "pending_decision": card,
        }

    # No gate to present (defensive) — pause rather than loop the router
    return {**state, "pipeline_status": "waiting_for_user"}


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

    # Applied adjustments are consumed — otherwise the mandatory-section rule
    # makes the model re-propose the same items and the gate loops forever.
    if state.get("revision_is_apply"):
        document = consume_adjustments(document)

    # Research docs are dicts; keep their structure, mark as no longer grounded-checked
    old_value = state.get(key)
    if isinstance(old_value, dict):
        new_value = {**old_value, "report": document, "revised": True}
    else:
        new_value = document

    # A revision during the quality phase invalidates the score — re-review
    # once the user approves the revised document. If a SPEC document changed,
    # the consistency report is stale too: re-run it (through its gate).
    quality_reset = {}
    if state.get("current_phase") == "quality":
        quality_reset = {"quality_feedback": None, "quality_review_done": False}
        spec_keys = [s["output_key"] for s in SPEC_AGENTS.values()]
        if key in spec_keys:
            quality_reset["consistency_report"] = None
            quality_reset["approved_docs"] = [
                k for k in (state.get("approved_docs") or [])
                if k != "consistency_report"
            ]

    base = {
        **state,
        **quality_reset,
        key: new_value,
        "revision_target": None,
        "revision_feedback": None,
        "revision_is_apply": False,
        "revision_then": None,
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }

    # "Apply & continue": approve the revised document and keep moving —
    # no extra review round.
    if state.get("revision_then") == "continue":
        approved = list(state.get("approved_docs") or [])
        if key not in approved:
            approved.append(key)
        return {
            **base,
            "approved_docs": approved,
            "messages": agent_message(
                state, "orchestrator",
                f"✏️ **{title} revised and approved** — adjustments applied "
                f"(`{DOC_PATHS.get(key, key)}`). Moving on.",
            ),
            "pending_decision": None,
        }

    return {
        **base,
        "messages": agent_message(
            state, "orchestrator",
            f"✏️ **{title} revised** — updated in the files panel "
            f"(`{DOC_PATHS.get(key, key)}`). Take another look.",
        ),
        "pending_decision": doc_gate_card(key, bool(extract_adjustments(document))),
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
    # This pass consumes the reports' recommendations and the top fixes —
    # record them so re-runs don't re-propose what is being applied.
    applied = list(state.get("applied_adjustments") or [])
    for report_key in ("devils_advocate", "consistency_report"):
        adj = extract_adjustments(get_doc(state, report_key))
        if adj:
            entry = f"From {DOC_TITLES.get(report_key, report_key)}:\n{adj}"
            if entry not in applied:
                applied.append(entry)
    if top_fixes:
        entry = "From Quality Review (top fixes):\n" + "\n".join(f"- {f}" for f in top_fixes)
        if entry not in applied:
            applied.append(entry)

    # The Devil's Advocate mitigations and consistency findings are part of
    # the improvement input too — they used to be produced and then ignored.
    devils = get_doc(state, "devils_advocate")
    if devils:
        gaps += (
            "\n\nDEVIL'S ADVOCATE — RISKS & MITIGATIONS (address the "
            "mitigations relevant to your document):\n" + devils[:2500]
        )
    consistency = get_doc(state, "consistency_report")
    if consistency:
        gaps += (
            "\n\nCONSISTENCY FINDINGS (fix the mismatches that involve your "
            "document):\n" + consistency[:2000]
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
            f"YOUR PREVIOUS VERSION:\n\n{previous[:14000]}\n\n---\n\n"
            f"QUALITY REVIEW FINDINGS (address every gap relevant to this document):\n"
            f"{gaps[:4000]}\n\n"
            f"IMPORTANT: this is a TARGETED improvement, not a from-scratch "
            f"rewrite. Preserve every existing section and all of its detail — "
            f"only fix and add what the findings require. The improved document "
            f"must not be shorter than the previous version. "
            f"Improve the {title} now."
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
                max_tokens=8192,
            )
            # Regression guard: a rewrite that lost a big chunk of the document
            # (truncated output, dropped sections) must not replace the original —
            # that's how a 94-score package degraded to 65.
            if len(document) < 0.6 * len(previous):
                logger.warning(
                    f"Improvement of {key} rejected: output {len(document)} chars "
                    f"vs previous {len(previous)} — looks truncated"
                )
                improved.append(f"{title} (skipped — output looked truncated)")
                continue
            state = {**state, key: document}
            improved.append(title)
        except Exception as e:
            logger.error(f"Improvement of {key} failed: {e}")

    # The specs changed, so downstream quality steps are stale: consistency
    # re-checks the updated documents (through its own gate), then the
    # reviewer re-scores. This keeps the phase step-by-step instead of
    # jumping straight to the final gate on old approvals.
    approved_after = [
        k for k in (state.get("approved_docs") or []) if k != "consistency_report"
    ]

    # "Apply & re-run this check": regenerate the requesting report against
    # the updated specs so the user stays at that step with a fresh analysis.
    rerun_report = state.get("quality_rerun_report")
    rerun_reset = {rerun_report: None} if rerun_report else {}
    next_note = (
        "The Devil's Advocate will re-check the updated specs next."
        if rerun_report == "devils_advocate"
        else "Consistency will re-check the updated specs next."
    )

    return {
        **state,
        **rerun_reset,
        "quality_improve_requested": False,
        "quality_improve_focus": None,
        "quality_improve_targets": [],
        "quality_top_fixes": [],
        "quality_feedback": None,
        "quality_review_done": False,
        "quality_rerun_report": None,
        "consistency_report": None,
        "approved_docs": approved_after,
        "messages": agent_message(
            state, "orchestrator",
            "🔧 **Improvement pass complete** — updated: "
            + (", ".join(improved) if improved else "nothing (all improvements failed)")
            + f". {next_note}",
        ),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + len(improved),
    }
