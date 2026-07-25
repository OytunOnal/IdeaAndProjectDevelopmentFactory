"""Disk-backed project index.

Pipeline state lives in the LangGraph SQLite checkpointer; this store holds
the lightweight project list (name, phase, status) shown on the dashboard,
persisted as JSON so it survives restarts. Single-process dev server — no
locking needed.
"""

import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ProjectStore:
    def __init__(self, path: Path):
        self._path = path
        self._items: dict[str, dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._path.exists():
            try:
                self._items = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load project store, starting empty: {e}")
                self._items = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._items, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save project store: {e}")

    def list(self) -> list[dict]:
        self._ensure_loaded()
        return sorted(
            self._items.values(),
            key=lambda p: p.get("created_at", ""),
            reverse=True,
        )

    def get(self, project_id: str) -> dict | None:
        self._ensure_loaded()
        return self._items.get(project_id)

    def upsert(self, project: dict) -> None:
        self._ensure_loaded()
        self._items[project["id"]] = project
        self._save()

    def update(self, project_id: str, **fields) -> None:
        self._ensure_loaded()
        if project_id in self._items:
            self._items[project_id].update(fields)
            self._save()

    def delete(self, project_id: str) -> None:
        self._ensure_loaded()
        if self._items.pop(project_id, None) is not None:
            self._save()


project_store = ProjectStore(Path(settings.data_dir) / "projects.json")
