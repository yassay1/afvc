"""Pytest session setup: default LLM off; SQL if Postgres is reachable."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("AFVC_USE_LLM", "false")
    os.environ.setdefault("AFVC_AGENT_GRAPH", "true")
    if os.environ.get("AFVC_DATA_PROFILE", "").strip().lower() == "demo":
        os.environ.setdefault("DATABASE_URL", "postgresql://afvc_demo:afvc_demo@127.0.0.1:55433/afvc_demo")
        os.environ["AFVC_DATA_BACKEND"] = "sql"
        return
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://afvc:afvc@localhost:5432/afvc",
    )
    if os.environ.get("AFVC_DATA_BACKEND", "").strip().lower() in {"file", "excel", "raw"}:
        return
    try:
        import psycopg

        url = os.environ["DATABASE_URL"]
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        os.environ["AFVC_DATA_BACKEND"] = "sql"
    except Exception:
        os.environ["AFVC_DATA_BACKEND"] = "file"


@pytest.fixture(scope="session", autouse=True)
def _init_sql_working_set():
    from backend.core.config import is_sql_backend

    if not is_sql_backend():
        yield
        return
    from backend.infrastructure.db import init_db
    from backend.infrastructure.workorder_repo import seed_default_if_empty

    init_db(with_checkpointer=True)
    from backend.core.config import get_data_profile

    if get_data_profile() == "demo":
        from backend.infrastructure.demo_seed import seed_demo_if_needed

        seed_demo_if_needed()
    else:
        seed_default_if_empty()
    yield


@pytest.fixture(autouse=True)
def _bypass_login_for_tests():
    """API contract tests call business routes without a browser login.

    Auth-specific tests clear this override (see tests/api/test_auth_api.py).
    """
    from backend.api.deps import require_login
    from backend.infrastructure.auth_repo import AuthUser
    from backend.main import app

    app.dependency_overrides[require_login] = lambda: AuthUser(
        id="00000000-0000-4000-8000-000000000001",
        username="pytest",
        is_active=True,
    )
    yield
    app.dependency_overrides.pop(require_login, None)
