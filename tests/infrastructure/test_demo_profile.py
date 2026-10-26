"""Synthetic data isolation and database seed checks."""

import pytest
from fastapi.testclient import TestClient

from backend.core.config import get_database_url
from backend.infrastructure.demo_seed import validate_demo_dataset
from backend.infrastructure.workorders import DEMO_WORKORDERS_FILE, get_latest_raw_file, read_workorder_file
from backend.main import app


def test_demo_never_selects_raw_even_if_it_exists(monkeypatch, tmp_path):
    from backend.infrastructure import workorders

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "afc非首次故障-L01线.xlsx").write_bytes(b"must not be read")
    monkeypatch.setattr(workorders, "RAW_DATA_DIR", raw)
    monkeypatch.setenv("AFVC_DATA_PROFILE", "demo")
    monkeypatch.setenv("AFVC_DATA_BACKEND", "sql")
    assert get_latest_raw_file() == DEMO_WORKORDERS_FILE
    assert read_workorder_file().height == 288
    with pytest.raises(RuntimeError, match="只能读取"):
        read_workorder_file(raw / "afc非首次故障-L01线.xlsx")


def test_demo_requires_isolated_database(monkeypatch):
    monkeypatch.setenv("AFVC_DATA_PROFILE", "demo")
    monkeypatch.setenv("DATABASE_URL", "postgresql://afvc:afvc@localhost:5433/afvc")
    with pytest.raises(RuntimeError, match="127.0.0.1:55433/afvc_demo"):
        get_database_url()


def test_dataset_references_and_seed_feedback():
    tasks = validate_demo_dataset()
    assert {task["status"] for task in tasks} == {"planned", "in_progress", "done"}
    assert sum(task["status"] == "done" for task in tasks) == 6


def test_missing_or_mismatched_demo_data_fails_explicitly(monkeypatch, tmp_path):
    from backend.infrastructure import demo_seed

    monkeypatch.setattr(demo_seed, "MOCK", tmp_path)
    with pytest.raises(FileNotFoundError, match="demo 数据文件缺失"):
        validate_demo_dataset()


def test_health_and_demo_upload_guard(monkeypatch, tmp_path):
    from backend.api import upload_api

    monkeypatch.setenv("AFVC_DATA_PROFILE", "demo")
    monkeypatch.setattr(upload_api, "RAW_DATA_DIR", tmp_path)
    client = TestClient(app)
    assert client.get("/health").json()["data_profile"] == "demo"
    response = client.post("/upload/workorders", files={"file": ("test.csv", b"test", "text/csv")})
    assert response.status_code == 403
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(
    __import__("os").environ.get("AFVC_DATA_PROFILE") != "demo",
    reason="requires the isolated demo database",
)
def test_demo_seed_is_idempotent_and_tasks_are_readable():
    from backend.infrastructure.demo_seed import seed_demo_if_needed
    from backend.infrastructure.db import get_pool

    assert seed_demo_if_needed() == 0
    with get_pool().connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM business.workorders").fetchone()["n"] == 288
        assert conn.execute("SELECT COUNT(*) AS n FROM business.maintenance_tasks").fetchone()["n"] >= 18
    client = TestClient(app)
    listed = client.get("/usecases/maintenance/tasks")
    assert listed.status_code == 200
    tasks = listed.json()["tasks"]
    assert {task["id"] for task in validate_demo_dataset()} <= {task["id"] for task in tasks}
    assert {task["status"] for task in tasks} == {"planned", "in_progress", "done"}
    detail = client.get(f"/usecases/maintenance/tasks/{tasks[0]['id']}")
    assert detail.status_code == 200
    devices = client.get("/usecases/devices").json()["devices"]
    risks = client.get("/usecases/high-risk?top_n=10").json()["devices"]
    suggestions = client.get("/usecases/maintenance/suggestions?top_n=10").json()["suggestions"]
    assets = {device["assetnum"] for device in devices}
    assert len(assets) == 36
    assert all(row["assetnum"] in assets for row in [*risks, *suggestions, *tasks])
    assert all(row["reasons"] for row in suggestions)


@pytest.mark.skipif(
    __import__("os").environ.get("AFVC_DATA_PROFILE") != "demo",
    reason="requires the isolated demo database",
)
def test_restart_seed_preserves_later_created_task():
    from backend.infrastructure.demo_seed import seed_demo_if_needed
    from backend.infrastructure.db import get_pool

    client = TestClient(app)
    created = client.post("/usecases/maintenance/tasks", json={
        "assetnum": "DEMO-AGM-036", "station_name": "银湾站",
        "assignee_crew_id": "DEMO-CREW-01", "priority": 42,
    })
    assert created.status_code == 200
    task_id = created.json()["task"]["id"]
    try:
        assert seed_demo_if_needed() == 0
        detail = client.get(f"/usecases/maintenance/tasks/{task_id}")
        assert detail.status_code == 200
        assert detail.json()["task"]["priority"] == 42
    finally:
        with get_pool().connection() as conn:
            conn.execute("DELETE FROM business.maintenance_tasks WHERE id = %s", (task_id,))
            conn.commit()
