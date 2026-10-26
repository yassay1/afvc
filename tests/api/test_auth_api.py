"""Fixed-account session gate HTTP tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import require_login
from backend.core.config import get_session_cookie_name, is_sql_backend
from backend.infrastructure import auth_repo
from backend.main import app

pytestmark = pytest.mark.skipif(not is_sql_backend(), reason="Postgres 不可用")


@pytest.fixture
def raw_client():
    """No dependency override — exercise real cookie sessions."""
    app.dependency_overrides.pop(require_login, None)
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(require_login, None)


@pytest.fixture
def test_user():
    username = f"u_{uuid.uuid4().hex[:10]}"
    password = "test-pass-ok"
    user = auth_repo.create_user(username, password)
    yield username, password, user
    try:
        auth_repo.set_user_active(username, active=False)
    except ValueError:
        pass


def test_business_routes_require_login(raw_client: TestClient):
    assert raw_client.get("/usecases/devices").status_code == 401
    assert raw_client.post("/interaction/turn", json={"query": "hi"}).status_code == 401
    assert raw_client.get("/health").status_code == 200


def test_login_me_logout_roundtrip(raw_client: TestClient, test_user):
    username, password, _ = test_user
    cookie = get_session_cookie_name()

    bad = raw_client.post("/auth/login", json={"username": username, "password": "wrong-pass-xx"})
    assert bad.status_code == 401

    login = raw_client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    assert login.json()["username"] == username
    assert cookie in raw_client.cookies

    me = raw_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == username

    devices = raw_client.get("/usecases/devices")
    assert devices.status_code == 200

    logout = raw_client.post("/auth/logout")
    assert logout.status_code == 200
    assert raw_client.get("/auth/me").status_code == 401
    assert raw_client.get("/usecases/devices").status_code == 401


def test_disabled_user_cannot_login(raw_client: TestClient, test_user):
    username, password, _ = test_user
    auth_repo.set_user_active(username, active=False)
    response = raw_client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401


def test_no_public_register_route(raw_client: TestClient):
    assert raw_client.post("/auth/register", json={"username": "x", "password": "y"}).status_code == 404
