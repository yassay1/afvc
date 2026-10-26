from fastapi.testclient import TestClient

from backend.application import maintenance_tasks
from backend.main import app


client = TestClient(app)


def test_api_rejects_direct_completion_without_touching_repository(monkeypatch):
    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("direct completion must be rejected before repository write")

    monkeypatch.setattr(maintenance_tasks.repo, "create_task", unexpected_write)
    created = client.post(
        "/usecases/maintenance/tasks",
        json={"assetnum": "DEMO-AGM-001", "status": "done"},
    )
    assert created.status_code == 409
    assert "提交现场执行反馈" in created.json()["detail"]

    monkeypatch.setattr(
        maintenance_tasks.repo,
        "get_task",
        lambda _task_id: {"id": "task-1", "status": "in_progress", "feedback_result": None},
    )
    updated = client.patch(
        "/usecases/maintenance/tasks/task-1",
        json={"status": "DONE"},
    )
    assert updated.status_code == 409
    assert "提交现场执行反馈" in updated.json()["detail"]


def test_api_returns_422_for_invalid_priority_and_blank_feedback(monkeypatch):
    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("invalid inputs must be rejected before repository write")

    monkeypatch.setattr(maintenance_tasks.repo, "create_task", unexpected_write)
    zero_priority = client.post(
        "/usecases/maintenance/tasks",
        json={"assetnum": "DEMO-AGM-001", "priority": 0},
    )
    assert zero_priority.status_code == 422

    monkeypatch.setattr(maintenance_tasks.repo, "record_feedback", unexpected_write)
    blank_feedback = client.post(
        "/usecases/maintenance/tasks/task-1/feedback",
        json={"result": "   "},
    )
    assert blank_feedback.status_code == 422
