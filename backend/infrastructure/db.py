"""PostgreSQL connection pool, SQL migrations, and Agent checkpointer setup."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.core.config import get_database_url

logger = logging.getLogger("afvc.db")

SQL_DIR = Path(__file__).resolve().parents[2] / "scripts" / "sql"

_pool: ConnectionPool | None = None
_checkpointer_pool: ConnectionPool | None = None
_checkpointer = None
_initialized = False


def wait_for_postgres(timeout_seconds: float = 20.0) -> None:
    url = get_database_url()
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 — retry until timeout
            last_error = exc
            time.sleep(0.4)
    raise RuntimeError(f"PostgreSQL 未就绪（{url}）：{last_error}")


def can_connect(timeout_seconds: float = 2.0) -> bool:
    try:
        with psycopg.connect(get_database_url(), connect_timeout=int(timeout_seconds)) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_database_url(),
            min_size=1,
            max_size=8,
            open=True,
            kwargs={
                "autocommit": False,
                "row_factory": dict_row,
                "options": "-c search_path=business,public",
            },
        )
    return _pool


def apply_migrations(conn: psycopg.Connection | None = None) -> list[str]:
    """Apply scripts/sql/*.sql in name order. Idempotent via schema_migrations."""
    sql_files = sorted(SQL_DIR.glob("*.sql"))
    applied: list[str] = []
    own_conn = conn is None
    if own_conn:
        conn = psycopg.connect(
            get_database_url(),
            autocommit=True,
            cursor_factory=psycopg.ClientCursor,
        )
    assert conn is not None
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        rows = conn.execute("SELECT filename FROM public.schema_migrations").fetchall()
        done = {row[0] if not isinstance(row, dict) else row["filename"] for row in rows}
        for path in sql_files:
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO public.schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
            applied.append(path.name)
            logger.info("applied migration %s", path.name)
    finally:
        if own_conn:
            conn.close()
    return applied


def get_checkpointer():
    """LangGraph PostgresSaver bound to schema agent. Created once per process."""
    global _checkpointer, _checkpointer_pool
    if _checkpointer is not None:
        return _checkpointer
    from langgraph.checkpoint.postgres import PostgresSaver

    _checkpointer_pool = ConnectionPool(
        conninfo=get_database_url(),
        min_size=1,
        max_size=4,
        open=True,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": "-c search_path=agent,public",
        },
    )
    saver = PostgresSaver(_checkpointer_pool)
    saver.setup()
    _checkpointer = saver
    logger.info("PostgresSaver ready (search_path=agent)")
    return _checkpointer


def init_db(*, with_checkpointer: bool = True) -> None:
    """Connect, migrate, optionally set up LangGraph checkpoint tables."""
    global _initialized
    wait_for_postgres()
    apply_migrations()
    get_pool()
    if with_checkpointer:
        get_checkpointer()
    _initialized = True
    logger.info("database initialized")


def close_db() -> None:
    global _pool, _checkpointer_pool, _checkpointer, _initialized
    if _pool is not None:
        _pool.close()
        _pool = None
    if _checkpointer_pool is not None:
        _checkpointer_pool.close()
        _checkpointer_pool = None
    _checkpointer = None
    _initialized = False
