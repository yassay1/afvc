"""Streamlit frontend for AFVC maintenance closed-loop."""
from __future__ import annotations

import uuid
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# Streamlit may execute this file with ``frontend`` as the import root. Ensure
# project packages remain importable regardless of the caller's working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import is_llm_enabled
from frontend.styles import inject_app_styles
from frontend.ui_components import (
    USE_CASE_LABELS,
    display_label,
    render_mode_card,
    render_page_header,
    render_sidebar_brand,
    render_status_panel,
)

API_BASE_URL = "http://127.0.0.1:8000"
NAVIGATION = {
    "首页概览": "home",
    "今日检修建议": "suggestions",
    "检修计划": "tasks",
    "执行反馈": "feedback",
    "数据上传": "upload",
    "数据概览": "overview",
    "高风险设备": "high_risk",
    "设备分析": "device_analysis",
    "对话工作台（旁路）": "chat",
}

st.set_page_config(
    page_title="AFVC 检修闭环",
    page_icon="AFC",
    layout="wide",
    initial_sidebar_state="expanded",
)


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接 FastAPI 后端，请确认服务已启动。")
    except requests.exceptions.HTTPError:
        st.error(f"API 请求失败：{response.text}")
    except Exception as exc:
        st.error(f"请求异常：{exc}")
    return None


