"""Decision handler node - manages HITL (Human-in-the-Loop) decision points."""

import logging

from app.agents.common import (
    extract_adjustments,
    get_doc,
    record_applied_adjustments,
)
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)

# Approval cards that advance the pipeline to the next phase
PHASE_GATES = {
    "approve-research": {
        "next_phase": "specification",
        "flag": "research_approved",
        "user_text": "Research approved — continue!",
        "note": "✅ Research approved. Moving to the specification phase.",
    },
    "approve-spec": {
        "next_phase": "quality",
        "flag": None,
        "user_text": "Specifications approved — continue!",
        "note": "✅ Specifications approved. Starting the quality review.",
    },
    "approve-quality": {
        "next_phase": "packaging",
        "flag": None,
        "user_text": "Quality review approved — package it!",
        "note": "✅ Quality approved. Generating the roadmap and final documents.",
    },
}


async def decision_handler_node(state: ProjectState) -> ProjectState:
    """Handle a pending decision based on autonomy settings.

    If autonomy level is 'delegate' for the decision category,
    auto-resolve using the agent's recommendation.
    Otherwise, keep pipeline paused for user input.
    """

    pending = state.get("pending_decision")
    if not pending:
        return state

    category = pending.get("category", "strategic")
    autonomy = state.get("autonomy_level", {})
    level = autonomy.get(category, "ask")

    if level == "delegate":
        # Auto-resolve: use agent's recommendation
        recommendation = pending.get("agent_recommendation")
        reasoning = pending.get("agent_reasoning", "Auto-delegated by autonomy settings.")

        decision_record = {
            "id": pending["id"],
            "agent": pending.get("agent", "unknown"),
            "category": category,
            "question": pending.get("question", ""),
            "resolved_by": "agent",
            "chosen_option": recommendation,
            "reasoning": reasoning,
        }

        decisions = list(state.get("decisions", []))
        decisions.append(decision_record)

        # Add a system message about the auto-decision
        messages = list(state.get("messages", []))
        messages.append({
            "id": f"msg-decision-{len(messages)}",
            "role": "system",
            "content": f"Decision auto-delegated to agent: {pending.get('question', '')} → {recommendation}",
            "timestamp": "",
        })

        logger.info(f"Auto-delegated decision '{pending['id']}': {recommendation}")

        return {
            **state,
            "decisions": decisions,
            "messages": messages,
            "pending_decision": None,
            "pipeline_status": "running",
        }

    # For 'ask' or 'suggest': keep pipeline paused, user needs to respond
    # The pending_decision is already in state, frontend will render it
    return {
        **state,
        "pipeline_status": "waiting_for_user",
    }


