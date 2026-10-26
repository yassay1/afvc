"""Use-case HTTP API contract tests."""

from fastapi.testclient import TestClient

from backend.application import usecases
from backend.main import app

client = TestClient(app)


def test_device_list_endpoint(monkeypatch):
    expected = {
        "status": "success",
        "message": "设备列表获取成功",
        "device_count": 1,
        "devices": [{
            "assetnum": "DEMO-AGM-001",
            "workorder_count": 2,
            "station_name": "示例站",
            "line": "L01",
            "brand": "DEMO",
            "last_record_time": "2026-01-01T08:00:00",
        }],
    }
    monkeypatch.setattr(usecases, "get_device_list", lambda: expected)
    response = client.get("/usecases/devices")
    assert response.status_code == 200
    assert response.json() == expected


def test_device_list_empty(monkeypatch):
    monkeypatch.setattr(usecases, "get_device_list", lambda: {
        "status": "success", "message": "设备列表获取成功", "device_count": 0, "devices": [],
    })
    response = client.get("/usecases/devices")
    assert response.status_code == 200
    assert response.json()["devices"] == []
    assert response.json()["device_count"] == 0


def test_device_list_application_errors(monkeypatch):
    def missing_column():
        raise ValueError("数据中缺少 assetnum 字段")

    monkeypatch.setattr(usecases, "get_device_list", missing_column)
    response = client.get("/usecases/devices")
    assert response.status_code == 404
    assert "assetnum" in response.json()["detail"]

    def unavailable_source():
        raise RuntimeError("数据源不可用")

    monkeypatch.setattr(usecases, "get_device_list", unavailable_source)
    response = client.get("/usecases/devices")
    assert response.status_code == 500


def test_device_list_openapi_contract():
    operation = client.get("/openapi.json").json()["paths"]["/usecases/devices"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("DeviceListResponse")


def test_diagnosis_endpoint():
    from backend.core.config import get_data_profile

    assetnum = "DEMO-AGM-001" if get_data_profile() == "demo" else "1000029970"
    r = client.get(f"/usecases/devices/{assetnum}/diagnosis")
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
    try:
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
    finally:
        from backend.core.config import is_sql_backend

        if is_sql_backend():
            from backend.infrastructure.db import get_pool

            with get_pool().connection() as conn:
                conn.execute("DELETE FROM business.maintenance_tasks WHERE id = %s", (task_id,))
                conn.commit()
