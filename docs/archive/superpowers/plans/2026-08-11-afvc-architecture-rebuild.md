# AFVC 目标架构重建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/architecture.md` 一次到位重建为「诊断能力平台 + 薄对话入口」：Application 独占业务编排，Interaction 只做理解/澄清/调用/叙述；删除八节点 Agent / Tool 规划骨架。

**Architecture:** 新建 `backend/application` 用例门面与 `backend/interaction` 薄对话；API 与 Chat 只调用用例；`diagnose_device` 为唯一综合聚合。旧 `backend/agent/**`（graph/nodes/tools/plan/evaluate 等）整包删除，不做双轨兼容。目录迁到 `domain` / `infrastructure` / `application` / `interaction` / `api`。

**Tech Stack:** Python 3.12+ · FastAPI · Pydantic · Polars · 可选 LLM（规则可关）· Streamlit · pytest

## Global Constraints

- 只实现目标架构；禁止「旧 Agent API 兼容层 / 新旧双路由 / 迁移说明」进入代码或 README。
- Application 是业务唯一编排者；Interaction 禁止手搓综合诊断、禁止 tool-plan/replan 主路径。
- 用例可单测且默认不依赖真实 LLM（`AFVC_USE_LLM=false`）。
- 科学边界文案不得放松（见 `docs/architecture.md` §6）。
- 预测模型算法可保持现有实现，不在本计划内重做模型。
- 步子大：每个 Task 是一整块可演示切片，不是微提交刷屏；Task 内仍用 checkbox 跟踪。

---

## File Map（目标落点）

| 路径 | 职责 |
|------|------|
| `backend/domain/*` | 预警、故障类别、概率、边界常量（从现有 `backend/domain` 收束；`warning` 只留 domain 一处） |
| `backend/infrastructure/workorders.py` | 工单文件定位与读取（现 `data_service` 的 IO 部分） |
| `backend/infrastructure/risk_table.py` | 外部风险 CSV 读取（现 `model_adapter`） |
| `backend/infrastructure/fault_table.py` | 故障类型 CSV（现 `adapters/fault_prediction_adapter`） |
| `backend/infrastructure/manual_search.py` | 手册检索实现（现 `rag_service`） |
| `backend/infrastructure/llm.py` | LLM 客户端（现 `core/llm`） |
| `backend/infrastructure/session_memory.py` | 进程内会话存储（`session_id` → messages / last_assetnum） |
| `backend/application/usecases.py` | **八个用例函数**的唯一对外门面 |
| `backend/application/diagnose.py` | `diagnose_device` 唯一聚合实现 |
| `backend/application/*.py` | 其余用例实现（可按文件拆，但对外只从 usecases 导出） |
| `backend/interaction/service.py` | `handle_turn(query, session_id) -> InteractionResult` |
| `backend/interaction/understand.py` | 规则（+可选 LLM）→ `use_case_id` / 澄清 / 闲聊 |
| `backend/interaction/narrate.py` | 结构化结果 → 最终答复字符串 |
| `backend/api/*.py` | 薄路由，只调 application / interaction |
| `backend/main.py` | 装配路由 |
| `frontend/streamlit_app.py` | 控制台打用例 API；Chat 只打 Interaction API |
| `tests/application/` · `tests/interaction/` · `tests/api/` | 按层重铺；删除依赖旧 graph/tools 的测试 |

**删除（整包，不留 shim）：**  
`backend/agent/`（含 graph、nodes、tools、llm_json 若仅被 agent 使用则一并迁走或删）、旧 `backend/services/`（逻辑迁入 application/infrastructure 后删除）、重复的 `backend/services/warning_service.py`（改调 domain）。

---

## 用例门面（全计划统一签名）

```python
# backend/application/usecases.py 对外约定

def get_data_overview(top_n: int = 10) -> dict: ...
def list_high_risk_devices(top_n: int = 10) -> dict: ...
def get_device_history(assetnum: str, limit: int = 50) -> dict: ...
def predict_device_risk(assetnum: str) -> dict: ...
def advise_maintenance(assetnum: str) -> dict: ...
def search_manual(query: str, assetnum: str | None = None, top_k: int = 5) -> dict: ...
def predict_fault_type(assetnum: str, window_days: int = 30, top_k: int = 3) -> dict: ...
def diagnose_device(assetnum: str, history_limit: int = 50) -> dict: ...
```

