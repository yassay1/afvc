"""封闭 Tool 注册表。Main Agent 看到的是具体能力，不是 data_op 枚举。"""

from __future__ import annotations

import json
from typing import Any

from functools import wraps

from langchain_core.tools import StructuredTool
from pydantic import ValidationError

from backend.agent.data_subgraph import invoke_data_capability
from backend.agent.runtime_context import get_thread_id
from backend.application import usecases
from backend.application.capabilities import CAPABILITIES, ToolTier, exposed_capability_names
from backend.application.approvals import propose_write
from backend.schemas.workorder_writes import (
    DeleteWorkorderInput,
    ImportWorkordersInput,
    InsertWorkorderInput,
    UpdateWorkorderInput,
)

TOOL_RESULT_CHAR_LIMIT = 12000
TOOL_REGISTRY = CAPABILITIES


def _risk_percent(value: Any) -> str | None:
    return f"{round(value * 100)}%" if isinstance(value, (int, float)) else None


def _friendly_suggestion_reason(reason: str) -> str:
    import re

    risk = re.match(r"^90 日复发风险\s+([0-9.]+)$", reason)
    if risk:
        return f"未来 90 天内再次出现故障工单的风险参考值为 {round(float(risk.group(1)) * 100)}%"
    history = re.match(r"^近史\s+(\d+)/(\d+)\s+条含「(.+)」$", reason)
    if history:
        return f"近 {history.group(2)} 条相关工单中，有 {history.group(1)} 条记录了“{history.group(3)}”现象"
    crew = re.match(r"^匹配班组\s+(.+?)（合成排班，非真实人员）$", reason)
    if crew:
        return f"演示排班建议班组为 {crew.group(1)}，安排前请核对现场班组"
    spare = re.match(r"^备件\s+(.+?)\s+库存\s+(\d+)（合成库存，非真实备件）$", reason)
    if spare:
        return f"演示库存显示 {spare.group(1)} 有 {spare.group(2)} 件，安排前请核对现场库存"
    if "虚构站点模拟权重" in reason:
        return "站点参考信息已纳入建议排序（体验数据）"
    if reason == "有可用检修班组（模拟）":
        return "演示排班显示有可用检修班组，请现场核实"
    if reason == "相关备件有库存（模拟）":
        return "演示库存显示有相关备件，请现场核实"
    return reason


def _risk_source_label(result: dict[str, Any]) -> str:
    source = result.get("prediction_source")
    if source == "external_prediction_csv":
        return "外部风险预测结果"
    if source == "statistical_baseline" or result.get("prediction_tier") == "statistical_baseline":
        return "基于历史工单的统计估算"
    return "接口未说明"


def _agent_risk_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "message": "设备风险参考已查询。",
        "assetnum": result.get("assetnum"),
        "station_name": result.get("station_name"),
        "line": result.get("line"),
        "risk_by_window": {
            "7 天": _risk_percent(result.get("risk_7d")),
            "14 天": _risk_percent(result.get("risk_14d")),
            "21 天": _risk_percent(result.get("risk_21d")),
            "30 天": _risk_percent(result.get("risk_30d")),
            "60 天": _risk_percent(result.get("risk_60d")),
            "90 天": _risk_percent(result.get("risk_90d")),
        },
        "warning_level": result.get("warning_level"),
        "suggested_inspection_window": result.get("suggested_inspection_window"),
        "warning_reason": result.get("warning_reason"),
        "data_source": _risk_source_label(result),
        "data_updated_at": "接口未提供更新时间",
        "risk_explanation": "风险表示未来对应时间窗内再次出现故障工单的参考可能性，不是故障发生日期。",
    }


