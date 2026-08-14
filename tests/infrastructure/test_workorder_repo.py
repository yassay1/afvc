"""Workorder SQL repository tests. Skipped when emergency file backend is on."""

from __future__ import annotations

import pytest

from backend.core.config import is_sql_backend
from backend.infrastructure.workorder_repo import (
    count_workorders,
    delete_workorder,
    get_workorder,
    insert_workorder,
    list_workorders_by_assetnum,
    update_workorder,
)
from backend.infrastructure.workorders import read_workorder_file
from backend.application.overview import get_data_overview

pytestmark = pytest.mark.skipif(not is_sql_backend(), reason="Postgres 不可用，跳过 SQL 仓储测试")


def test_working_set_has_seeded_rows():
    assert count_workorders() > 1000


def test_overview_counts_match_excel_source():
    file_df = read_workorder_file()
    overview = get_data_overview(top_n=5)
    metrics = overview["basic_metrics"]
    assert metrics["workorder_count"] == file_df.height
    assert metrics["device_count"] == file_df["assetnum"].n_unique()
    assert overview.get("data_backend") == "sql"


def test_crud_insert_update_delete_roundtrip():
    leftover = list_workorders_by_assetnum("TEST-CRUD-001", limit=50)
    for row in leftover:
        delete_workorder(str(row["id"]))

    workorder_id = None
    try:
        created = insert_workorder(
            {
                "assetnum": "TEST-CRUD-001",
                "station_name": "测试站",
                "cust_linenum": "L01",
                "description": "仓储 CRUD 探针",
                "cust_brand": "测试品牌",
            }
        )
        workorder_id = str(created["id"])
        fetched = get_workorder(workorder_id)
        assert fetched is not None
        assert fetched["assetnum"] == "TEST-CRUD-001"

        listed = list_workorders_by_assetnum("TEST-CRUD-001", limit=5)
        assert any(str(row["id"]) == workorder_id for row in listed)

        updated = update_workorder(workorder_id, {"description": "已更新探针"})
        assert updated["description"] == "已更新探针"
        deleted = delete_workorder(workorder_id)
        assert deleted["deleted"] is True
        workorder_id = None
    finally:
        if workorder_id:
            delete_workorder(workorder_id)


def test_delete_missing_workorder_raises():
    with pytest.raises(ValueError, match="工单不存在"):
        delete_workorder("00000000-0000-0000-0000-000000000000")
