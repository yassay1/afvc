"""Row-level workorder repository. PostgreSQL is the business source of truth."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import polars as pl

from backend.infrastructure.db import get_pool

logger = logging.getLogger("afvc.workorder_repo")

WORKORDER_COLUMNS = [
    "assetnum",
    "station_name",
    "cust_linenum",
    "current_faildate",
    "prev_faildate",
    "total_failure_count",
    "description",
    "cust_brand",
    "cust_subsys",
    "worktype",
    "pre_type",
    "pre_value",
]

DEFAULT_DATA_FILE = "afc非首次故障-L01线.xlsx"

_df_caches: dict[bool, pl.DataFrame] = {}


def invalidate_workorder_cache() -> None:
    _df_caches.clear()


def _to_sql_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, bool):
        return str(value)
    if hasattr(value, "isoformat"):
        text = value.isoformat(sep=" ")
        return text.replace("T", " ")
    text = str(value).strip()
    return text if text else None


def _row_from_mapping(row: dict[str, Any]) -> dict[str, str | None]:
    return {column: _to_sql_value(row.get(column)) for column in WORKORDER_COLUMNS}


def count_workorders() -> int:
    with get_pool().connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM business.workorders").fetchone()
        return int(row["n"] if isinstance(row, dict) else row[0])


def get_latest_import_batch() -> dict[str, Any] | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT id, source_filename, stored_path, mode, row_count, created_at, actor_id
            FROM business.import_batches
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row is not None else None


def get_data_source_info() -> dict[str, Any]:
    """Label the current working set by the batch that owns the most live rows."""
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT b.id, b.source_filename, b.stored_path, b.mode, b.row_count
            FROM business.workorders w
            JOIN business.import_batches b ON b.id = w.import_batch_id
            GROUP BY b.id, b.source_filename, b.stored_path, b.mode, b.row_count
            ORDER BY COUNT(*) DESC, b.created_at DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        batch = get_latest_import_batch()
        if batch is None:
            return {
                "current_file": "business.workorders",
                "file_path": "postgresql:business.workorders",
                "backend": "sql",
                "import_batch_id": None,
            }
        row = batch
    payload = dict(row)
    return {
        "current_file": payload["source_filename"],
        "file_path": payload.get("stored_path") or "postgresql:business.workorders",
        "backend": "sql",
        "import_batch_id": str(payload["id"]),
    }


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(row).items():
        if hasattr(value, "hex") and not isinstance(value, str):
            out[key] = str(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _returning_sql() -> str:
    return """
        id, import_batch_id, assetnum, station_name, cust_linenum,
        current_faildate, prev_faildate, total_failure_count, description,
        cust_brand, cust_subsys, worktype, pre_type, pre_value,
        created_at, updated_at, actor_id
    """


def fetch_all_as_dataframe(*, include_id: bool = False) -> pl.DataFrame:
    """Return the working set as a Polars frame with the original Excel column names."""
    cached = _df_caches.get(include_id)
    if cached is not None:
        return cached
    if include_id:
        columns_sql = "id::text AS workorder_id, " + ", ".join(WORKORDER_COLUMNS)
        schema_names = ["workorder_id", *WORKORDER_COLUMNS]
    else:
        columns_sql = ", ".join(WORKORDER_COLUMNS)
        schema_names = list(WORKORDER_COLUMNS)
    with get_pool().connection() as conn:
        rows = conn.execute(
            f"SELECT {columns_sql} FROM business.workorders"
        ).fetchall()
    records = [dict(row) for row in rows]
    if records:
        frame = pl.DataFrame(records)
    else:
        frame = pl.DataFrame(schema={column: pl.Utf8 for column in schema_names})
    _df_caches[include_id] = frame
    return frame


def get_workorder(workorder_id: str, conn=None) -> dict[str, Any] | None:
    sql = f"SELECT {_returning_sql()} FROM business.workorders WHERE id = %s"

    def _fetch(connection) -> dict[str, Any] | None:
        row = connection.execute(sql, (workorder_id,)).fetchone()
        return _serialize_row(row) if row is not None else None

    if conn is not None:
        return _fetch(conn)
    with get_pool().connection() as owned:
        return _fetch(owned)


def list_workorders_by_assetnum(assetnum: str, *, limit: int = 50) -> list[dict[str, Any]]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT id, assetnum, station_name, cust_linenum, current_faildate,
                   prev_faildate, total_failure_count, description, cust_brand,
                   cust_subsys, worktype, pre_type, pre_value
            FROM business.workorders
            WHERE assetnum = %s
            ORDER BY current_faildate DESC NULLS LAST
            LIMIT %s
            """,
            (assetnum.strip(), limit),
        ).fetchall()
        return [_serialize_row(row) for row in rows]


def _insert_on_connection(
    conn,
    payload: dict[str, str | None],
    *,
    actor_id: str | None,
    import_batch_id: str | None,
) -> dict[str, Any]:
    batch_id = import_batch_id or _ensure_manual_batch(conn, actor_id=actor_id)
    row = conn.execute(
        f"""
        INSERT INTO business.workorders (
            import_batch_id, assetnum, station_name, cust_linenum,
            current_faildate, prev_faildate, total_failure_count, description,
            cust_brand, cust_subsys, worktype, pre_type, pre_value, actor_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING {_returning_sql()}
        """,
        (
            batch_id,
            payload["assetnum"],
            payload["station_name"],
            payload["cust_linenum"],
            payload["current_faildate"],
            payload["prev_faildate"],
            payload["total_failure_count"],
            payload["description"],
            payload["cust_brand"],
            payload["cust_subsys"],
            payload["worktype"],
            payload["pre_type"],
            payload["pre_value"],
            actor_id,
        ),
    ).fetchone()
    assert row is not None
    return _serialize_row(row)