def api_post(path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=json_data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接 FastAPI 后端，请确认服务已启动。")
    except requests.exceptions.HTTPError:
        st.error(f"API 请求失败：{response.text}")
    except Exception as exc:
        st.error(f"请求异常：{exc}")
    return None


def api_patch(path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.patch(f"{API_BASE_URL}{path}", json=json_data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接 FastAPI 后端，请确认服务已启动。")
    except requests.exceptions.HTTPError:
        st.error(f"API 请求失败：{response.text}")
    except Exception as exc:
        st.error(f"请求异常：{exc}")
    return None


def upload_file(uploaded_file) -> dict[str, Any] | None:
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(f"{API_BASE_URL}/upload/workorders", files=files, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接 FastAPI 后端，请确认服务已启动。")
    except requests.exceptions.HTTPError:
        st.error(f"上传失败：{response.text}")
    except Exception as exc:
        st.error(f"上传异常：{exc}")
    return None


def _header(title: str, english: str, description: str, scene: str | None = None) -> None:
    render_page_header(
        st,
        title=title,
        english_title=english,
        description=description,
        llm_enabled=is_llm_enabled(),
        scene=scene,
    )


def page_home() -> None:
    _header(
        "AFVC 检修安排闭环",
        "Prediction-driven Maintenance Loop",
        "把已有预测变成：先查谁、何时查、派谁、修完怎么记。主路径是建议 → 计划 → 反馈。",
        "产品主路径",
    )
    st.markdown('<div class="afc-section-label">V1 闭环</div>', unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info("**今日检修建议**\n\n风险 + 站点重要度 + 故障相关度 + 模拟人员/备件，规则打分排序。")
    with col_b:
        st.info("**检修计划**\n\n从建议生成可调整任务（顺序、班组、日期），不是工单 HITL。")
    with col_c:
        st.info("**执行反馈**\n\n记录结果与是否按建议执行，供复盘；不宣称降本减故。")
    st.caption("设备范围：L01 闸机（AFCAGM）；故障焦点：暂停服务。对话/Agent 为旁路加分项。")
    render_status_panel(st, "list_maintenance_suggestions", "DEMO-AGM-001", None)


def page_suggestions() -> None:
    _header(
        "今日检修建议",
        "Maintenance Suggestions",
        "确定性规则排序；不用 LLM/RAG 决定先查谁。",
        "闭环 · 建议",
    )
    top_n = st.number_input("建议条数 Top N", min_value=1, max_value=50, value=10)
    fault_focus = st.text_input("故障焦点", value="暂停服务")
    if st.button("生成今日建议", type="primary"):
        result = api_get(
            "/usecases/maintenance/suggestions",
            params={"top_n": int(top_n), "fault_focus": fault_focus},
        )
        if result:
            st.session_state["last_suggestions"] = result.get("suggestions") or []
            st.caption(result.get("model_note") or "")
            rows = st.session_state["last_suggestions"]
            if rows:
                st.dataframe(
                    [
                        {
                            "设备": r.get("assetnum"),
                            "车站": r.get("station_name"),
                            "得分": r.get("score"),
                            "风险90d": r.get("risk_90d"),
                            "建议班组": r.get("suggested_crew_id"),
                            "理由": "；".join(r.get("reasons") or [])[:120],
                        }
                        for r in rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            with st.expander("原始响应", expanded=False):
                st.json(result)

    suggestions = st.session_state.get("last_suggestions") or []
    if suggestions:
        st.markdown('<div class="afc-section-label">纳入计划</div>', unsafe_allow_html=True)
        labels = [
            f"{s.get('assetnum')} · {s.get('station_name')} · score={s.get('score')}"
            for s in suggestions
        ]
        choice = st.selectbox("选择一条建议", options=list(range(len(labels))), format_func=lambda i: labels[i])
        if st.button("生成检修任务", type="primary"):
            accepted = api_post(
                "/usecases/maintenance/accept-suggestion",
                {"suggestion": suggestions[int(choice)], "priority": int(choice) + 1},
            )
            if accepted:
                st.success(f"已创建任务 {accepted.get('task', {}).get('id')}")
                st.json(accepted.get("task"))


def page_tasks() -> None:
    _header(
        "检修计划",
        "Maintenance Tasks",
        "调整优先级、班组、日期与状态。独立于对话工单审批。",
        "闭环 · 计划",
    )
    status = st.selectbox(
        "按状态筛选",
        options=["全部", "planned", "in_progress", "done", "cancelled"],
    )
    params = {} if status == "全部" else {"status": status}
    if st.button("刷新计划列表", type="primary") or "tasks_cache" not in st.session_state:
        result = api_get("/usecases/maintenance/tasks", params=params or None)
        if result:
            st.session_state["tasks_cache"] = result.get("tasks") or []

    tasks = st.session_state.get("tasks_cache") or []
    if not tasks:
        st.info("暂无检修任务。请先在「今日检修建议」生成并纳入计划。")
        return
    st.dataframe(tasks, use_container_width=True, hide_index=True)

    st.markdown('<div class="afc-section-label">调整任务</div>', unsafe_allow_html=True)
    task_ids = [t.get("id") for t in tasks]
    task_id = st.selectbox("任务 ID", options=task_ids)
    col1, col2, col3 = st.columns(3)
    with col1:
        priority = st.number_input("优先级（越小越先）", min_value=1, max_value=999, value=10)
    with col2:
        crew = st.text_input("班组 ID", value="CREW-A")
    with col3:
        new_status = st.selectbox("状态", options=["planned", "in_progress", "done", "cancelled"])
    if st.button("保存调整"):
        patched = api_patch(
            f"/usecases/maintenance/tasks/{task_id}",
            {"priority": int(priority), "assignee_crew_id": crew, "status": new_status},
        )
        if patched:
            st.success("已调整")
            st.session_state.pop("tasks_cache", None)
            st.rerun()


def page_feedback() -> None:
    _header(
        "执行反馈",
        "Maintenance Feedback",
        "修完后记录结果，用于说明平台是否帮了忙。",
        "闭环 · 反馈",
    )
    result = api_get("/usecases/maintenance/tasks", params={"status": "in_progress"})
    open_result = api_get("/usecases/maintenance/tasks", params={"status": "planned"})
    tasks = []
    if result:
        tasks.extend(result.get("tasks") or [])
    if open_result:
        tasks.extend(open_result.get("tasks") or [])
    if not tasks:
        st.info("没有 planned / in_progress 任务可反馈。")
        return
    labels = {t["id"]: f"{t.get('assetnum')} · {t.get('status')} · {t.get('id')[:8]}" for t in tasks}
    task_id = st.selectbox("选择任务", options=list(labels.keys()), format_func=lambda i: labels[i])
    text = st.text_area("执行结果", value="已现场检查")
    matched = st.checkbox("是否属于目标故障类（暂停服务）", value=True)
    followed = st.checkbox("是否按建议执行", value=True)
    note = st.text_input("备注", value="")
    if st.button("提交反馈", type="primary"):
        out = api_post(
            f"/usecases/maintenance/tasks/{task_id}/feedback",
            {
                "result": text,
                "matched_fault": matched,
                "followed_suggestion": followed,
                "note": note or None,
            },
        )
        if out:
            st.success("反馈已记录")
            st.json(out.get("task"))


def page_upload() -> None:
    _header("数据上传", "Work-order Data Upload", "上传 AFC 工单 Excel 或 CSV 文件，供后续统计和分析使用。", "数据接入")
    uploaded = st.file_uploader("选择工单文件", type=["xlsx", "xls", "csv"], help="支持 xlsx、xls 和 csv 格式。")
    if uploaded and st.button("上传并处理", type="primary"):
        result = upload_file(uploaded)
        if result:
            st.success("文件上传成功。")
            with st.expander("查看上传响应", expanded=False):
                st.json(result)


def page_data_overview() -> None:
    _header("数据概览", "Work-order Data Overview", "查看当前工单数据的规模、分布和高频故障摘要。", "全局数据分析")
    top_n = st.number_input("统计条数 Top N", min_value=1, max_value=50, value=10)
    if st.button("刷新数据概览", type="primary"):
        result = api_get("/usecases/overview", params={"top_n": int(top_n)})
        if result:
            st.json(result)


def page_high_risk() -> None:
    _header("高风险设备", "High-risk Device Prioritization", "按预测风险识别需要优先关注的 AFC 设备。", "风险排序")
    top_n = st.number_input("设备数量 Top N", min_value=1, max_value=50, value=10)
    if st.button("生成风险列表", type="primary"):
        result = api_get("/usecases/high-risk", params={"top_n": int(top_n)})
        if result:
            devices = result.get("devices") if isinstance(result, dict) else None
            if devices:
                st.dataframe(devices, use_container_width=True, hide_index=True)
            with st.expander("查看原始响应", expanded=False):
                st.json(result)


def page_device_analysis() -> None:
    _header("设备分析", "Device Analysis", "查询单台设备的综合诊断（历史、风险、建议等聚合结果）。", "单设备诊断")
    assetnum = st.text_input("设备编号", value="DEMO-AGM-001", help="公开 DEMO：DEMO-AGM-001；本地真实数据用实际 assetnum。")
    if st.button("开始分析", type="primary") and assetnum.strip():
        result = api_get(f"/usecases/devices/{assetnum.strip()}/diagnosis")
        if result:
            st.json(result)


def _init_chat_session() -> None:
    defaults = {
        "agent_session_id": str(uuid.uuid4()),
        "agent_messages": [],
        "agent_last_assetnum": None,
        "agent_last_use_case": None,
        "agent_is_processing": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("agent_pending_actions", [])


def _new_chat_session() -> None:
    st.session_state["agent_session_id"] = str(uuid.uuid4())
    st.session_state["agent_messages"] = []
    st.session_state["agent_last_assetnum"] = None
    st.session_state["agent_last_use_case"] = None
    st.session_state["agent_is_processing"] = False
    st.session_state["agent_pending_actions"] = []


def _clear_stale_agent_processing() -> None:
    """Clear a transient flag left by a browser refresh or interrupted run."""
    if st.session_state.get("agent_is_processing", False):
        st.session_state["agent_is_processing"] = False


def _interaction_turn(question: str) -> dict[str, Any] | None:
    return api_post(
        "/interaction/turn",
        {"query": question, "session_id": st.session_state["agent_session_id"]},
    )


def _handle_agent_query(question: str) -> bool:
    """Execute one Interaction turn and always clear its transient loading state."""
    if st.session_state.get("agent_is_processing", False):
        return False

    st.session_state["agent_is_processing"] = True
    thinking_placeholder = st.empty()
    st.session_state["agent_messages"].append({"role": "user", "content": question, "meta": None})

    try:
        thinking_placeholder.markdown("正在调用诊断能力并整理答复……")
        result = _interaction_turn(question)

        if not result:
            st.session_state["agent_messages"].append(
                {"role": "assistant", "content": "后端服务暂不可用，请确认 FastAPI 服务已启动后重试。", "meta": None}
            )
            return True

        if result.get("status") in {"success", "clarified", "chat", "unsupported"}:
            st.session_state["agent_last_assetnum"] = result.get("last_assetnum") or result.get("assetnum")
            st.session_state["agent_last_use_case"] = result.get("use_case")
            if result.get("session_id"):
                st.session_state["agent_session_id"] = result["session_id"]

        st.session_state["agent_messages"].append(
            {
                "role": "assistant",
                "content": result.get("final_answer") or "本次未生成有效回答。",
                "meta": {
                    "use_case": result.get("use_case"),
                    "assetnum": result.get("assetnum"),
                    "last_assetnum": result.get("last_assetnum"),
                    "session_id": result.get("session_id"),
                    "status": result.get("status"),
                },
            }
        )
        st.session_state["agent_pending_actions"] = result.get("pending_actions") or []
        return True
    except Exception as exc:
        st.session_state["agent_messages"].append(
            {
                "role": "assistant",
                "content": f"对话调用异常：{exc}。请稍后重试。",
                "meta": None,
            }
        )
        return True
    finally:
        st.session_state["agent_is_processing"] = False
        thinking_placeholder.empty()


def _render_message_meta(meta: dict[str, Any]) -> None:
    bits = []
    use_case = meta.get("use_case")
    if use_case:
        bits.append(display_label(use_case, USE_CASE_LABELS))
    if meta.get("assetnum"):
        bits.append(f"设备 {meta['assetnum']}")
    if meta.get("session_id"):
        bits.append(f"会话 {str(meta['session_id'])[:8]}")
    if bits:
        st.caption(" · ".join(bits))


def _resolve_pending_action(action_id: str, decision: str) -> None:
    path = "/interaction/approve" if decision == "approve" else "/interaction/reject"
    result = api_post(
        path,
        {
            "session_id": st.session_state.get("agent_session_id"),
            "action_id": action_id,
        },
    )
    if not result:
        return
    st.session_state["agent_pending_actions"] = result.get("pending_actions") or []
    st.session_state["agent_messages"].append(
        {
            "role": "assistant",
            "content": result.get("final_answer") or "审批已完成。",
            "meta": {"status": result.get("status"), "session_id": result.get("session_id")},
        }
    )


def _render_pending_actions() -> None:
    pending = st.session_state.get("agent_pending_actions") or []
    if not pending:
        return
    st.markdown('<div class="afc-section-label">待批准写操作</div>', unsafe_allow_html=True)
    st.caption("这些操作尚未写入数据库。请点批准或拒绝；在对话里说「好的」不会生效。")
    for action in pending:
        action_id = action.get("action_id")
        with st.container(border=True):
            st.write(action.get("summary") or action.get("tool_name"))
            st.caption(f"{action.get('tool_name')} · {action_id}")
            col_ok, col_no = st.columns(2)
            with col_ok:
                if st.button("批准", key=f"approve_{action_id}", use_container_width=True):
                    _resolve_pending_action(action_id, "approve")
                    st.rerun()
            with col_no:
                if st.button("拒绝", key=f"reject_{action_id}", use_container_width=True):
                    _resolve_pending_action(action_id, "reject")
                    st.rerun()


def page_chat() -> None:
    _init_chat_session()
    # A browser refresh or an interrupted previous run must not resurrect a
    # transient loading indicator. Requests are synchronous within one run.
    _clear_stale_agent_processing()
    use_case = st.session_state.get("agent_last_use_case")
    scene = display_label(use_case, USE_CASE_LABELS, "对话工作台")
    _header(
        "对话工作台",
        "AFC Conversation Console",
        "通过自然语言查询设备风险、历史工单、维护建议和综合诊断。",
        scene,
    )

    col_status, col_button = st.columns([5, 1])
    with col_status:
        render_status_panel(
            st,
            use_case,
            st.session_state.get("agent_last_assetnum"),
            st.session_state.get("agent_session_id"),
        )
    with col_button:
        st.write("")
        if st.button("新建会话", use_container_width=True):
            _new_chat_session()
            st.rerun()

    render_mode_card(st, is_llm_enabled())

    quick_questions = [
        "帮我分析设备 DEMO-AGM-001",
        "设备 DEMO-AGM-001 未来30天风险高吗",
        "设备 DEMO-AGM-001 最近有哪些故障",
        "设备 DEMO-AGM-001 应该先检查什么",
        "当前高风险设备有哪些",
        "那它最近有哪些故障",
    ]
    with st.expander("常用问题", expanded=False):
        cols = st.columns(3)
        for index, question in enumerate(quick_questions):
            with cols[index % 3]:
                if st.button(question, key=f"quick_{index}", use_container_width=True):
                    if _handle_agent_query(question):
                        st.rerun()

    st.markdown('<div class="afc-section-label">对话记录</div>', unsafe_allow_html=True)
    messages = st.session_state.get("agent_messages", [])
    if not messages:
        st.info("尚无对话。你可以输入设备编号、故障现象或维护问题开始分析。")
    for message in messages:
        role = message.get("role", "assistant")
        with st.chat_message(role):
            if role == "assistant":
                st.caption("AFC 智能运维助手")
            st.markdown(message.get("content") or "（空消息）")
            if role == "assistant" and message.get("meta"):
                _render_message_meta(message["meta"])

    _render_pending_actions()

    prompt = st.chat_input("请输入设备编号、故障现象或维护问题")
    if prompt and not st.session_state.get("agent_is_processing", False):
        if _handle_agent_query(prompt):
            st.rerun()


def main() -> None:
    inject_app_styles(st)
    with st.sidebar:
        render_sidebar_brand(st)
        selected = st.radio("主导航", list(NAVIGATION), label_visibility="collapsed")
        st.caption("预测驱动的检修安排闭环")

    page = NAVIGATION[selected]
    if page == "home":
        page_home()
    elif page == "suggestions":
        page_suggestions()
    elif page == "tasks":
        page_tasks()
    elif page == "feedback":
        page_feedback()
    elif page == "upload":
        page_upload()
    elif page == "overview":
        page_data_overview()
    elif page == "high_risk":
        page_high_risk()
    elif page == "device_analysis":
        page_device_analysis()
    else:
        page_chat()


if __name__ == "__main__":
    main()