def resolve_decision(state: ProjectState, submission: dict) -> ProjectState:
    """Process a user's decision submission and update state.

    Called from the API when user submits a decision.
    """

    pending = state.get("pending_decision")
    if not pending:
        return state

    action = submission.get("action", "choose")
    decisions = list(state.get("decisions", []))
    messages = list(state.get("messages", []))

    if action == "delegate":
        chosen = pending.get("agent_recommendation")
        resolved_by = "agent"
    elif action == "choose":
        chosen = submission.get("chosen_option")
        resolved_by = "user"
    elif action == "custom":
        chosen = submission.get("custom_input")
        resolved_by = "user"
    else:
        chosen = None
        resolved_by = "user"

    decision_record = {
        "id": pending["id"],
        "agent": pending.get("agent", "unknown"),
        "category": pending.get("category", "strategic"),
        "question": pending.get("question", ""),
        "resolved_by": resolved_by,
        "chosen_option": chosen,
    }
    decisions.append(decision_record)

    # Handle brief confirmation specifically
    if pending.get("id") == "confirm-brief" and chosen == "confirm":
        idea_brief = state.get("idea_brief", {})
        idea_brief["confirmed"] = True

        messages.append({
            "id": f"msg-user-{len(messages)}",
            "role": "user",
            "content": "Looks good, continue!",
            "timestamp": "",
        })

        return {
            **state,
            "idea_brief": idea_brief,
            "decisions": decisions,
            "messages": messages,
            "pending_decision": None,
            "pipeline_status": "running",
        }

    # Per-document approval cards ("approve-doc:<key>")
    pending_id = pending.get("id", "")
    if pending_id.startswith("approve-doc:"):
        doc_key = pending_id.split(":", 1)[1]

        if chosen == "confirm":
            approved = list(state.get("approved_docs") or [])
            if doc_key not in approved:
                approved.append(doc_key)
            messages.append({
                "id": f"msg-user-{len(messages)}",
                "role": "user",
                "content": "Approved — continue.",
                "timestamp": "",
            })
            return {
                **state,
                "approved_docs": approved,
                "decisions": decisions,
                "messages": messages,
                "pending_decision": None,
                "pipeline_status": "running",
            }

        if chosen in ("apply", "apply_review", "apply_recheck"):
            # Stale card safety: if the document carries no real adjustments
            # (e.g. "None — ..."), there is nothing to apply — approve instead
            # of forcing the model into a pointless rewrite.
            if not extract_adjustments(get_doc(state, doc_key) or ""):
                approved = list(state.get("approved_docs") or [])
                if doc_key not in approved:
                    approved.append(doc_key)
                messages.append({
                    "id": f"msg-agent-{len(messages)}",
                    "role": "agent",
                    "agent_id": "orchestrator",
                    "content": "This document has no pending adjustments to apply — approved as-is, moving on.",
                    "timestamp": "",
                })
                return {
                    **state,
                    "approved_docs": approved,
                    "decisions": decisions,
                    "messages": messages,
                    "pending_decision": None,
                    "pipeline_status": "running",
                }

            # Quality reports: their recommendations target the SPEC documents,
            # not the report itself — run an improvement pass instead of a
            # report rewrite, and approve the report.
            if doc_key in ("devils_advocate", "consistency_report"):
                titles = {
                    "devils_advocate": "Devil's Advocate report",
                    "consistency_report": "Consistency report",
                }
                recheck = chosen == "apply_recheck"
                approved = list(state.get("approved_docs") or [])
                # "Apply & re-run this check" keeps the step open: the report
                # is regenerated against the updated specs after the pass.
                if not recheck and doc_key not in approved:
                    approved.append(doc_key)
                messages.append({
                    "id": f"msg-user-{len(messages)}",
                    "role": "user",
                    "content": f"Apply the {titles[doc_key]}'s recommendations to the specs"
                    + (", then re-run the check." if recheck else "."),
                    "timestamp": "",
                })
                return {
                    **state,
                    "approved_docs": approved,
                    "quality_improve_requested": True,
                    "quality_improve_focus": (
                        f"Apply the recommended adjustments/mitigations from the "
                        f"{titles[doc_key]} to the affected documents."
                    ),
                    "quality_rerun_report": doc_key if recheck else None,
                    # Remember what was applied — the re-run must not re-propose it
                    "applied_adjustments": record_applied_adjustments(state, doc_key),
                    "decisions": decisions,
                    "messages": messages,
                    "pending_decision": None,
                    "pipeline_status": "running",
                }

            # Integrate all numbered recommendations into the document.
            # "apply" continues without another review round; "apply_review"
            # re-presents the gate with the revised document.
            messages.append({
                "id": f"msg-user-{len(messages)}",
                "role": "user",
                "content": "Apply the recommended adjustments"
                + (" and continue." if chosen == "apply" else ", then let me review."),
                "timestamp": "",
            })
            return {
                **state,
                "revision_target": doc_key,
                "revision_feedback": (
                    "Apply ALL the numbered items from your previous version's "
                    "'Recommended Adjustments' section: integrate them fully into "
                    "the project direction and rewrite the document accordingly."
                ),
                "revision_is_apply": True,
                "revision_then": "continue" if chosen == "apply" else "review",
                # Remember what was applied — later docs must not re-propose it
                "applied_adjustments": record_applied_adjustments(state, doc_key),
                "decisions": decisions,
                "messages": messages,
                "pending_decision": None,
                "pipeline_status": "running",
            }

        if submission.get("custom_input"):
            # Freeform text on the card goes to the discussion agent, which
            # decides the intent: revise, approve-and-continue, or answer a
            # question. (Blindly treating it as a change request caused
            # "noted, let's continue" to trigger a full rewrite.)
            messages.append({
                "id": f"msg-user-{len(messages)}",
                "role": "user",
                "content": submission["custom_input"],
                "timestamp": "",
            })
            return {
                **state,
                "decisions": decisions,
                "messages": messages,
                "pending_decision": None,
                "pipeline_status": "running",
            }

        # "Request changes" clicked without text → ask what to change
        messages.append({
            "id": f"msg-agent-{len(messages)}",
            "role": "agent",
            "agent_id": "orchestrator",
            "content": "What should be different? Describe the changes and the agent will rewrite the document.",
            "timestamp": "",
        })
        return {
            **state,
            "revision_target": doc_key,
            "decisions": decisions,
            "messages": messages,
            "pending_decision": None,
            "pipeline_status": "waiting_for_user",
        }

    # Quality gate: "improve" (or freeform guidance) runs a revision pass
    if pending_id == "approve-quality" and (
        chosen == "improve" or (action == "custom" and submission.get("custom_input"))
    ):
        focus = submission.get("custom_input") if action == "custom" else None
        messages.append({
            "id": f"msg-user-{len(messages)}",
            "role": "user",
            "content": focus or "Improve the specs using the quality review.",
            "timestamp": "",
        })
        return {
            **state,
            "quality_improve_requested": True,
            "quality_improve_focus": focus,
            "decisions": decisions,
            "messages": messages,
            "pending_decision": None,
            "pipeline_status": "running",
        }

    # Phase-gate approvals share the same mechanics
    if pending.get("id") in PHASE_GATES:
        gate = PHASE_GATES[pending["id"]]
        if chosen == "confirm":
            messages.append({
                "id": f"msg-user-{len(messages)}",
                "role": "user",
                "content": gate["user_text"],
                "timestamp": "",
            })
            messages.append({
                "id": f"msg-system-{len(messages)}",
                "role": "system",
                "content": gate["note"],
                "timestamp": "",
            })
            new_state = {
                **state,
                "current_phase": gate["next_phase"],
                "decisions": decisions,
                "messages": messages,
                "pending_decision": None,
                "pipeline_status": "running",
            }
            if gate.get("flag"):
                new_state[gate["flag"]] = True
            return new_state
        if chosen == "revise" and not submission.get("custom_input"):
            messages.append({
                "id": f"msg-agent-{len(messages)}",
                "role": "agent",
                "agent_id": "orchestrator",
                "content": "Sure — what would you like to know?",
                "timestamp": "",
            })
            return {
                **state,
                "decisions": decisions,
                "messages": messages,
                "pending_decision": None,
                "pipeline_status": "waiting_for_user",
            }
        # Freeform input → fall through: it becomes a user message and the
        # orchestrator routes it to the discussion agent.

    # For other decisions or brief revision, add user's input as a message
    user_text = submission.get("custom_input") or chosen or "Continue"
    messages.append({
        "id": f"msg-user-{len(messages)}",
        "role": "user",
        "content": user_text,
        "timestamp": "",
    })

    # If user wants to revise the brief, clear it
    if pending.get("id") == "confirm-brief" and chosen == "revise":
        return {
            **state,
            "idea_brief": {},
            "decisions": decisions,
            "messages": messages,
            "pending_decision": None,
            "pipeline_status": "running",
        }

    return {
        **state,
        "decisions": decisions,
        "messages": messages,
        "pending_decision": None,
        "pipeline_status": "running",
    }