def insert_workorder(
    fields: dict[str, Any],
    *,
    actor_id: str | None = None,
    import_batch_id: str | None = None,
    conn=None,
) -> dict[str, Any]:
    payload = _row_from_mapping(fields)
    if conn is not None:
        return _insert_on_connection(
            conn, payload, actor_id=actor_id, import_batch_id=import_batch_id
        )
    with get_pool().connection() as owned:
        with owned.transaction():
            row = _insert_on_connection(
                owned, payload, actor_id=actor_id, import_batch_id=import_batch_id
            )
    invalidate_workorder_cache()
    return row


def update_workorder(
    workorder_id: str,
    fields: dict[str, Any],
    conn=None,
) -> dict[str, Any]:
    allowed = {key: _to_sql_value(value) for key, value in fields.items() if key in WORKORDER_COLUMNS}
    if not allowed:
        raise ValueError("没有可更新的工单字段")
    assignments = ", ".join(f"{key} = %s" for key in allowed)
    values = list(allowed.values()) + [workorder_id]
    sql = f"""
        UPDATE business.workorders
        SET {assignments}, updated_at = NOW()
        WHERE id = %s
        RETURNING {_returning_sql()}
    """

    def _update(connection) -> dict[str, Any]:
        row = connection.execute(sql, values).fetchone()
        if row is None:
            raise ValueError(f"工单不存在：{workorder_id}")
        return _serialize_row(row)

    if conn is not None:
        return _update(conn)
    with get_pool().connection() as owned:
        row = _update(owned)
        owned.commit()
    invalidate_workorder_cache()
    return row


def delete_workorder(workorder_id: str, conn=None) -> dict[str, Any]:
    sql = "DELETE FROM business.workorders WHERE id = %s RETURNING id"

    def _delete(connection) -> dict[str, Any]:
        row = connection.execute(sql, (workorder_id,)).fetchone()
        if row is None:
            raise ValueError(f"工单不存在：{workorder_id}")
        deleted_id = row["id"] if isinstance(row, dict) else row[0]
        return {"deleted": True, "workorder_id": str(deleted_id)}

    if conn is not None:
        return _delete(conn)
    with get_pool().connection() as owned:
        result = _delete(owned)
        owned.commit()
    invalidate_workorder_cache()
    return result


def import_dataframe(
    df: pl.DataFrame,
    *,
    source_filename: str,
    stored_path: str | None,
    mode: str = "replace",
    actor_id: str | None = None,
    conn=None,
) -> dict[str, Any]:
    if mode not in {"replace", "append"}:
        raise ValueError("import mode 必须是 replace 或 append")

    records = [_row_from_mapping(row) for row in df.to_dicts()]
    batch_id = uuid.uuid4()
    copy_columns = ["import_batch_id", *WORKORDER_COLUMNS, "actor_id"]

    def _import(connection) -> None:
        if mode == "replace":
            connection.execute("DELETE FROM business.workorders")
        connection.execute(
            """
            INSERT INTO business.import_batches (
                id, source_filename, stored_path, mode, row_count, actor_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(batch_id), source_filename, stored_path, mode, len(records), actor_id),
        )
        with connection.cursor() as cur:
            with cur.copy(
                f"COPY business.workorders ({', '.join(copy_columns)}) FROM STDIN"
            ) as copy:
                for record in records:
                    copy.write_row(
                        (
                            str(batch_id),
                            *[record[column] for column in WORKORDER_COLUMNS],
                            actor_id,
                        )
                    )

    if conn is not None:
        _import(conn)
    else:
        with get_pool().connection() as owned:
            with owned.transaction():
                _import(owned)
        invalidate_workorder_cache()

    logger.info(
        "imported %s rows from %s mode=%s batch=%s",
        len(records),
        source_filename,
        mode,
        batch_id,
    )
    return {
        "status": "success",
        "import_batch_id": str(batch_id),
        "source_filename": source_filename,
        "stored_path": stored_path,
        "mode": mode,
        "row_count": len(records),
    }


def import_from_path(
    path: Path,
    *,
    mode: str = "replace",
    actor_id: str | None = None,
    conn=None,
) -> dict[str, Any]:
    from backend.infrastructure.workorders import read_workorder_file

    df = read_workorder_file(path)
    return import_dataframe(
        df,
        source_filename=path.name,
        stored_path=str(path),
        mode=mode,
        actor_id=actor_id,
        conn=conn,
    )


def seed_default_if_empty() -> dict[str, Any] | None:
    from backend.core.config import get_data_profile

    if count_workorders() > 0:
        return None
    data_root = Path(__file__).resolve().parent.parent / "data"
    default_path = data_root / "raw" / DEFAULT_DATA_FILE
    demo_path = data_root / "mock" / "workorders_demo.csv"
    seed_path = demo_path if get_data_profile() == "demo" else default_path
    if not seed_path.exists():
        raise FileNotFoundError(f"{get_data_profile()} 工单种子缺失：{seed_path}")
    logger.info("seeding empty workorders table from %s", seed_path.name)
    return import_from_path(seed_path, mode="replace")


def _ensure_manual_batch(conn, *, actor_id: str | None) -> str:
    row = conn.execute(
        """
        SELECT id FROM business.import_batches
        WHERE source_filename = 'manual_insert'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is not None:
        return str(row["id"] if isinstance(row, dict) else row[0])
    batch_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO business.import_batches (
            id, source_filename, stored_path, mode, row_count, actor_id
        )
        VALUES (%s, 'manual_insert', NULL, 'append', 0, %s)
        """,
        (str(batch_id), actor_id),
    )
    return str(batch_id)
