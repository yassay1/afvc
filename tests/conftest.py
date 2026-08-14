"""Pytest session setup: default LLM off; SQL if Postgres is reachable."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("AFVC_USE_LLM", "false")
    os.environ.setdefault("AFVC_AGENT_GRAPH", "true")
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
    seed_default_if_empty()
    yield
