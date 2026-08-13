"""Reusable presentation helpers for the Streamlit frontend."""
from __future__ import annotations

from html import escape
from typing import Any

USE_CASE_LABELS = {
    "get_data_overview": "数据概览",
    "list_high_risk_devices": "高风险设备",
    "get_device_history": "设备历史",
    "predict_device_risk": "设备风险预测",
    "advise_maintenance": "维护建议",
    "predict_fault_type": "故障类型预测",
    "diagnose_device": "设备综合诊断",
    "search_manual": "维修手册检索",
}


def display_label(value: Any, mapping: dict[str, str], empty: str = "尚未识别") -> str:
    """Map an internal enum to a user-facing label with a safe fallback."""
    if value is None or value == "":
        return empty
    text = str(value)
    return mapping.get(text, text)


def render_sidebar_brand(st_module) -> None:
    st_module.markdown(
        """
        <div class="afc-brand">
          <div class="afc-brand-mark">AFC</div>
          <div class="afc-brand-title">AFC 智能运维</div>
          <div class="afc-brand-subtitle">Fault Prediction Platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    st_module,
    *,
    title: str,
    english_title: str,
    description: str,
    llm_enabled: bool,
    scene: str | None = None,
) -> None:
    mode = "LLM 模式" if llm_enabled else "规则兜底"
    scene_chip = f'<span class="afc-chip afc-chip--route">当前场景：{escape(scene)}</span>' if scene else ""
    st_module.markdown(
        f"""
        <header class="afc-page-header">
          <div>
            <div class="afc-eyebrow">AFC Operations Intelligence</div>
            <h1 class="afc-page-title">{escape(title)}</h1>
            <div class="afc-page-subtitle">{escape(english_title)}</div>
            <div class="afc-page-description">{escape(description)}</div>
          </div>
          <div class="afc-status-row" aria-label="系统状态">
            <span class="afc-chip afc-chip--online">服务在线</span>
            <span class="afc-chip afc-chip--mode">当前模式：{mode}</span>
            {scene_chip}
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_mode_card(st_module, llm_enabled: bool) -> None:
    if llm_enabled:
        title = "当前使用 LLM 模式"
        copy = "模型能力已启用，系统会在结构化约束下完成意图理解与结果叙述。"
        class_name = "afc-mode-card afc-mode-card--enabled"
    else:
        title = "当前使用规则兜底模式"
        copy = "LLM 调用尚未启用，系统将通过内置规则完成意图识别与用例路由。设置 AFVC_USE_LLM=true 后可启用模型能力。"
        class_name = "afc-mode-card"
    st_module.markdown(
        f'<div class="{class_name}" role="status"><span class="afc-mode-indicator"></span><div><div class="afc-mode-title">{title}</div><div class="afc-mode-copy">{copy}</div></div></div>',
        unsafe_allow_html=True,
    )


def render_status_panel(
    st_module,
    use_case: Any,
    assetnum: Any = None,
    session_id: Any = None,
) -> None:
    use_case_label = display_label(use_case, USE_CASE_LABELS)
    asset_label = str(assetnum) if assetnum else "未选择设备"
    session_label = str(session_id)[:12] if session_id else "未建立"
    st_module.markdown(
        f"""
        <section class="afc-route-panel" aria-label="当前对话状态">
          <div class="afc-route-item"><div class="afc-route-label">用例</div><div class="afc-route-value">{escape(use_case_label)}</div></div>
          <div class="afc-route-item"><div class="afc-route-label">当前设备</div><div class="afc-route-value">{escape(asset_label)}</div></div>
          <div class="afc-route-item"><div class="afc-route-label">会话</div><div class="afc-route-value">{escape(session_label)}</div></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
