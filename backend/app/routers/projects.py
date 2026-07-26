"""Project endpoints - CRUD and pipeline control."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import Response

from app.agents import graph
from app.agents.decision_handler import resolve_decision
from app.agents.packaging import draft_files
from app.models.decision import DecisionSubmit
from app.models.project import ProjectCreate, ProjectResponse
from app.services.project_store import project_store
from app.websocket.socket_app import emit_pipeline_update

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate):
    project_id = str(uuid4())
    project = {
        "id": project_id,
        "name": data.name,
        "slug": data.name.lower().replace(" ", "-"),
        "description": data.description,
        "current_phase": "idle",
        "pipeline_status": "idle",
        "quality_score": None,
        "estimated_cost_usd": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    project_store.upsert(project)
    return ProjectResponse(**project)


@router.get("/projects")
async def list_projects():
    return {"projects": project_store.list()}


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = project_store.get(project_id)
    return project if project else {"error": "Project not found"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    project_store.delete(project_id)
    return {"deleted": True}


@router.post("/projects/{project_id}/start")
async def start_pipeline(project_id: str, body: dict | None = None):
    """Start the pipeline with an initial idea message."""
    initial_message = ""
    api_key = ""

    if body:
        initial_message = body.get("message", "")
        api_key = body.get("api_key", "")

    if not initial_message:
        return {"error": "No message provided"}
    # api_key is optional if .env has a configured key (BYOK fallback)

    # Build initial state
    initial_state = {
        "project_id": project_id,
        "project_name": (project_store.get(project_id) or {}).get("name", ""),
        "current_phase": "idle",
        "pipeline_status": "running",
        "current_agent": "orchestrator",
        "api_key": api_key,
        "autonomy_level": {"strategic": "ask", "technical": "suggest", "content": "delegate", "quality": "ask"},
        "messages": [
            {
                "id": "msg-user-0",
                "role": "user",
                "content": initial_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "decisions": [],
        "pending_decision": None,
        "approved_docs": [],
        "revision_target": None,
        "revision_feedback": None,
        "total_llm_calls": 0,
        "total_tokens_used": 0,
        "estimated_cost": 0,
    }

    # Run the pipeline
    thread_config = {"configurable": {"thread_id": project_id}}

    try:
        result = await graph.pipeline.ainvoke(initial_state, config=thread_config)

        project_store.update(
            project_id,
            current_phase=result.get("current_phase", "discovery"),
            pipeline_status=result.get("pipeline_status", "running"),
        )

        # Emit update to WebSocket clients
        await emit_pipeline_update(project_id, result)

        return _pipeline_response(result)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return {"error": str(e)}


def _pipeline_response(result: dict) -> dict:
    """Shared response shape for pipeline-driving endpoints."""
    return {
        "status": result.get("pipeline_status"),
        "current_phase": result.get("current_phase"),
        "current_agent": result.get("current_agent"),
        "messages": result.get("messages", []),
        "pending_decision": result.get("pending_decision"),
        "idea_brief": result.get("idea_brief"),
        "research": {
            "market_research": result.get("market_research"),
            "competitor_analysis": result.get("competitor_analysis"),
            "tech_feasibility": result.get("tech_feasibility"),
            "approved": result.get("research_approved", False),
        },
        "quality_score": result.get("quality_score"),
        "files": sorted(draft_files(result).keys()),
    }


@router.get("/projects/{project_id}/state")
async def get_pipeline_state(project_id: str):
    """Return the current pipeline state (for page loads / reconnects)."""
    state = await _get_state_values(project_id)

    if not state:
        return {"exists": False, "project": project_store.get(project_id)}

    return {"exists": True, **_pipeline_response(state)}


@router.post("/projects/{project_id}/chat")
async def send_chat_message(project_id: str, body: dict):
    """Send a user message and continue the pipeline."""
    message = body.get("message", "")
    api_key = body.get("api_key", "")

    if not message:
        return {"error": "No message provided"}

    thread_config = {"configurable": {"thread_id": project_id}}

    # Get current state from checkpointer
    current_state = await graph.pipeline.aget_state(thread_config)

    if not current_state.values:
        return {"error": "No active pipeline for this project. Call /start first."}

    state = dict(current_state.values)

    # Add user message
    messages = list(state.get("messages", []))
    messages.append({
        "id": f"msg-user-{len(messages)}",
        "role": "user",
        "content": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    state["messages"] = messages
    state["pipeline_status"] = "running"
    state["api_key"] = api_key or state.get("api_key", "")
    # A free-text message answers any open decision card
    state["pending_decision"] = None

    # Re-run pipeline with updated state
    try:
        result = await graph.pipeline.ainvoke(state, config=thread_config)

        project_store.update(
            project_id,
            current_phase=result.get("current_phase"),
            pipeline_status=result.get("pipeline_status"),
        )
        await emit_pipeline_update(project_id, result)

        return _pipeline_response(result)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/projects/{project_id}/decision")
async def submit_decision(project_id: str, body: DecisionSubmit):
    """Submit a user decision and resume the pipeline."""
    thread_config = {"configurable": {"thread_id": project_id}}

    current_state = await graph.pipeline.aget_state(thread_config)
    if not current_state.values:
        return {"error": "No active pipeline for this project."}

    state = dict(current_state.values)

    # Resolve the decision
    updated_state = resolve_decision(state, body.model_dump())

    # Re-run pipeline
    try:
        result = await graph.pipeline.ainvoke(updated_state, config=thread_config)

        project_store.update(
            project_id,
            current_phase=result.get("current_phase"),
            pipeline_status=result.get("pipeline_status"),
        )
        await emit_pipeline_update(project_id, result)

        return _pipeline_response(result)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/projects/{project_id}/pause")
async def pause_pipeline(project_id: str):
    return {"status": "paused"}


@router.post("/projects/{project_id}/resume")
async def resume_pipeline(project_id: str):
    return {"status": "running"}


async def _get_state_values(project_id: str) -> dict:
    thread_config = {"configurable": {"thread_id": project_id}}
    current_state = await graph.pipeline.aget_state(thread_config)
    return dict(current_state.values) if current_state.values else {}


@router.get("/projects/{project_id}/files")
async def list_files(project_id: str):
    state = await _get_state_values(project_id)
    files = draft_files(state)
    return {"files": [{"path": p, "size": len(files[p])} for p in sorted(files)]}


@router.get("/projects/{project_id}/files/{file_path:path}")
async def get_file(project_id: str, file_path: str):
    state = await _get_state_values(project_id)
    files = draft_files(state)
    if file_path not in files:
        return {"error": "File not found", "file_path": file_path}
    return {"file_path": file_path, "content": files[file_path]}


@router.get("/projects/{project_id}/quality")
async def get_quality_score(project_id: str):
    state = await _get_state_values(project_id)
    breakdown = state.get("quality_breakdown") or {}
    return {
        "score": state.get("quality_score"),
        "breakdown": breakdown,
        "grade": breakdown.get("grade"),
    }


@router.get("/projects/{project_id}/decisions")
async def get_decisions(project_id: str):
    state = await _get_state_values(project_id)
    return {"decisions": state.get("decisions", [])}


@router.get("/projects/{project_id}/export")
async def export_project_zip(project_id: str):
    """Download all generated documents as a ZIP archive."""
    import io
    import zipfile

    state = await _get_state_values(project_id)
    files = state.get("project_files") or {}
    if not files:
        return {"error": "No files generated yet — complete the pipeline first."}

    slug = (project_store.get(project_id) or {}).get("slug", "project")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(f"{slug}/{path}", content)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}-specs.zip"'},
    )


@router.post("/projects/{project_id}/export")
async def export_project(project_id: str):
    state = await _get_state_values(project_id)
    files = state.get("project_files") or {}
    return {
        "download_url": f"/api/projects/{project_id}/export" if files else None,
        "file_count": len(files),
    }
