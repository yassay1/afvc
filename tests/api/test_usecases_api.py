"""Use-case HTTP API contract tests."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_diagnosis_endpoint():
    r = client.get("/usecases/devices/1000029970/diagnosis")
    assert r.status_code == 200
    body = r.json()
    assert "risk_prediction" in body or body.get("status") == "success"


def test_old_agent_path_gone():
    r = client.post("/agent/diagnose", json={"query": "hi"})
    assert r.status_code == 404


def test_interaction_turn_returns_answer():
    r = client.post("/interaction/turn", json={"query": "hi", "session_id": "api-t1"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"success", "clarified", "rejected"}
    assert "final_answer" in body
    assert body["session_id"] == "api-t1"


def test_overview_endpoint():
    r = client.get("/usecases/overview", params={"top_n": 5})
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_maintenance_http_loop():
    """预测对齐后的建议 → 建任务 → 调整 → 反馈，经 HTTP 可跑通。"""
    sug = client.get(
        "/usecases/maintenance/suggestions",
        params={"top_n": 3, "fault_focus": "暂停服务"},
    )
    assert sug.status_code == 200
    body = sug.json()
    assert body["ranking_method"] == "deterministic_weighted_rules"
    assert body["suggestions"]
    top = body["suggestions"][0]
    assert top.get("reasons")

    created = client.post(
        "/usecases/maintenance/accept-suggestion",
        json={"suggestion": top, "priority": 1},
    )
    assert created.status_code == 200
    task = created.json()["task"]
    task_id = task["id"]
    assert task["assetnum"] == top["assetnum"]

    patched = client.patch(
        f"/usecases/maintenance/tasks/{task_id}",
        json={"status": "in_progress", "priority": 2},
    )
    assert patched.status_code == 200
    assert patched.json()["task"]["status"] == "in_progress"

    feedback = client.post(
        f"/usecases/maintenance/tasks/{task_id}/feedback",
        json={
            "result": "HTTP 闭环验收：已现场处理",
            "matched_fault": True,
            "followed_suggestion": True,
        },
    )
    assert feedback.status_code == 200
    assert feedback.json()["task"]["status"] == "done"

    listed = client.get("/usecases/maintenance/tasks", params={"status": "done"})
    assert listed.status_code == 200
    assert any(t["id"] == task_id for t in listed.json()["tasks"])