def dumps_tool_result(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= TOOL_RESULT_CHAR_LIMIT:
        return text
    return text[:TOOL_RESULT_CHAR_LIMIT] + "…(truncated)"


def _domain_error_as_result(fn):
    """Return domain/validation errors to the model; do not crash the graph run."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, ValidationError) as exc:
            return dumps_tool_result({"ok": False, "error": str(exc)})

    return wrapped


def _proposal_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "executed": False,
        "status": action["status"],
        "action_id": action["action_id"],
        "summary": action["summary"],
        "message": (
            "操作尚未执行，已生成待审批单据。"
            "请用户在界面点击批准后才会写入数据库。"
            "用户说「好的 / 确认 / 行」不等于批准。"
        ),
    }


def _get_overview(top_n: int = 10) -> str:
    """查询当前工单工作集的数据概览：数量、站点/线路/品牌分布、时间范围。不需要设备编号。"""
    result = invoke_data_capability("get_overview", top_n=top_n)
    source = "当前接入的工单数据库" if result.get("data_backend") == "sql" else "当前接入的工单文件" if result.get("data_backend") == "file" else "接口未说明"
    visible = {key: value for key, value in result.items() if key not in {"current_file", "file_path", "data_backend"}}
    visible.update({"data_source": source, "data_updated_at": "接口未提供更新时间"})
    return dumps_tool_result(visible)


def _get_device_history(assetnum: str, limit: int = 20) -> str:
    """查询一台设备的历史工单（现象描述、时间、品牌/子系统等）。需要设备编号 assetnum。查不到时返回错误 JSON，不要因此中断。"""
    return dumps_tool_result(
        invoke_data_capability("get_device_history", assetnum=assetnum, limit=limit)
    )


def _list_high_risk(top_n: int = 10) -> str:
    """列出当前工作集中复发风险较高的设备，用于巡检优先级。不需要设备编号。"""
    result = usecases.list_high_risk_devices(top_n=top_n)
    devices = []
    for device in result.get("devices") or []:
        devices.append({
            "assetnum": device.get("assetnum"),
            "station_name": device.get("station_name"),
            "line": device.get("line"),
            "risk_by_window": {
                "30 天": _risk_percent(device.get("risk_30d")),
                "90 天": _risk_percent(device.get("risk_90d")),
            },
            "warning_level": device.get("warning_level"),
            "suggested_inspection_window": device.get("suggested_inspection_window"),
        })
    return dumps_tool_result({
        "status": result.get("status"),
        "message": "高风险设备参考列表已查询。",
        "devices": devices,
        "data_source": _risk_source_label(result),
        "data_updated_at": "接口未提供更新时间",
        "risk_explanation": "风险表示未来对应时间窗内再次出现故障工单的参考可能性，不是故障发生日期。",
    })


def _predict_device_risk(assetnum: str) -> str:
    """预测一台设备在未来窗口内再次产生故障工单的风险。需要设备编号。风险不是故障日期。"""
    return dumps_tool_result(_agent_risk_result(usecases.predict_device_risk(assetnum=assetnum)))


def _predict_fault_type(assetnum: str, window_days: int = 30) -> str:
    """给出一台设备在窗口内的故障类型参考（条件概率，不是必然发生）。需要设备编号。"""
    return dumps_tool_result(
        usecases.predict_fault_type(assetnum=assetnum, window_days=window_days)
    )


def _advise_maintenance(assetnum: str) -> str:
    """根据历史工单现象给出巡检/维修建议方向（单设备 SOP 向）。需要设备编号。不是今日检修排序清单；建议不是根因结论。"""
    return dumps_tool_result(usecases.advise_maintenance(assetnum=assetnum))


def _list_maintenance_suggestions(top_n: int = 10, fault_focus: str = "暂停服务") -> str:
    """查询已排好顺序的检修建议及人员可以理解的依据。保持返回顺序，不要自行调整优先级。"""
    result = usecases.list_maintenance_suggestions(top_n=top_n, fault_focus=fault_focus)
    source_note = str(result.get("model_note") or "")
    if "prediction_results.csv" in source_note:
        risk_source = "外部风险预测结果；接口未提供更新时间"
    elif "统计基线" in source_note:
        risk_source = "基于历史工单的统计估算；接口未提供更新时间"
    else:
        risk_source = "接口未说明风险来源和更新时间"
    visible_suggestions = []
    for row in result.get("suggestions") or []:
        visible_suggestions.append({
            "assetnum": row.get("assetnum"),
            "station_name": row.get("station_name"),
            "fault_focus": row.get("fault_focus"),
            "warning_level": row.get("warning_level"),
            "risk_90d": _risk_percent(row.get("risk_90d")),
            "reasons": [_friendly_suggestion_reason(str(reason)) for reason in row.get("reasons") or []],
        })
    visible = {
        "status": result.get("status"),
        "message": "检修建议已生成。",
        "fault_focus": result.get("fault_focus"),
        "suggestions": visible_suggestions,
        "order_note": "以下顺序由服务端提供，请保持原顺序。",
        "suggestion_generated_at": "接口未提供建议生成时间",
        "risk_data_source": risk_source,
    }
    if any("模拟" in str(row.get("data_note") or "") for row in result.get("suggestions") or []):
        visible["resource_data_note"] = "人员、备件和站点参考信息为体验数据，不代表现场排班或库存；安排前请核实现场情况。"
    return dumps_tool_result(visible)


def _list_maintenance_tasks(status: str | None = None) -> str:
    """列出检修任务（planned / in_progress / done / cancelled）。与工单 pending_actions 不是同一条线。"""
    return dumps_tool_result(usecases.list_maintenance_tasks(status=status))


def _search_manual(query: str, assetnum: str | None = None) -> str:
    """检索维修手册片段。query 为故障现象或关键词；设备编号可选，用于收窄。"""
    return dumps_tool_result(usecases.search_manual(query=query, assetnum=assetnum))


def _diagnose_device(assetnum: str) -> str:
    """综合诊断快捷工具：一次聚合历史、风险、建议、故障类型。需要设备编号。若只要其中一项，请改用对应原子工具。"""
    return dumps_tool_result(usecases.diagnose_device(assetnum=assetnum))


def _insert_workorder(
    assetnum: str,
    station_name: str | None = None,
    cust_linenum: str | None = None,
    current_faildate: str | None = None,
    prev_faildate: str | None = None,
    total_failure_count: str | None = None,
    description: str | None = None,
    cust_brand: str | None = None,
    cust_subsys: str | None = None,
    worktype: str | None = None,
    pre_type: str | None = None,
    pre_value: str | None = None,
) -> str:
    """提案：新增一条工单。最少只需 assetnum，其他字段可选、缺省可留空。不要为补全可选字段先查历史。不会立即写库，需用户在界面显式批准。不要自行编造 action_id。"""
    payload = InsertWorkorderInput(
        assetnum=assetnum,
        station_name=station_name,
        cust_linenum=cust_linenum,
        current_faildate=current_faildate,
        prev_faildate=prev_faildate,
        total_failure_count=total_failure_count,
        description=description,
        cust_brand=cust_brand,
        cust_subsys=cust_subsys,
        worktype=worktype,
        pre_type=pre_type,
        pre_value=pre_value,
    ).model_dump(exclude_none=True)
    action = propose_write(thread_id=get_thread_id(), tool_name="insert_workorder", payload=payload)
    return dumps_tool_result(_proposal_payload(action))


def _update_workorder(
    workorder_id: str,
    assetnum: str | None = None,
    station_name: str | None = None,
    cust_linenum: str | None = None,
    current_faildate: str | None = None,
    prev_faildate: str | None = None,
    total_failure_count: str | None = None,
    description: str | None = None,
    cust_brand: str | None = None,
    cust_subsys: str | None = None,
    worktype: str | None = None,
    pre_type: str | None = None,
    pre_value: str | None = None,
) -> str:
    """提案：按工单 ID 更新业务字段。不会立即写库，需界面显式批准。workorder_id 来自历史查询。"""
    payload = UpdateWorkorderInput(
        workorder_id=workorder_id,
        assetnum=assetnum,
        station_name=station_name,
        cust_linenum=cust_linenum,
        current_faildate=current_faildate,
        prev_faildate=prev_faildate,
        total_failure_count=total_failure_count,
        description=description,
        cust_brand=cust_brand,
        cust_subsys=cust_subsys,
        worktype=worktype,
        pre_type=pre_type,
        pre_value=pre_value,
    ).model_dump(exclude_none=True)
    action = propose_write(thread_id=get_thread_id(), tool_name="update_workorder", payload=payload)
    return dumps_tool_result(_proposal_payload(action))


def _delete_workorder(workorder_id: str) -> str:
    """提案：按工单 ID 删除一条工单。不会立即写库，需界面显式批准。"""
    payload = DeleteWorkorderInput(workorder_id=workorder_id).model_dump()
    action = propose_write(thread_id=get_thread_id(), tool_name="delete_workorder", payload=payload)
    return dumps_tool_result(_proposal_payload(action))


def _import_workorders(source_filename: str, mode: str = "replace") -> str:
    """提案：将 raw 目录中已有 Excel/CSV 导入工单库。不会立即写库，需界面显式批准。mode 为 replace 或 append。"""
    payload = ImportWorkordersInput(source_filename=source_filename, mode=mode).model_dump()
    action = propose_write(thread_id=get_thread_id(), tool_name="import_workorders", payload=payload)
    return dumps_tool_result(_proposal_payload(action))


_TOOL_BUILDERS = {
    "get_overview": lambda: StructuredTool.from_function(
        _domain_error_as_result(_get_overview), name="get_overview"
    ),
    "get_device_history": lambda: StructuredTool.from_function(
        _domain_error_as_result(_get_device_history), name="get_device_history"
    ),
    "list_high_risk": lambda: StructuredTool.from_function(
        _domain_error_as_result(_list_high_risk), name="list_high_risk"
    ),
    "list_maintenance_suggestions": lambda: StructuredTool.from_function(
        _domain_error_as_result(_list_maintenance_suggestions),
        name="list_maintenance_suggestions",
    ),
    "list_maintenance_tasks": lambda: StructuredTool.from_function(
        _domain_error_as_result(_list_maintenance_tasks),
        name="list_maintenance_tasks",
    ),
    "predict_device_risk": lambda: StructuredTool.from_function(
        _domain_error_as_result(_predict_device_risk), name="predict_device_risk"
    ),
    "predict_fault_type": lambda: StructuredTool.from_function(
        _domain_error_as_result(_predict_fault_type), name="predict_fault_type"
    ),
    "advise_maintenance": lambda: StructuredTool.from_function(
        _domain_error_as_result(_advise_maintenance), name="advise_maintenance"
    ),
    "search_manual": lambda: StructuredTool.from_function(
        _domain_error_as_result(_search_manual), name="search_manual"
    ),
    "diagnose_device": lambda: StructuredTool.from_function(
        _domain_error_as_result(_diagnose_device), name="diagnose_device"
    ),
    "insert_workorder": lambda: StructuredTool.from_function(
        _domain_error_as_result(_insert_workorder), name="insert_workorder"
    ),
    "update_workorder": lambda: StructuredTool.from_function(
        _domain_error_as_result(_update_workorder), name="update_workorder"
    ),
    "delete_workorder": lambda: StructuredTool.from_function(
        _domain_error_as_result(_delete_workorder), name="delete_workorder"
    ),
    "import_workorders": lambda: StructuredTool.from_function(
        _domain_error_as_result(_import_workorders), name="import_workorders"
    ),
}


def build_exposed_tools() -> list[StructuredTool]:
    tools: list[StructuredTool] = []
    for name in exposed_capability_names():
        builder = _TOOL_BUILDERS.get(name)
        if builder is not None:
            tools.append(builder())
    return tools


TOOL_TO_USE_CASE = {
    "get_overview": "get_data_overview",
    "get_device_history": "get_device_history",
    "list_high_risk": "list_high_risk_devices",
    "list_maintenance_suggestions": "list_maintenance_suggestions",
    "list_maintenance_tasks": "list_maintenance_tasks",
    "predict_device_risk": "predict_device_risk",
    "predict_fault_type": "predict_fault_type",
    "advise_maintenance": "advise_maintenance",
    "search_manual": "search_manual",
    "diagnose_device": "diagnose_device",
    "insert_workorder": "insert_workorder",
    "update_workorder": "update_workorder",
    "delete_workorder": "delete_workorder",
    "import_workorders": "import_workorders",
}


def sensitive_tool_names() -> list[str]:
    return exposed_capability_names(tier=ToolTier.SENSITIVE)
