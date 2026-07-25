import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.agents import graph
from app.config import settings
from app.routers import health, projects
from app.routers import settings as settings_router
from app.websocket.socket_app import ws_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: persist pipeline state to SQLite so projects survive restarts
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    saver = await graph.use_sqlite_checkpointer(str(data_dir / "checkpoints.sqlite"))
    logger.info(f"Pipeline checkpoints persisted to {data_dir / 'checkpoints.sqlite'}")
    yield
    # Shutdown
    await saver.conn.close()


app = FastAPI(
    title="ProjectFactory API",
    description="AI-Powered Autonomous Project Specification Factory",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time pipeline updates."""
    await ws_manager.connect(project_id, websocket)
    try:
        while True:
            # Keep connection alive; client messages are handled via REST
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(project_id, websocket)