```python
# backend/interaction/service.py

class InteractionResult(TypedDict):
    status: str                    # success | clarified | rejected
    use_case: str | None           # 上表用例名或 None
    assetnum: str | None
    final_answer: str
    session_id: str
    last_assetnum: str | None
    result: dict | None            # 用例原始 dict；澄清/闲聊时为 None

def handle_turn(query: str, session_id: str | None = None) -> InteractionResult: ...
```

HTTP（目标，一步到位，不保留旧路径别名）：

| Method | Path | 调用 |
|--------|------|------|
| GET | `/health` | — |
| POST | `/upload/workorders` | infra 存文件 |
| GET | `/usecases/overview` | `get_data_overview` |
| GET | `/usecases/high-risk` | `list_high_risk_devices` |
| GET | `/usecases/devices/{assetnum}/history` | `get_device_history` |
| GET | `/usecases/devices/{assetnum}/risk` | `predict_device_risk` |
| GET | `/usecases/devices/{assetnum}/advice` | `advise_maintenance` |
| GET | `/usecases/devices/{assetnum}/fault-type` | `predict_fault_type` |
| GET | `/usecases/devices/{assetnum}/diagnosis` | `diagnose_device` |
| GET | `/usecases/manuals/search` | `search_manual` |
| POST | `/interaction/turn` | `handle_turn` |

---

### Task 1: Application 门面 + 唯一综合诊断（大步）

**Files:**
- Create: `backend/application/__init__.py`, `usecases.py`, `diagnose.py`, 以及从现有 service 迁入的用例模块
- Create: `backend/infrastructure/`（workorders / risk_table / fault_table / manual_search；llm 可后置）
- Modify: `backend/domain/warning.py` 为唯一预警实现；删除重复 warning service 依赖
- Test: `tests/application/test_usecases.py`
- Delete after green: 被替换的 `backend/services/*.py` 中已迁走部分（本 Task 结束时 services 应清空或仅剩未引用文件并删除）

**Interfaces:**
- Consumes: 现有 Polars 读数、风险/建议/故障逻辑（迁入，不改算法语义）
- Produces: `usecases.py` 八个函数；`diagnose_device` 内部只调用同层用例/infra，不经过任何 agent/tool

- [ ] **Step 1: 写 Application 契约测试（先失败）**

```python
# tests/application/test_usecases.py
from backend.application import usecases

def test_diagnose_device_returns_aggregated_sections():
    out = usecases.diagnose_device("1000029970")
    assert out["status"] == "success"
    assert "history_summary" in out or "device_profile" in out
    assert "risk_prediction" in out
    assert "maintenance_advice" in out

def test_overview_and_high_risk_smoke():
    assert usecases.get_data_overview(top_n=5)["status"] in {"success", "ok"} or "basic_metrics" in usecases.get_data_overview(5)
    assert isinstance(usecases.list_high_risk_devices(top_n=3), dict)
```

（断言字段名与迁入后的实际 dict 对齐；以 `diagnose_device` 为聚合合同。）

- [ ] **Step 2: 跑测确认失败**

Run: `pytest tests/application/test_usecases.py -v`  
Expected: IMPORT/属性失败（包尚未存在）

- [ ] **Step 3: 大步实现门面**

1. 建 `infrastructure`：把文件 IO、CSV adapter、rag 实现挪入。  
2. 建 `application`：每个用例一个实现函数；`diagnose.py` 内顺序调用 history/risk/advice/fault_type 并组装——**禁止**再引入 tool 层。  
3. `usecases.py` 仅做导出。  
4. Domain 预警：`predict_device_risk` 只调 `domain.warning.generate_warning_info`。  
5. 删除旧 `services/`、`adapters/`（若已迁完）、重复 warning service。

- [ ] **Step 4: 跑 Application 测试至通过**

