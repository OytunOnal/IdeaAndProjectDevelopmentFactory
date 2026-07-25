"""Orchestrator agent - routes work to appropriate agents based on pipeline state."""

from app.agents.state import ProjectState


def route_orchestrator(state: ProjectState) -> str:
    """Determine next node based on current pipeline state."""

    # Waiting for user input → stop the graph run. Checked BEFORE
    # pending_decision: a paused decision would otherwise bounce between
    # orchestrator and decision_handler forever (recursion error).
    if state.get("pipeline_status") == "waiting_for_user":
        return "__end__"

    # Fresh pending decision → let the decision handler resolve or pause it
    if state.get("pending_decision"):
        return "decision_handler"

    phase = state.get("current_phase", "idle")

    # IDLE: new project, start discovery
    if phase == "idle":
        return "idea_analyst"

    # DISCOVERY phase
    if phase == "discovery":
        idea_brief = state.get("idea_brief")

        # No brief yet, or brief not confirmed → keep talking to idea analyst
        if not idea_brief or not idea_brief.get("confirmed"):
            return "idea_analyst"

        # Brief confirmed → run research agents sequentially, then review
        if not state.get("research_approved"):
            if not state.get("market_research", {}).get("completed"):
                return "market_researcher"
            if not state.get("competitor_analysis", {}).get("completed"):
                return "competitor_analyst"
            if not state.get("tech_feasibility", {}).get("completed"):
                return "tech_feasibility"
            if not state.get("research_review_done"):
                return "research_review"
            # Review done but not approved → answer follow-up questions
            messages = state.get("messages", [])
            if messages and messages[-1].get("role") == "user":
                return "research_discussion"
            return "__end__"

    # SPECIFICATION phase: write the five spec documents, then review
    if phase == "specification":
        for key, node in (
            ("prd", "spec_writer"),
            ("architecture", "architecture_designer"),
            ("ux_design", "ux_strategist"),
            ("gtm_strategy", "gtm_strategist"),
            ("financial_model", "financial_modeler"),
        ):
            if not state.get(key):
                return node
        if not state.get("spec_review_done"):
            return "spec_review"
        return _discussion_or_end(state)

    # QUALITY phase: score, stress-test, cross-check, then review
    if phase == "quality":
        if not state.get("quality_feedback"):
            return "quality_reviewer"
        if not state.get("devils_advocate"):
            return "devils_advocate"
        if not state.get("consistency_report"):
            return "consistency_checker"
        if not state.get("quality_review_done"):
            return "quality_review"
        return _discussion_or_end(state)

    # PACKAGING phase: roadmap, then assemble the final file set
    if phase == "packaging":
        if not state.get("implementation_roadmap"):
            return "planning_agent"
        if not state.get("project_files"):
            return "doc_formatter"
        return "__end__"

    # COMPLETED: still answer questions about the finished project
    if phase == "completed":
        return _discussion_or_end(state)

    return "__end__"


def _discussion_or_end(state: ProjectState) -> str:
    """Route a fresh user message to the discussion agent, else stop."""
    messages = state.get("messages", [])
    if messages and messages[-1].get("role") == "user":
        return "review_discussion"
    return "__end__"


async def orchestrator_node(state: ProjectState) -> ProjectState:
    """Orchestrator node - sets up initial state if needed, then routing handles the rest."""

    # Initialize phase if this is the first run
    if state.get("current_phase", "idle") == "idle" and state.get("messages"):
        return {
            **state,
            "current_phase": "discovery",
            "pipeline_status": "running",
            "current_agent": "orchestrator",
        }

    return state
