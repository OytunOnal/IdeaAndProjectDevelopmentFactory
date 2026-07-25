"""Shared helpers for pipeline agents."""

import json
import logging

from app.agents.state import ProjectState
from app.websocket.socket_app import emit_pipeline_update

logger = logging.getLogger(__name__)

DOC_TITLES = {
    "market_research": "Market Research",
    "competitor_analysis": "Competitor Analysis",
    "tech_feasibility": "Tech Feasibility",
    "prd": "Product Requirements Document (PRD)",
    "architecture": "System Architecture",
    "ux_design": "UX Specification",
    "gtm_strategy": "Go-to-Market Strategy",
    "financial_model": "Financial Model",
    "quality_feedback": "Quality Review",
    "devils_advocate": "Devil's Advocate Report",
    "consistency_report": "Consistency Report",
    "implementation_roadmap": "Implementation Roadmap",
}


def get_doc(state: ProjectState, key: str) -> str | None:
    """Return a document's text whether it's stored as str or research dict."""
    value = state.get(key)
    if isinstance(value, dict):
        return value.get("report")
    return value or None


def docs_context(state: ProjectState, keys: list[str], max_chars: int = 12000) -> str:
    """Concatenate the requested documents as markdown context for a prompt."""
    parts = []
    for key in keys:
        doc = get_doc(state, key)
        if doc:
            parts.append(f"## {DOC_TITLES.get(key, key)}\n\n{doc[:max_chars]}")
    return "\n\n---\n\n".join(parts)


def brief_context(state: ProjectState) -> str:
    """Render the confirmed idea brief as prompt context."""
    brief = state.get("idea_brief", {})
    clean = {k: v for k, v in brief.items() if k != "confirmed"}
    return (
        f"Project name: {state.get('project_name', 'Untitled')}\n\n"
        f"Confirmed idea brief:\n```json\n{json.dumps(clean, indent=2, ensure_ascii=False)}\n```"
    )


def agent_message(state: ProjectState, agent_id: str, content: str) -> list:
    """Return the message list with a new agent message appended."""
    messages = list(state.get("messages", []))
    messages.append({
        "id": f"msg-agent-{len(messages)}",
        "role": "agent",
        "agent_id": agent_id,
        "content": content,
        "timestamp": "",
    })
    return messages


async def emit_progress(state: ProjectState, agent_id: str, note: str) -> None:
    """Push a live 'working on it' update to WebSocket clients.

    The transient message is NOT stored in state — the final pipeline
    response replaces it with the real output.
    """
    project_id = state.get("project_id")
    if not project_id:
        return
    transient = {
        "id": f"msg-progress-{agent_id}",
        "role": "agent",
        "agent_id": agent_id,
        "content": note,
        "timestamp": "",
    }
    try:
        await emit_pipeline_update(project_id, {
            **state,
            "messages": [*state.get("messages", []), transient],
            "current_agent": agent_id,
            "pipeline_status": "running",
        })
    except Exception:  # never let progress reporting break the pipeline
        logger.debug("Progress emit failed", exc_info=True)
