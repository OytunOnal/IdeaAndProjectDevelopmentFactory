"""LangGraph pipeline definition for ProjectFactory.

Week 2 scope: Orchestrator → Idea Analyst → Decision Handler loop.
Research agents and later phases are registered as nodes but not wired yet.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.collaboration import (
    doc_gate_node,
    revise_document_node,
    spec_improver_node,
)
from app.agents.decision_handler import decision_handler_node
from app.agents.idea_analyst import idea_analyst_node
from app.agents.orchestrator import orchestrator_node, route_orchestrator
from app.agents.packaging import doc_formatter_node, planning_agent_node
from app.agents.quality import (
    consistency_checker_node,
    devils_advocate_node,
    quality_review_node,
    quality_reviewer_node,
)
from app.agents.research import (
    competitor_analyst_node,
    market_researcher_node,
    research_discussion_node,
    research_review_node,
    tech_feasibility_node,
)
from app.agents.specification import (
    architecture_designer_node,
    financial_modeler_node,
    gtm_strategist_node,
    review_discussion_node,
    spec_review_node,
    spec_writer_node,
    ux_strategist_node,
)
from app.agents.state import ProjectState

# ── Stub nodes for agents not yet implemented (roadmap) ────────────


async def _stub(state: ProjectState) -> ProjectState:
    return state


brand_strategist_node = _stub
legal_advisor_node = _stub
visual_designer_node = _stub
design_system_architect_node = _stub
user_checkpoint_node = _stub


# ── Build the graph ────────────────────────────────────────────────

graph_builder = StateGraph(ProjectState)

# Register all nodes
graph_builder.add_node("orchestrator", orchestrator_node)
graph_builder.add_node("idea_analyst", idea_analyst_node)
graph_builder.add_node("decision_handler", decision_handler_node)
graph_builder.add_node("user_checkpoint", user_checkpoint_node)
# Research agents (live — run sequentially, then reviewed by the user)
graph_builder.add_node("market_researcher", market_researcher_node)
graph_builder.add_node("competitor_analyst", competitor_analyst_node)
graph_builder.add_node("tech_feasibility", tech_feasibility_node)
graph_builder.add_node("research_review", research_review_node)
graph_builder.add_node("research_discussion", research_discussion_node)
# Specification agents (live — write the five spec documents, then review)
graph_builder.add_node("spec_writer", spec_writer_node)
graph_builder.add_node("architecture_designer", architecture_designer_node)
graph_builder.add_node("ux_strategist", ux_strategist_node)
graph_builder.add_node("gtm_strategist", gtm_strategist_node)
graph_builder.add_node("financial_modeler", financial_modeler_node)
graph_builder.add_node("spec_review", spec_review_node)
graph_builder.add_node("review_discussion", review_discussion_node)
# Quality agents (live)
graph_builder.add_node("quality_reviewer", quality_reviewer_node)
graph_builder.add_node("devils_advocate", devils_advocate_node)
graph_builder.add_node("consistency_checker", consistency_checker_node)
graph_builder.add_node("quality_review", quality_review_node)
# Packaging agents (live)
graph_builder.add_node("planning_agent", planning_agent_node)
graph_builder.add_node("doc_formatter", doc_formatter_node)
# Collaboration nodes (per-doc gates, revisions, quality improvement)
graph_builder.add_node("doc_gate", doc_gate_node)
graph_builder.add_node("revise_document", revise_document_node)
graph_builder.add_node("spec_improver", spec_improver_node)
# Roadmap agents (stubs)
graph_builder.add_node("brand_strategist", brand_strategist_node)
graph_builder.add_node("legal_advisor", legal_advisor_node)
graph_builder.add_node("visual_designer", visual_designer_node)
graph_builder.add_node("design_system_architect", design_system_architect_node)


# ── Wire edges ─────────────────────────────────────────────────────

# Entry point
graph_builder.add_edge(START, "orchestrator")

# Orchestrator routes based on pipeline state
graph_builder.add_conditional_edges(
    "orchestrator",
    route_orchestrator,
    {
        "idea_analyst": "idea_analyst",
        "decision_handler": "decision_handler",
        "market_researcher": "market_researcher",
        "competitor_analyst": "competitor_analyst",
        "tech_feasibility": "tech_feasibility",
        "research_review": "research_review",
        "research_discussion": "research_discussion",
        "spec_writer": "spec_writer",
        "architecture_designer": "architecture_designer",
        "ux_strategist": "ux_strategist",
        "gtm_strategist": "gtm_strategist",
        "financial_modeler": "financial_modeler",
        "spec_review": "spec_review",
        "review_discussion": "review_discussion",
        "quality_reviewer": "quality_reviewer",
        "devils_advocate": "devils_advocate",
        "consistency_checker": "consistency_checker",
        "quality_review": "quality_review",
        "planning_agent": "planning_agent",
        "doc_formatter": "doc_formatter",
        "doc_gate": "doc_gate",
        "revise_document": "revise_document",
        "spec_improver": "spec_improver",
        "__end__": END,
    },
)

# Every worker node returns to the orchestrator, which decides what's next
for node in (
    "idea_analyst",
    "decision_handler",
    "market_researcher",
    "competitor_analyst",
    "tech_feasibility",
    "research_review",
    "research_discussion",
    "spec_writer",
    "architecture_designer",
    "ux_strategist",
    "gtm_strategist",
    "financial_modeler",
    "spec_review",
    "review_discussion",
    "quality_reviewer",
    "devils_advocate",
    "consistency_checker",
    "quality_review",
    "planning_agent",
    "doc_formatter",
    "doc_gate",
    "revise_document",
    "spec_improver",
):
    graph_builder.add_edge(node, "orchestrator")


# ── Compile with checkpointer ─────────────────────────────────────

# Default: in-memory checkpointer (used by tests and until startup runs).
# At app startup, main.py swaps in a SQLite checkpointer so pipeline state
# survives server restarts (see use_sqlite_checkpointer).
checkpointer = MemorySaver()

pipeline = graph_builder.compile(checkpointer=checkpointer)


async def use_sqlite_checkpointer(db_path: str):
    """Recompile the pipeline with a persistent SQLite checkpointer.

    Returns the saver so the caller can close its connection on shutdown.
    """
    global pipeline

    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    pipeline = graph_builder.compile(checkpointer=saver)
    return saver
