"""ProjectStore round-trips projects to disk."""

from app.services.project_store import ProjectStore


def test_store_persists_across_instances(tmp_path):
    path = tmp_path / "projects.json"

    store = ProjectStore(path)
    store.upsert({"id": "p1", "name": "Test", "created_at": "2026-01-01"})
    store.upsert({"id": "p2", "name": "Later", "created_at": "2026-02-01"})
    store.update("p1", pipeline_status="running")

    # Fresh instance reads the same file (simulates a server restart)
    reloaded = ProjectStore(path)
    assert reloaded.get("p1")["pipeline_status"] == "running"
    # Newest first
    assert [p["id"] for p in reloaded.list()] == ["p2", "p1"]

    reloaded.delete("p2")
    assert ProjectStore(path).get("p2") is None


def test_store_survives_corrupt_file(tmp_path):
    path = tmp_path / "projects.json"
    path.write_text("{not json", encoding="utf-8")

    store = ProjectStore(path)
    assert store.list() == []
    store.upsert({"id": "p1", "name": "Recovered", "created_at": ""})
    assert ProjectStore(path).get("p1")["name"] == "Recovered"
