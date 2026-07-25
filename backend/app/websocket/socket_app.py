"""WebSocket manager using FastAPI's native WebSocket support.

python-socketio had OpenSSL DLL issues on Windows, so we use
FastAPI's built-in WebSocket support instead.
"""

import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[project_id].append(websocket)
        logger.info(f"WebSocket connected for project {project_id}")

    def disconnect(self, project_id: str, websocket: WebSocket):
        self.connections[project_id].remove(websocket)
        logger.info(f"WebSocket disconnected for project {project_id}")

    async def emit(self, project_id: str, event: str, data: dict):
        """Send event to all clients watching a project."""
        message = json.dumps({"type": event, "data": data})
        disconnected = []
        for ws in self.connections.get(project_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.connections[project_id].remove(ws)


ws_manager = WebSocketManager()


# ── Helper functions ──────────────────────────────────────────────


async def emit_agent_started(project_id: str, agent: str, phase: str):
    await ws_manager.emit(project_id, "agent:started", {"agent": agent, "phase": phase})


async def emit_agent_streaming(project_id: str, agent: str, token: str):
    await ws_manager.emit(project_id, "agent:streaming", {"agent": agent, "token": token})


async def emit_agent_completed(project_id: str, agent: str, summary: str):
    await ws_manager.emit(project_id, "agent:completed", {"agent": agent, "summary": summary})


async def emit_decision_required(project_id: str, decision: dict):
    await ws_manager.emit(project_id, "decision:required", decision)


async def emit_pipeline_update(project_id: str, state: dict):
    """Emit full pipeline state update."""
    await ws_manager.emit(project_id, "pipeline:update", {
        "messages": state.get("messages", []),
        "current_phase": state.get("current_phase"),
        "pipeline_status": state.get("pipeline_status"),
        "current_agent": state.get("current_agent"),
        "pending_decision": state.get("pending_decision"),
        "idea_brief": state.get("idea_brief"),
        "quality_score": state.get("quality_score"),
        "files": sorted((state.get("project_files") or {}).keys()),
    })
