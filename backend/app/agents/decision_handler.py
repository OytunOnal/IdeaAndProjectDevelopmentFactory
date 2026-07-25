"""Decision handler node - manages HITL (Human-in-the-Loop) decision points."""

import logging

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