Run: `pytest tests/application -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/application backend/infrastructure backend/domain tests/application
git add -u backend/services backend/adapters
git commit -m "feat: add application use-case facade and sole diagnose aggregation"
```

---

### Task 2: API 全部改挂 Application（大步，旧路径删除）

**Files:**
- Create: `backend/api/usecases_api.py`, `backend/api/interaction_api.py`（interaction 可先 501 占位，Task 3 填满）
- Modify: `backend/main.py` — 只注册新路由 + upload + health
- Delete: 旧 `predict_api`/`analysis_api`/`advice_api`/`device_api`/`data_api`/`agent_api` 等（逻辑已由 usecases_api 覆盖）
- Test: `tests/api/test_usecases_api.py`（FastAPI TestClient）

**Interfaces:**
- Consumes: Task 1 `usecases.*`
- Produces: 上表 `/usecases/*` HTTP 合同；**不再提供** `/agent/diagnose`、`/analysis/{id}` 等旧路径

- [ ] **Step 1: 写 API 测试**

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_diagnosis_endpoint():
    r = client.get("/usecases/devices/1000029970/diagnosis")
    assert r.status_code == 200
    body = r.json()
    assert "risk_prediction" in body or body.get("status") == "success"

def test_old_agent_path_gone():
    r = client.post("/agent/diagnose", json={"query": "hi"})
    assert r.status_code == 404
```

- [ ] **Step 2: 实现 usecases_api 并改 main；删除旧 router 文件**

- [ ] **Step 3: 跑测**

Run: `pytest tests/api -v` 与 `pytest tests/application -v`  
Expected: PASS；全仓若仍有引用旧路径的测试，本 Task 直接删改那些测试，不留 skip 兼容。

- [ ] **Step 4: Commit**

```bash
git add backend/api backend/main.py tests/api
git add -u
git commit -m "feat: expose use-case HTTP API and remove legacy routes"
```

---

### Task 3: 薄 Interaction 整包替换旧 Agent（大步）

**Files:**
- Create: `backend/interaction/{__init__,service,understand,narrate}.py`, `backend/infrastructure/session_memory.py`
- Modify: `backend/api/interaction_api.py` — `POST /interaction/turn`
- Delete: **整个** `backend/agent/`（graph、nodes、tools、report_builder、schemas 若仅服务 agent 则删；`llm_json` 若 narrate 需要可迁到 `infrastructure/llm_json.py` 或 interaction 内小工具）
- Test: `tests/interaction/test_handle_turn.py`
- Delete: `tests/test_agent_*.py`、`tests/test_understand_prompt.py` 等旧 Agent 测试

**Interfaces:**
- Consumes: `usecases.*`、`session_memory`、可选 `infrastructure.llm`
- Produces: `handle_turn` → `InteractionResult`；主路径映射：

| 用户意图（规则优先） | 调用 |
|----------------------|------|
| 概览 / 工单整体 | `get_data_overview` |
| 高风险 / 优先巡检 | `list_high_risk_devices` |
| 历史 | `get_device_history` |
| 风险 / 预警 | `predict_device_risk` |
| 建议 / 检查什么 | `advise_maintenance` |
| 手册 | `search_manual` |
| 故障类型 | `predict_fault_type` |
| 分析设备 / 综合 | `diagnose_device` |
| 缺设备号 | 不调用例，`status=clarified` |
| 闲聊 / 越界 | 固定话术，`rejected` 或 chat 文案 |

**禁止实现：** tool 注册表、plan_tools、evaluate_evidence、replan 循环、EvidencePacket 主路径。

- [ ] **Step 1: 写 Interaction 测试（LLM 关闭）**

```python
from backend.interaction.service import handle_turn

