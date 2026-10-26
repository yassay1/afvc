"""叙述层 —— LLM 优先，将用例结构化结果写成可读答复；模板作为兜底。"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.core.config import is_llm_enabled

logger = logging.getLogger("afvc.narrate")

SCIENTIFIC_BOUNDARY = (
    "科学边界说明：\n"
    "- 风险预测表示未来时间窗口内再次产生故障工单的风险，不等同于一定发生物理故障。\n"
    "- 单设备巡检建议（advise）是历史现象参考，不是最终根因结论。\n"
    "- 最终维修判断需结合现场检测、设备日志和人工经验。"
)

CAPABILITY_TEXT = (
    "我是 AFC 闸机检修助手，可以帮你：\n"
    "- 查看检修建议与跟进检修任务\n"
    "- 工单概览、高风险设备、单设备历史 / 风险 / 故障类型\n"
    "- 单设备巡检方向、手册检索；综合诊断为设备快捷聚合\n"
    "例：查询检修建议 / 当前有哪些检修任务？ / 分析设备 1000029970"
)

CHAT_TEXT = (
    "你好。我可以协助 AFC 闸机检修安排与设备分析。"
    "可问检修建议、检修任务、工单概览或设备风险，也可以提供设备编号查询单台设备。"
)

REJECTED_TEXT = (
    "该问题超出 AFC 闸机检修与设备分析范围。"
    "我只能协助检修建议与任务查询、工单分析、风险预警、巡检参考与手册检索等。"
)

EXPLANATION_TEXT = (
    "风险数值表示在给定时间窗口内再次产生故障工单的可能性，"
    "不是「一定发生」或具体故障日期。"
    "维修建议只是巡检方向，不能替代现场根因鉴定。\n\n"
    + SCIENTIFIC_BOUNDARY
)

CLARIFY_ASSET_TEXT = (
    "请补充设备编号后再继续，例如：\n"
    "- 帮我分析设备 1000029970\n"
    "- 设备 EX011115 最近有哪些故障？\n"
    "- 1000029970 未来 30 天风险高吗？"
)


def narrate_static(kind: str) -> str:
    """闲聊 / 能力 / 拒绝 / 解释 / 澄清 的固定话术。"""
    mapping = {
        "chat": CHAT_TEXT,
        "capability": CAPABILITY_TEXT,
        "rejected": REJECTED_TEXT,
        "explanation": EXPLANATION_TEXT,
        "clarified": CLARIFY_ASSET_TEXT,
    }
    return mapping.get(kind, CHAT_TEXT)


# chat / explanation 属于对话性文本，LLM 可用时用模型生成更自然的答复；
# capability / clarified / rejected 是能力边界与澄清提示，属于护栏文案，保持固定。
_LLM_STATIC_KINDS = {"chat", "explanation"}

_STATIC_SYSTEM_PROMPT = (
    "你是地铁 AFC 闸机检修助手。请用简洁、友好、专业的中文回应用户，"
    "并把话题引导回：检修建议、检修任务查询、工单概览、高风险设备、"
    "设备历史与风险、单设备巡检参考、故障类型、手册检索。硬性要求：\n"
    "1. 不承诺超出上述范围的能力，不编造设备、数值或结论；\n"
    "2. 风险是未来窗口内再次产生故障工单的可能性，不等于精确故障日期；"
    "检修建议顺序不得由对话重排；单设备巡检建议不是最终根因；\n"
    "3. 输出纯文本，简短即可（3~5 句以内）。"
)


def _llm_static(kind: str, query: str) -> str | None:
    """chat / explanation 的 LLM 生成；失败返回 None 由调用方兜底。"""
    try:
        from backend.core.llm import get_conversation_llm

        llm = get_conversation_llm()
        intent = "日常寒暄或简单交流" if kind == "chat" else "解释风险/概率/建议等概念的含义与边界"
        user_content = (
            f"用户消息：{query}\n"
            f"你的任务：{intent}。请遵守能力边界与科学边界。"
        )
        response = llm.invoke(
            [
                ("system", _STATIC_SYSTEM_PROMPT),
                ("human", user_content),
            ]
        )
        text = _extract_llm_text(response)
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM 静态叙述失败，回退固定话术：%s", exc)
        return None


def narrate_reply(kind: str, query: str = "") -> str:
    """非用例分支的答复：chat/explanation 优先走 LLM，其余用固定话术。"""
    if is_llm_enabled() and kind in _LLM_STATIC_KINDS:
        text = _llm_static(kind, query)
        if text:
            return text
    return narrate_static(kind)


def _fmt(value: Any, default: str = "数据缺失") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _append_list(lines: list[str], title: str, items: list[Any] | None) -> None:
    lines.append("")
    lines.append(title)
    if not items:
        lines.append("- 暂无数据")
        return
    for item in items:
        lines.append(f"- {item}")


def _human_suggestion_reason(reason: str) -> str:
    import re

    risk = re.match(r"^90 日复发风险\s+([0-9.]+)$", reason)
    if risk:
        try:
            return f"未来 90 天内再次出现故障工单的风险参考值为 {round(float(risk.group(1)) * 100)}%"
        except ValueError:
            return "未来 90 天内再次出现故障工单的风险参考值"
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
    return "服务端提供了其他排序依据"


def _task_status_label(status: Any) -> str:
    return {
        "planned": "待执行",
        "in_progress": "执行中",
        "done": "已完成",
        "cancelled": "已取消",
    }.get(status, _fmt(status))


def _risk_label(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return _fmt(value)
    return f"{round(value * 100)}%"


def narrate_overview(result: dict[str, Any]) -> str:
    basic = result.get("basic_metrics", {}) or {}
    time_range = result.get("time_range", {}) or {}
    lines = [
        "【AFC 工单数据概览】",
        "",
        "一、基础指标",
        f"- 工单总数：{_fmt(basic.get('workorder_count'))}",
        f"- 设备数量：{_fmt(basic.get('device_count'))}",
        f"- 车站数量：{_fmt(basic.get('station_count'))}",
        f"- 线路数量：{_fmt(basic.get('line_count'))}",
        f"- 品牌数量：{_fmt(basic.get('brand_count'))}",
        "",
        "二、时间范围",
        f"- 起始时间：{_fmt(time_range.get('start_time'))}",
        f"- 结束时间：{_fmt(time_range.get('end_time'))}",
        "",
        f"数据来源：{'当前接入的工单文件' if result.get('data_backend') == 'file' else '当前接入的工单数据库' if result.get('data_backend') == 'sql' else '接口未说明'}。",
        "接口未提供数据更新时间。",
        "",
        SCIENTIFIC_BOUNDARY,
    ]
    return "\n".join(lines)


def narrate_high_risk(result: dict[str, Any]) -> str:
    devices = result.get("devices", []) or []
    lines = [
        "【高风险设备巡检清单】",
        "",
        f"共 {len(devices)} 台高风险设备需要优先关注：",
    ]
    for i, device in enumerate(devices, 1):
        lines.extend(
            [
                "",
                f"{i}. 设备 {_fmt(device.get('assetnum'))}",
                f"- 车站：{_fmt(device.get('station_name'))}　线路：{_fmt(device.get('line'))}",
                f"- 30 天内再次出现故障工单的风险：{_risk_label(device.get('risk_30d'))}　90 天：{_risk_label(device.get('risk_90d'))}",
                f"- 预警等级：{_fmt(device.get('warning_level'))}",
                f"- 建议巡检窗口：{_fmt(device.get('suggested_inspection_window'))}",
            ]
        )
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_maintenance_suggestions(result: dict[str, Any]) -> str:
    suggestions = result.get("suggestions") or []
    focus = result.get("fault_focus") or "暂停服务"
    lines = [
        "【检修建议】",
        "",
        f"故障焦点：{focus}",
        f"共 {len(suggestions)} 条，按服务端提供的顺序列出：",
    ]
    for i, row in enumerate(suggestions, 1):
        reasons = row.get("reasons") or []
        reason_preview = "；".join(_human_suggestion_reason(str(r)) for r in reasons[:3]) if reasons else "暂无可展示的依据"
        lines.extend(
            [
                "",
                f"{i}. 设备 {_fmt(row.get('assetnum'))}　车站 {_fmt(row.get('station_name'))}",
                f"- 建议依据：{reason_preview}",
            ]
        )
    source_note = str(result.get("model_note") or "")
    if "prediction_results.csv" in source_note:
        lines.extend(["", "风险参考来自外部预测结果；接口未提供该数据的更新时间。"])
    elif "统计基线" in source_note:
        lines.extend(["", "风险参考根据历史工单频次和复发间隔估算；接口未提供该数据的更新时间。"])
    elif source_note:
        lines.extend(["", "接口未说明风险数据的具体来源和更新时间。"])
    if any("模拟" in str(row.get("data_note") or "") for row in suggestions):
        lines.extend(["", "人员、备件和站点参考信息为体验数据，安排前请核实现场情况。"])
    lines.extend(
        [
            "",
            SCIENTIFIC_BOUNDARY,
        ]
    )
    return "\n".join(lines)


def narrate_maintenance_tasks(result: dict[str, Any]) -> str:
    tasks = result.get("tasks") or []
    lines = [
        "【检修任务列表】",
        "",
        f"共 {result.get('count', len(tasks))} 条：",
    ]
    if not tasks:
        lines.append("- 暂无检修任务")
    else:
        for i, task in enumerate(tasks[:20], 1):
            lines.extend(
                [
                    "",
                    f"{i}. {_fmt(task.get('id'))}　设备 {_fmt(task.get('assetnum'))}",
                    f"- 状态：{_task_status_label(task.get('status'))}　优先级：{_fmt(task.get('priority'))}",
                    f"- 计划日：{_fmt(task.get('planned_date'), '未定')}　班组：{_fmt(task.get('assignee_crew_id'), '未指定')}",
                ]
            )
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_history(result: dict[str, Any]) -> str:
    history = result.get("history", []) or []
    lines = [
        "【设备历史工单摘要】",
        "",
        f"设备编号：{_fmt(result.get('assetnum'))}",
        f"返回工单数：{_fmt(result.get('history_count'))}",
        "",
        "最近工单：",
    ]
    if not history:
        lines.append("- 暂无明细")
    else:
        for i, row in enumerate(history[:5], 1):
            lines.append(
                f"{i}. {_fmt(row.get('current_faildate'), '时间缺失')} | "
                f"{_fmt(row.get('worktype'), '类型缺失')} | "
                f"{_fmt(row.get('description'), '描述缺失')}"
            )
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_risk(result: dict[str, Any]) -> str:
    lines = [
        "【设备复发风险预测】",
        "",
        f"设备编号：{_fmt(result.get('assetnum'))}",
        f"车站：{_fmt(result.get('station_name'))}",
        f"线路：{_fmt(result.get('line'))}",
        f"品牌：{_fmt(result.get('brand'))}",
        "",
        "复发风险：",
        f"- 7 天：{_risk_label(result.get('risk_7d'))}",
        f"- 14 天：{_risk_label(result.get('risk_14d'))}",
        f"- 21 天：{_risk_label(result.get('risk_21d'))}",
        f"- 30 天：{_risk_label(result.get('risk_30d'))}",
        f"- 60 天：{_risk_label(result.get('risk_60d'))}",
        f"- 90 天：{_risk_label(result.get('risk_90d'))}",
        "",
        f"预警等级：{_fmt(result.get('warning_level'))}",
        f"建议巡检窗口：{_fmt(result.get('suggested_inspection_window'))}",
        f"预警原因：{_fmt(result.get('warning_reason'))}",
    ]
    factors = result.get("main_risk_factors") or []
    if factors:
        _append_list(lines, "主要风险因素：", factors)
    statement = result.get("risk_statement")
    if statement:
        lines.extend(["", str(statement)])
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_advice(result: dict[str, Any]) -> str:
    lines = [
        "【维修与巡检建议】",
        "",
        f"设备编号：{_fmt(result.get('assetnum'))}",
    ]
    _append_list(lines, "识别到的故障现象：", result.get("recognized_fault_phenomena") or [])
    _append_list(lines, "可能原因：", result.get("possible_causes") or [])
    _append_list(lines, "建议检查方向：", result.get("inspection_suggestions") or [])
    _append_list(lines, "备件准备建议：", result.get("spare_part_suggestions") or [])
    note = result.get("advice_note")
    if note:
        lines.extend(["", f"注意事项：{note}"])
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_manual(result: dict[str, Any]) -> str:
    hits = result.get("results") or result.get("hits") or result.get("documents") or []
    lines = ["【维修手册检索结果】", ""]
    if not hits:
        lines.append("未检索到可追溯的手册条目。请换关键词或补充设备子系统信息。")
    else:
        for i, hit in enumerate(hits[:5], 1):
            if isinstance(hit, dict):
                title = hit.get("title") or hit.get("source") or hit.get("doc_id") or "条目"
                snippet = hit.get("snippet") or hit.get("content") or hit.get("text") or ""
                source = hit.get("source") or hit.get("path") or ""
                lines.append(f"{i}. {title}")
                if snippet:
                    lines.append(f"   {snippet}")
                if source:
                    lines.append(f"   来源：{source}")
            else:
                lines.append(f"{i}. {hit}")
    lines.extend(["", "手册内容须可追溯来源，系统不会编造条目。", "", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_fault_type(result: dict[str, Any]) -> str:
    lines = [
        "【故障类型参考预测】",
        "",
        f"设备编号：{_fmt(result.get('assetnum'))}",
        f"预测窗口（天）：{_fmt(result.get('prediction_window_days'))}",
        f"整体故障风险：{_fmt(result.get('overall_failure_risk'))}",
    ]
    most = result.get("most_likely_fault")
    if most:
        lines.append(f"最可能故障参考：{_fmt(most)}")
    preds = result.get("fault_type_predictions") or []
    if preds:
        lines.extend(["", "类型得分："])
        for item in preds[:5]:
            if isinstance(item, dict):
                lines.append(
                    f"- {_fmt(item.get('fault_type') or item.get('name'))}: "
                    f"{_fmt(item.get('score') or item.get('probability'))}"
                )
            else:
                lines.append(f"- {item}")
    message = result.get("message")
    if message:
        lines.extend(["", str(message)])
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_diagnose(result: dict[str, Any]) -> str:
    profile = result.get("device_profile") or {}
    risk = result.get("risk_prediction") or {}
    history = result.get("history_summary") or {}
    advice = result.get("maintenance_advice") or {}

    lines = [
        "【设备综合诊断】",
        "",
        "一、设备档案",
        f"- 设备编号：{_fmt(profile.get('assetnum') or result.get('assetnum'))}",
        f"- 车站：{_fmt(profile.get('station_name'))}",
        f"- 线路：{_fmt(profile.get('line'))}",
        f"- 品牌：{_fmt(profile.get('brand'))}",
        f"- 子系统：{_fmt(profile.get('subsystem'))}",
        f"- 历史工单数：{_fmt(profile.get('history_workorder_count'))}",
        "",
        "二、复发风险",
        f"- 30 天：{_risk_label(risk.get('risk_30d'))}",
        f"- 90 天：{_risk_label(risk.get('risk_90d'))}",
        f"- 预警等级：{_fmt(risk.get('warning_level'))}",
        f"- 建议巡检窗口：{_fmt(risk.get('suggested_inspection_window'))}",
        "",
        f"三、历史摘要（返回 {_fmt(history.get('returned_history_count'))} 条）",
    ]
    recent = history.get("recent_descriptions") or []
    if recent:
        for desc in recent[:5]:
            lines.append(f"- {desc}")
    else:
        lines.append("- 暂无近期描述")

    _append_list(lines, "四、建议检查方向：", advice.get("inspection_suggestions") or [])

    statement = result.get("analysis_statement")
    if statement:
        lines.extend(["", str(statement)])
    lines.extend(["", SCIENTIFIC_BOUNDARY])
    return "\n".join(lines)


def narrate_error(message: str) -> str:
    return f"处理失败：{message}\n\n{SCIENTIFIC_BOUNDARY}"


_NARRATORS = {
    "get_data_overview": narrate_overview,
    "list_high_risk_devices": narrate_high_risk,
    "list_maintenance_suggestions": narrate_maintenance_suggestions,
    "list_maintenance_tasks": narrate_maintenance_tasks,
    "get_device_history": narrate_history,
    "predict_device_risk": narrate_risk,
    "advise_maintenance": narrate_advice,
    "search_manual": narrate_manual,
    "predict_fault_type": narrate_fault_type,
    "diagnose_device": narrate_diagnose,
}


def _template_narrate(use_case: str, result: dict[str, Any]) -> str:
    """模板叙述（兜底 & LLM 关闭时使用）。"""
    narrator = _NARRATORS.get(use_case)
    if narrator is None:
        return f"已完成相关查询，但暂时无法整理结果摘要。请查看对应页面中的结构化数据。\n\n{SCIENTIFIC_BOUNDARY}"
    return narrator(result)


_NARRATE_SYSTEM_PROMPT = (
    "你是地铁 AFC（自动售检票）闸机检修助手。"
    "你会收到某个业务用例的结构化结果（JSON）以及用户的原始问题。"
    "请用简洁、专业、面向一线检修人员的中文，把结果讲清楚。硬性要求：\n"
    "1. 只能使用提供的数据，严禁编造设备编号、风险数值、故障类别、手册条目或任何未提供的事实；\n"
    "2. 风险表示未来时间窗口内再次产生故障工单的可能性，不等于精确故障发生日期；\n"
    "3. 若结果含检修建议列表，必须按给定顺序叙述，禁止重排；单设备巡检建议不是最终根因；"
    "故障类型的条件概率不得说成一定发生；\n"
    "4. 若某项数据缺失，如实说明，不要臆测；风险参考若来自统计估算，应明确说是估算参考。没有更新时间时不得说‘今日’、‘最新’或‘实时’；\n"
    "5. 使用一线检修人员熟悉的中文。不要复述内部用例名、Tool 名、字段名、文件名、接口地址或实现方法，也不要提‘确定性规则’、‘LLM’或‘RAG’。"
    "数据来源必要时用用户语言概括；体验/模拟资源必须明说是体验数据，并提醒现场核实。风险小数按百分数表述。\n"
    "6. 输出纯文本，不要输出 JSON 或代码块，结尾附一句简短的科学边界提示。"
)


def _extract_llm_text(response: Any) -> str:
    """从 LangChain 响应中提取纯文本。"""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                parts.append(str(chunk.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


def _compact_payload(result: dict[str, Any], limit: int = 3500) -> str:
    compact = json.dumps(result, ensure_ascii=False, default=str)
    if len(compact) > limit:
        compact = compact[:limit] + "...(截断)"
    return compact


def _llm_narrate(use_case: str, result: dict[str, Any], query: str) -> str | None:
    """调用 LLM 生成自然语言答复；失败返回 None 由调用方兜底。"""
    try:
        from backend.core.llm import get_conversation_llm

        llm = get_conversation_llm()
        user_content = (
            f"用户问题：{query or '（未提供，请基于结果给出诊断说明）'}\n"
            f"用例：{use_case}\n"
            f"结构化结果（JSON）：\n{_compact_payload(result)}"
        )
        response = llm.invoke(
            [
                ("system", _NARRATE_SYSTEM_PROMPT),
                ("human", user_content),
            ]
        )
        text = _extract_llm_text(response)
        return text or None
    except Exception as exc:  # noqa: BLE001 — LLM 失败时静默兜底到模板
        logger.warning("LLM 叙述失败，回退模板：%s", exc)
        return None


def narrate(use_case: str, result: dict[str, Any] | None, *, query: str = "") -> str:
    """基于用例结果生成答复；LLM 开启且可用时用模型生成，否则/失败时用模板。"""
    if result is None:
        return narrate_static("clarified")

    if is_llm_enabled():
        llm_answer = _llm_narrate(use_case, result, query)
        if llm_answer:
            return llm_answer

    return _template_narrate(use_case, result)
