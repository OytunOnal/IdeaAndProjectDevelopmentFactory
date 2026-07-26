"""Shared helpers for pipeline agents."""

import json
import logging

from app.agents.state import ProjectState
from app.websocket.socket_app import emit_pipeline_update

logger = logging.getLogger(__name__)

# Where each document lives in the file tree (drafts + final export)
DOC_PATHS = {
    "market_research": "01_RESEARCH/market_research.md",
    "competitor_analysis": "01_RESEARCH/competitor_analysis.md",
    "tech_feasibility": "01_RESEARCH/tech_feasibility.md",
    "prd": "02_PRODUCT/prd.md",
    "ux_design": "03_DESIGN/ux_specification.md",
    "architecture": "04_TECH/architecture.md",
    "gtm_strategy": "05_PLANNING/gtm_strategy.md",
    "financial_model": "05_PLANNING/financial_model.md",
    "implementation_roadmap": "05_PLANNING/development_roadmap.md",
    "quality_feedback": "06_QUALITY/quality_review.md",
    "devils_advocate": "06_QUALITY/devils_advocate.md",
    "consistency_report": "06_QUALITY/consistency_report.md",
}

# Shared principle appended to content-producing agent prompts
CONSTRUCTIVE_PRINCIPLE = """

GUIDING PRINCIPLE: Be realistic AND constructive. Your goal is to shape this project into something buildable and commercially viable. Never dismiss an idea or a user request outright — when something is weak or infeasible as stated, propose the nearest viable version (smaller scope, different segment, different pricing, phased approach) and explain the trade-off. Every problem you raise must come with at least one concrete way to address it.

End the document with a section titled exactly `## Recommended Adjustments` containing 1-3 NUMBERED, optional, concrete changes to the PROJECT itself that your findings suggest would improve its viability (e.g. "1. Launch in Germany only first — 60% of the addressable demand is there"). These are proposals for the user to accept or ignore — not editorial notes about the document. If you have no meaningful recommendation, write: None — the current direction holds up."""


SPEC_DOC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")

# Instruction block that lets discussion agents ACT instead of giving advice
ACTION_CAPABILITY = """

YOU CAN TAKE ACTION. There are no UI forms, menus, or buttons for the user to fill in — never instruct them to click or paste anything. When the user asks you to change, fix, or improve documents (rather than asking a question), do NOT explain how — trigger the work yourself by responding with ONLY a fenced JSON block:

To rewrite one document with specific feedback:
```json
{"action": "revise", "target": "<one of: market_research|competitor_analysis|tech_feasibility|prd|architecture|ux_design|gtm_strategy|financial_model>", "feedback": "<the concrete change request, self-contained>"}
```

To run an improvement pass across the specs (e.g. fixing quality gaps or consistency issues):
```json
{"action": "improve", "focus": "<what to prioritize>", "targets": ["<optional doc keys to limit the pass>"]}
```

Only answer in plain text when the user is genuinely asking a question, not requesting changes."""


def parse_action(text: str) -> dict | None:
    """Extract an {"action": ...} JSON block from a discussion agent's reply."""
    import json as _json

    if "```json" not in text or '"action"' not in text:
        return None
    try:
        start = text.index("```json") + 7
        end = text.index("```", start)
        data = _json.loads(text[start:end].strip())
        if isinstance(data, dict) and data.get("action") in ("revise", "improve"):
            return data
    except (ValueError, _json.JSONDecodeError):
        pass
    return None


def apply_discussion_action(state: ProjectState, action: dict) -> dict | None:
    """Turn a discussion agent's action JSON into pipeline state, or None."""
    act = action.get("action")

    if act == "revise":
        target = action.get("target")
        feedback = (action.get("feedback") or "").strip()
        if target in DOC_PATHS and get_doc(state, target) and feedback:
            return {
                **state,
                "revision_target": target,
                "revision_feedback": feedback,
                "messages": agent_message(
                    state, "orchestrator",
                    f"✏️ On it — sending your request to the "
                    f"{DOC_TITLES.get(target, target)} owner...",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": None,
            }
        return None

    if act == "improve":
        focus = (action.get("focus") or "").strip()
        targets = [t for t in (action.get("targets") or []) if t in SPEC_DOC_KEYS]

        if state.get("current_phase") == "quality":
            return {
                **state,
                "quality_improve_requested": True,
                "quality_improve_focus": focus or None,
                "quality_improve_targets": targets,
                "messages": agent_message(
                    state, "orchestrator",
                    "🔧 Running an improvement pass"
                    + (f" focused on: {focus}" if focus else "")
                    + (f" (documents: {', '.join(targets)})" if targets else "")
                    + "...",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": None,
            }

        # Outside the quality phase, a single clear target becomes a revision
        if len(targets) == 1 and get_doc(state, targets[0]) and focus:
            return apply_discussion_action(
                state, {"action": "revise", "target": targets[0], "feedback": focus}
            )
        return None

    return None


def extract_adjustments(text: str | None) -> str | None:
    """Pull the `## Recommended Adjustments` section out of a document."""
    if not text or "## Recommended Adjustments" not in text:
        return None
    start = text.index("## Recommended Adjustments") + len("## Recommended Adjustments")
    rest = text[start:]
    end = rest.find("\n## ")
    section = (rest[:end] if end != -1 else rest).strip()
    if not section or section.lower().startswith("none"):
        return None
    return section

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


def doc_gate_card(key: str, has_adjustments: bool = False) -> dict:
    """Approval card shown after a document is produced or revised."""
    title = DOC_TITLES.get(key, key)
    path = DOC_PATHS.get(key, key)

    question = f"{title} is ready — review it in the files panel ({path})."
    options = [
        {
            "id": "confirm",
            "label": "Approve as-is",
            "description": "Accept this document and move on",
        },
    ]
    if has_adjustments:
        question += (
            " It ends with numbered Recommended Adjustments — apply all of them, "
            "pick some (type e.g. 'apply 1 and 3'), or approve as-is."
        )
        options.append({
            "id": "apply",
            "label": "Apply the recommended adjustments",
            "description": "Integrate all numbered recommendations into the project",
        })
    options.append({
        "id": "revise",
        "label": "Request changes",
        "description": "Describe what should be different — the agent will rewrite it",
    })

    return {
        "id": f"approve-doc:{key}",
        "agent": "orchestrator",
        "category": "strategic",
        "question": question,
        "options": options,
        "agent_recommendation": "confirm",
        "agent_reasoning": "Review the document before the pipeline builds on it.",
        "allow_delegate": True,
        "allow_freeform": True,
    }


def current_gate_card(state: ProjectState) -> dict | None:
    """The approval card that should be open right now, given pipeline state.

    Used by discussion agents to re-present the correct card after answering
    a question. Returns None when nothing needs approval (e.g. completed).
    """
    phase = state.get("current_phase")
    approved = state.get("approved_docs") or []

    if phase == "discovery":
        for key in ("market_research", "competitor_analysis", "tech_feasibility"):
            doc = state.get(key)
            if isinstance(doc, dict) and doc.get("completed") and key not in approved:
                return doc_gate_card(key, bool(extract_adjustments(get_doc(state, key))))
        return None  # research_review builds its own phase card

    if phase == "specification":
        for key in ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model"):
            if state.get(key) and key not in approved:
                return doc_gate_card(key, bool(extract_adjustments(get_doc(state, key))))
        return None

    return None


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
