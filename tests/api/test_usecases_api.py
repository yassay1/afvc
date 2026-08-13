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