def test_diagnose_intent_calls_usecase(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    out = handle_turn("帮我分析设备 1000029970", session_id="t1")
    assert out["status"] == "success"
    assert out["use_case"] == "diagnose_device"
    assert out["assetnum"] == "1000029970"
    assert "final_answer" in out and len(out["final_answer"]) > 0

def test_followup_uses_last_assetnum(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    handle_turn("帮我分析设备 1000029970", session_id="t2")
    out = handle_turn("那它风险高吗？", session_id="t2")
    assert out["assetnum"] == "1000029970"
    assert out["use_case"] == "predict_device_risk"

def test_missing_asset_clarifies(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    out = handle_turn("帮我看看风险", session_id="t3")
    assert out["status"] == "clarified"
    assert out["result"] is None
```

- [ ] **Step 2: 实现 understand（规则）+ handle_turn + narrate（模板优先，可选 LLM）+ session_memory**

- [ ] **Step 3: 删除 `backend/agent` 与旧 agent 测试；修 import 残留**

- [ ] **Step 4: 跑测**

Run: `pytest tests/interaction tests/application tests/api -v`  
Expected: PASS  
Run: `pytest -q`  
Expected: 全绿（已删除过时测试，无 skip 伪装）

- [ ] **Step 5: Commit**

```bash
git add backend/interaction backend/infrastructure/session_memory.py backend/api/interaction_api.py tests/interaction
git add -u backend/agent tests
git commit -m "feat: thin interaction layer; remove agent graph and tools"
```

---

### Task 4: 前端 + 文档对齐 + 清理（大步）

**Files:**
- Modify: `frontend/streamlit_app.py`（及 `ui_components` 若需要）— 控制台改打 `/usecases/*`；Chat 改打 `POST /interaction/turn`；去掉对旧字段（tool_trace、evidence_packet、八节点 debug）的依赖
- Modify: `README.md` — 补充真实路径表（仍不写迁移）
- Modify: `docs/architecture.md` — 若路径/函数名有定稿差异，改成与代码一致
- Delete: 仅服务旧 Agent 的前端调试块、无用脚本引用
- Test: `tests/test_frontend_ui.py`、`tests/test_frontend_processing.py` 改为断言新路径与 session 键；`tests/test_text_integrity.py` 保留

**Interfaces:**
- Consumes: Task 2/3 HTTP 合同
- Produces: 可演示的控制台 + Chat；仓库无 `backend/agent`、无旧路由

- [ ] **Step 1: 改前端 API 封装与页面**

```python
# Chat 仅此
api_post("/interaction/turn", {"query": text, "session_id": st.session_state.agent_session_id})
# 设备分析页
api_get(f"/usecases/devices/{assetnum}/diagnosis")
```

- [ ] **Step 2: 更新前端静态测试与 README 路径表**

- [ ] **Step 3: 全量验证**

Run:

```bash
pytest -q
python scripts/check_text_integrity.py
python -m compileall backend frontend
```

Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add frontend README.md docs/architecture.md tests
git add -u
git commit -m "feat: point UI at use-case and interaction APIs; finalize docs"
```

---

## 执行顺序与风险

```
Task 1 Application ──► Task 2 API ──► Task 3 Interaction 删 Agent ──► Task 4 Frontend/Docs
```

| 风险 | 应对 |
|------|------|
| 一次删 agent 导致测试海量失败 | Task 3 同步删除旧测试，不以 skip 掩盖 |
| 字段名与旧前端不一致 | Task 4 按新合同改前端，不在 API 做别名 |
| 步子大难回滚 | 每 Task 一次 commit；出问题回滚到该 Task 起点 |

## Spec Coverage（对照 architecture.md）

| 规格要点 | Task |
|----------|------|
| Application 唯一编排 / diagnose 唯一聚合 | 1 |
| API 暴露同一组用例 | 2 |
| Interaction 四步 + 禁区 | 3 |
| 删除 tool-plan/replan 骨架 | 3 |
| Frontend 控制台 + Chat | 4 |
| 科学边界 / 无 LLM 可测 | 1–3 |
| 目标目录 | 1–3 落地，4 收尾 |

## Placeholder Scan

无 TBD；旧路径不保留；算法不重做已写明。

---

## 完成后的仓库形态（心里预期）

- 能打的是：**用例清晰的诊断平台** + **够用的薄对话**  
- 不再是：八节点 LangGraph Tool Agent 叙事  
- 代码量应明显下降（agent 包整体消失）
