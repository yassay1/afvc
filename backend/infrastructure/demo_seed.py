"""Validate and atomically install the committed synthetic demo dataset once."""

from __future__ import annotations

import csv
import json

from backend.core.config import get_data_profile, get_database_url
from backend.infrastructure.db import get_pool
from backend.infrastructure.workorder_repo import import_dataframe, invalidate_workorder_cache
from backend.infrastructure.workorders import DEMO_WORKORDERS_FILE, read_workorder_file

MOCK = DEMO_WORKORDERS_FILE.parent
VERSION = 1


def _csv(name: str) -> list[dict[str, str]]:
    path = MOCK / name
    if not path.is_file():
        raise FileNotFoundError(f"demo 数据文件缺失：{path}")
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError(f"demo 数据文件为空：{path}")
    return rows


def validate_demo_dataset() -> list[dict]:
    """Fail closed before opening a DB connection or considering raw data."""
    workorders = _csv("workorders_demo.csv")
    risks = _csv("prediction_results.csv")
    faults = _csv("fault_prediction_results.csv")
    stations = _csv("station_importance.csv")
    crews = _csv("crew_availability.csv")
    parts = _csv("spare_parts.csv")
    task_path = MOCK / "maintenance_tasks_demo.json"
    if not task_path.is_file():
        raise FileNotFoundError(f"demo 任务文件缺失：{task_path}")
    task_data = json.loads(task_path.read_text(encoding="utf-8"))
    if task_data.get("version") != VERSION:
        raise ValueError("demo 任务版本不匹配")
    tasks = task_data["tasks"]
    assets = {r["assetnum"] for r in workorders}
    asset_stations = {r["assetnum"]: r["station_name"] for r in workorders}
    station_names = {r["station_name"] for r in stations}
    crew_ids = {r["crew_id"] for r in crews}
    if len(assets) < 30 or len(workorders) < 200 or len(tasks) < 12:
        raise ValueError("demo 数据量不足，设备/工单/任务种子不完整")
    if not all(a.startswith("DEMO-AGM-") for a in assets):
        raise ValueError("demo 工单含非合成设备编号")
    if {r["assetnum"] for r in risks} != assets:
        raise ValueError("demo 风险表与工单 assetnum 不一致")
    if {r["assetnum"] for r in faults} != assets:
        raise ValueError("demo 故障类型表与工单 assetnum 不一致")
    if len(risks) != len(assets) or len(faults) != len(assets) * 9:
        raise ValueError("demo 预测表存在重复或缺少设备/窗口")
    expected_fault_keys = {
        (asset, str(window)) for asset in assets for window in (7, 30, 90)
    }
    fault_keys = [(r["assetnum"], r["window_days"]) for r in faults]
    if set(fault_keys) != expected_fault_keys or any(fault_keys.count(key) != 3 for key in expected_fault_keys):
        raise ValueError("demo 故障类型预测窗口不完整")
    if any(r["station_name"] != asset_stations[r["assetnum"]] for r in workorders):
        raise ValueError("demo 设备站点引用不一致")
    if any(r["station_name"] not in station_names or not r["cust_linenum"] or not r["cust_brand"] for r in workorders):
        raise ValueError("demo 工单站点、线路或品牌引用不完整")
    if not parts or any(not r["part_code"].startswith("DEMO-PART-") for r in parts):
        raise ValueError("demo 备件数据不完整")
    if any(not r["crew_id"].startswith("DEMO-CREW-") for r in crews):
        raise ValueError("demo 班组编号不完整")
    if len({t["id"] for t in tasks}) != len(tasks) or any(
        t["assetnum"] not in assets or t["station_name"] != asset_stations[t["assetnum"]]
        or t["assignee_crew_id"] not in crew_ids or t["status"] not in {"planned", "in_progress", "done"}
        or (t["status"] == "done" and not t["feedback_result"])
        for t in tasks
    ):
        raise ValueError("demo 检修任务引用、状态或反馈不一致")
    return tasks


def seed_demo_if_needed() -> int:
    if get_data_profile() != "demo":
        raise RuntimeError("演示种子仅用于 demo profile")
    get_database_url()  # Validate the isolation boundary before obtaining a pool.
    tasks = validate_demo_dataset()
    frame = read_workorder_file(DEMO_WORKORDERS_FILE)
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(193879, 1)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS business.demo_dataset (
                    version INTEGER PRIMARY KEY,
                    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            installed = conn.execute("SELECT version FROM business.demo_dataset").fetchall()
            if installed:
                if len(installed) != 1 or installed[0]["version"] != VERSION:
                    raise RuntimeError("demo 数据库版本不匹配；请使用明确的演示重置流程")
                return 0
            workorder_count = conn.execute("SELECT COUNT(*) AS n FROM business.workorders").fetchone()["n"]
            task_count = conn.execute("SELECT COUNT(*) AS n FROM business.maintenance_tasks").fetchone()["n"]
            if workorder_count or task_count:
                raise RuntimeError("demo 数据库已有未标记的工单或任务，拒绝覆盖")
            import_dataframe(
                frame, source_filename=DEMO_WORKORDERS_FILE.name,
                stored_path="synthetic:v1", mode="append", conn=conn,
            )
            for task in tasks:
                conn.execute("""
                    INSERT INTO business.maintenance_tasks (
                        id, assetnum, station_name, fault_focus, priority, planned_date,
                        assignee_crew_id, status, suggestion_score, suggestion_reasons,
                        feedback_result, feedback_matched_fault, feedback_followed_suggestion,
                        feedback_note, feedback_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s
                    )
                """, (
                    task["id"], task["assetnum"], task["station_name"], task["fault_focus"],
                    task["priority"], task["planned_date"], task["assignee_crew_id"],
                    task["status"], task["suggestion_score"],
                    json.dumps(task["suggestion_reasons"], ensure_ascii=False),
                    task["feedback_result"], task["feedback_matched_fault"],
                    task["feedback_followed_suggestion"], task["feedback_note"],
                    task["feedback_at"],
                ))
            conn.execute("INSERT INTO business.demo_dataset (version) VALUES (%s)", (VERSION,))
    invalidate_workorder_cache()
    return len(tasks)
