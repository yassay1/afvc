"""Static compatibility tests for the Streamlit AFC operations UI."""
from pathlib import Path

from frontend.styles import APP_CSS
from frontend.ui_components import USE_CASE_LABELS, display_label

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "frontend" / "streamlit_app.py").read_text(encoding="utf-8")
UI_SOURCE = (ROOT / "frontend" / "ui_components.py").read_text(encoding="utf-8")


def test_use_case_display_mapping_has_safe_fallback():
    assert display_label("diagnose_device", USE_CASE_LABELS) == "设备综合诊断"
    assert display_label("get_data_overview", USE_CASE_LABELS) == "数据概览"
    assert display_label("future_case", USE_CASE_LABELS) == "future_case"
    assert display_label(None, USE_CASE_LABELS) == "尚未识别"


def test_styles_define_responsive_container_and_accessibility_states():
    assert "max-width: 1280px" in APP_CSS
    assert "@media (max-width: 760px)" in APP_CSS
    assert "prefers-reduced-motion" in APP_CSS
    assert "focus-visible" in APP_CSS
    assert "min-height: 44px" in APP_CSS


def test_navigation_pages_and_chat_state_keys_are_preserved():
    for label in ("首页概览", "数据上传", "数据概览", "高风险设备", "设备分析", "对话工作台"):
        assert label in APP_SOURCE
    for key in ("agent_session_id", "agent_messages", "agent_last_assetnum", "agent_last_use_case"):
        assert key in APP_SOURCE
    assert "Agent 工作台" not in APP_SOURCE
    assert "工作流：8 节点" not in UI_SOURCE
    assert "八节点" not in APP_SOURCE


def test_frontend_api_paths_target_use_case_and_interaction():
    for path in (
        "/upload/workorders",
        "/usecases/overview",
        "/usecases/high-risk",
        "/usecases/devices/",
        "/diagnosis",
        "/interaction/turn",
        "/interaction/approve",
        "/interaction/reject",
    ):
        assert path in APP_SOURCE
    for legacy in ("/data/summary", "/devices/high-risk", "/analysis/", "/agent/diagnose"):
        assert legacy not in APP_SOURCE


def test_frontend_bootstraps_project_root_before_backend_import():
    bootstrap = APP_SOURCE.index("sys.path.insert")
    backend_import = APP_SOURCE.index("from backend.core.config import is_llm_enabled")
    assert bootstrap < backend_import


def test_llm_mode_uses_existing_backend_configuration():
    assert "from backend.core.config import is_llm_enabled" in APP_SOURCE
    assert "AFVC_USE_LLM=true" in UI_SOURCE


def test_official_streamlit_chat_without_legacy_agent_debug():
    assert "st.chat_message" in APP_SOURCE
    assert 'st.chat_input("请输入设备编号、故障现象或维护问题")' in APP_SOURCE
    assert "tool_trace" not in APP_SOURCE
    assert "evidence_packet" not in APP_SOURCE
    assert 'st.expander("调试信息"' not in APP_SOURCE
