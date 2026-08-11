"""规则优先意图理解 —— 映射到 Application 用例名，不做工具规划。"""

from __future__ import annotations

import re
from typing import Any, TypedDict


class Understanding(TypedDict):
    kind: str  # usecase | clarified | chat | capability | rejected | explanation
    use_case: str | None
    assetnum: str | None
    needs_asset: bool
    manual_query: str | None


_CHAT_KEYWORDS = ("你好", "您好", "hello", "hi", "嗨", "在吗", "谢谢", "再见")
_CAPABILITY_KEYWORDS = (
    "你会干什么",
    "你能做什么",
    "有什么功能",
    "功能介绍",
    "使用说明",
    "怎么用",
    "帮助",
    "help",
)
_GLOBAL_KEYWORDS = (
    "整体情况",
    "概览",
    "这批工单",
    "工单数据",
    "高风险设备",
    "优先巡检",
    "巡检重点",
    "当前高风险",
)
_UNSUPPORTED_KEYWORDS = (
    "写论文",
    "天气",
    "推荐电影",
    "推荐音乐",
    "点外卖",
    "翻译",
    "写代码",
    "炒股",
)
_REFERENCE_PHRASES = (
    "那它",
    "它",
    "这个设备",
    "该设备",
    "刚才那个",
    "刚才那台",
    "这台",
    "那台",
    "那应该",
)
_BUSINESS_KEYWORDS = (
    "分析",
    "风险",
    "故障",
    "检查",
    "建议",
    "维修",
    "诊断",
    "历史",
    "预警",
    "巡检",
    "复发",
    "再坏",
    "手册",
    "规程",
    "工单",
)
_EXPLANATION_KEYWORDS = (
    "一般怎么",
    "原理",
    "什么意思",
    "怎么理解",
    "为什么不代表",
    "风险模型",
    "概率怎么解释",
    "可信度怎么看",
)
_OPEN_CONNECTORS = ("比较", "矛盾", "原因", "综合", "结合", "最值得关注", "为什么")
_SWITCH_PATTERNS = (
    r"换成\s*([A-Za-z0-9]{3,})",
    r"换到\s*([A-Za-z0-9]{3,})",
    r"切换(?:到|成)?\s*(?:设备\s*)?([A-Za-z0-9]{3,})",
    r"再看(?:一下)?\s*(?:设备\s*)?([A-Za-z0-9]{3,})",
)
_FAULT_TYPE_PHRASES = (
    "会发生什么故障",
    "可能出现什么错误",
    "下次可能坏哪里",
    "最可能出现什么问题",
    "未来可能报什么错",
    "哪个模块最可能故障",
    "最可能发生什么",
    "什么故障",
    "哪种故障",
    "哪类故障",
    "故障类型",
    "故障类别",
    "哪个模块",
)


def _contains_any(q: str, phrases: tuple[str, ...]) -> bool:
    return any(x in q for x in phrases)


def _extract_assetnum(q: str) -> str | None:
    patterns = (
        r"设备\s*([A-Za-z0-9]{3,})",
        r"([A-Z]{2,}\d{5,})",
        r"(\d{10,})",
    )
    values = [x for p in patterns for x in re.findall(p, q)]
    return values[-1].upper() if values else None


def _has_device_switch(q: str) -> str | None:
    values = [x for p in _SWITCH_PATTERNS for x in re.findall(p, q, re.I)]
    return values[-1].upper() if values else None


def _looks_like_business(q: str) -> bool:
    return bool(_extract_assetnum(q)) or _contains_any(q, _BUSINESS_KEYWORDS)


def _is_open_analysis(q: str) -> bool:
    dimensions = sum(
        bool(_contains_any(q, keys))
        for keys in (
            ("风险", "预警", "概率"),
            ("历史", "记录", "工单"),
            ("维修", "建议", "巡检"),
            ("手册", "规程"),
        )
    )
    return dimensions >= 2 or (dimensions >= 1 and _contains_any(q, _OPEN_CONNECTORS))


def _detect_device_use_case(q: str) -> str:
    if _contains_any(q, ("手册", "规程", "标准")):
        return "search_manual"
    if _is_open_analysis(q):
        return "diagnose_device"
    if _contains_any(q, _FAULT_TYPE_PHRASES):
        return "predict_fault_type"

    risk = _contains_any(q, ("风险", "预测", "复发", "再坏", "再次故障", "什么时候"))
    advice = _contains_any(q, ("检查", "建议", "处理", "维修", "先看", "先检查"))

    if risk and advice:
        return "diagnose_device"
    if _contains_any(q, ("为什么", "预警", "红色", "橙色", "黄色")) or risk:
        return "predict_device_risk"
    if _contains_any(q, ("历史", "最近", "以前", "出过", "记录", "工单")):
        return "get_device_history"
    if advice:
        return "advise_maintenance"
    if _contains_any(q, ("分析", "诊断", "综合")):
        return "diagnose_device"
    return "diagnose_device"


def _result(
    kind: str,
    *,
    use_case: str | None = None,
    assetnum: str | None = None,
    needs_asset: bool = False,
    manual_query: str | None = None,
) -> Understanding:
    return {
        "kind": kind,
        "use_case": use_case,
        "assetnum": assetnum,
        "needs_asset": needs_asset,
        "manual_query": manual_query,
    }


def understand(query: str, *, last_assetnum: str | None = None) -> Understanding:
    """规则路由：用户话 → 用例 / 澄清 / 闲聊 / 拒绝。"""
    q = (query or "").strip()
    if not q:
        return _result("clarified", needs_asset=True)

    if _contains_any(q, _CHAT_KEYWORDS) and not _looks_like_business(q):
        return _result("chat")
    if _contains_any(q, _CAPABILITY_KEYWORDS) or "help" in q.lower():
        return _result("capability")
    if _contains_any(q, _UNSUPPORTED_KEYWORDS) or ("推荐" in q and "电影" in q):
        return _result("rejected")
    if _contains_any(q, _EXPLANATION_KEYWORDS) and not _extract_assetnum(q):
        return _result("explanation")

    if _contains_any(q, _GLOBAL_KEYWORDS):
        if "高风险" in q or "优先" in q or "巡检重点" in q:
            return _result("usecase", use_case="list_high_risk_devices")
        return _result("usecase", use_case="get_data_overview")

    asset = _has_device_switch(q) or _extract_assetnum(q)
    if not asset and _contains_any(q, _REFERENCE_PHRASES):
        asset = last_assetnum
    if not asset and last_assetnum and _looks_like_business(q):
        asset = last_assetnum

    if asset:
        use_case = _detect_device_use_case(q)
        manual_query = q if use_case == "search_manual" else None
        return _result(
            "usecase",
            use_case=use_case,
            assetnum=asset,
            needs_asset=True,
            manual_query=manual_query,
        )

    if _looks_like_business(q):
        return _result("clarified", needs_asset=True)

    return _result("chat")


def understanding_to_dict(u: Understanding) -> dict[str, Any]:
    return dict(u)
