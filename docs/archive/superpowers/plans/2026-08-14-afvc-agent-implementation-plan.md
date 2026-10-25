# AFVC Agent Implementation Plan + Migration Map

**Status (2026-08-14):** P0–P3 已在 `main` 本地提交（`5ac519b`）。V1 真实 DeepSeek + LangSmith 验收曾 6/6 通过。当前工作区另有**未提交**稳定化改动：eval cases、tracing、`tool_trace` 按轮次统计、tool 错误不崩图、DeepSeek 文档对齐。下一阶段：**稳定化 / eval 复跑**，不再扩架构。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重写业务算法的前提下，把 AFVC 从「文件库 + 规则 Interaction」迁到「Postgres 行级业务数据 + LangGraph 主图 Agent」。写操作人批（P3）为：Agent 提案 → `pending_actions` → 当前 run 正常结束 → 显式 approve/reject API → DB 写入；**不是**会话 thread 暂停/恢复式 HITL。

**Architecture:** Application 继续实现 Data / Prediction / 建议手册；主图只编排。对话 thread 与写操作审批解耦：会话可继续，写操作只能走显式 approve API。`understand.py` 退出 LLM 主路径，仅作 LLM 关闭/失败兜底。

**Tech Stack:** Python 3.12 · FastAPI · Streamlit · Polars · Postgres · LangGraph + PostgresSaver · OpenAI-compatible LLM（V1 验收：DeepSeek）· LangSmith tracing（开关）· pytest

**Spec:** `docs/superpowers/specs/2026-08-14-afvc-agent-architecture-design.md`  
**本轮拍板：** 1c（无 semantic gate）· 2b（行级 CRUD）· 3a（无登录，但不写死单用户）· HITL = 提案单据 + 显式 API（见 §0 / §7；禁止用会话 thread 的 `interrupt()` / `Command(resume)` 等人批）

## Global Constraints

- 不恢复八节点 Agent；不把平台做成开放 Tool Calling。
- 不重写 overview/risk/advice 等业务数值逻辑；只换 IO（文件 → SQL）。
- 不重命名 `backend/data/mock/`。
- 不建设登录 / RBAC；`actor_id` 可空预留。
- `understand.py` 不进入 LLM 主路径。
- 写操作不得因用户说「好的/确认」被模型推断为已批准。
- pending approval **不得**锁死整个会话 thread。
- 只给最外层图挂 checkpointer；数据子图不单独挂。
- 测试默认 `AFVC_USE_LLM=false` 必须仍绿。
- 本机不 push。

---

## 0. HITL 怎么落地（以及为什么不用会话 interrupt）

**已拍板的人批路径（P3，本轮不实现）：**

```text
Agent 提案 → pending_actions → 当前 run 正常结束
    → 显式 approve/reject API → DB 写入
```

会话 thread **照常结束本轮**；用户继续聊天是同一 `thread_id` 上的 **新 invoke**，不是 `Command(resume)`。口语「好的」不得执行写入。

下面记录官方 `interrupt()` / double-texting 只说明 **为什么不能** 做成「会话暂停/恢复式 HITL」，不是本产品的目标形态。

### `interrupt()`（OSS LangGraph）

[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 要点：

- 在节点里调用 `interrupt(payload)` → **该 thread 无限挂起**，直到用**同一个 `thread_id`** 再 `invoke(Command(resume=...))`。
- resume 值成为 `interrupt()` 的返回值；**节点会从函数开头重跑**（`interrupt()` 之前的代码会再执行一遍）。
- 这是给「同一条 run 必须等人才能继续」用的，**不是**给「一边等人批、一边继续聊天」用的。

若把会话 `session_id` 当成这一个 thread，一旦写工具 `interrupt()`，后续 `POST /turn` 要么变成误 resume，要么和挂起状态打架 → **必然锁死会话**。这与 1c +「不锁死会话」冲突，**会话主路径禁止用 `interrupt()` 等人批。**

### Double-texting（非 OSS）

[Double texting](https://docs.langchain.com/langsmith/double-texting) 明确写在 **LangSmith Agent Server / Deployment**，OSS 没有 `multitask_strategy`。四种策略只作产品语义对照：

| 策略 | 语义 | AFVC 怎么落地 |
|------|------|----------------|
| reject | 进行中拒绝新 run | **进行中的图 run**（LLM 还在跑）：拒绝新 `/turn`（沿用 Streamlit `agent_is_processing` + API 409） |
| enqueue | 排队 | 本阶段不做队列 Worker |
| interrupt（取消当前 run） | 停当前、保留 checkpoint | 不用于 HITL；仅若以后要「用户打断正在生成」 |
| rollback | 删掉当前 run | 不用 |

**人批挂起 ≠ 图还在跑。** 人批是 run **已经结束** 后留下的业务单据。

### 推荐结构：两级身份

```text
thread_id  = session_id          # 对话 checkpoint（PostgresSaver）
action_id  = uuid                # 写操作审批单（agent.pending_actions）
```

- 敏感 Tool **只提案**：插入 `pending_actions`，向模型返回「未执行，等待人批」，本轮图 **正常结束**。
- 用户继续说话：新 `/turn` = 同一 `thread_id` 上 **新的 invoke（普通 input dict）**，不是 `Command(resume)`。
- 批准：`POST /interaction/approve` + `action_id`。**只有这条路径写库。** 然后把执行结果作为一条 Tool/系统消息注入会话，可选再跑一轮短叙述。
- 若写路径自身需要崩溃恢复：对 **action 专用 thread**（`action:{action_id}`）使用 `interrupt()` / `Command(resume)`，与会话 thread 隔离。第一版可以先同步执行写入、靠 DB 事务，action-thread 作为增强。

模型在对话里看到「好的」最多再解释或提醒去点批准按钮，**工具实现里没有 execute_write()**。

---

## 1. 当前架构 → 目标架构迁移路线

```text
现在
  工单 = 最新 Excel/CSV
  会话 = 进程内存
  对话 = understand 规则一次一用例 + narrate
  上传 = 只落盘

目标
  工单 = Postgres 行（Excel 只是 import）
  会话 = PostgresSaver + pending_actions
  对话 = 主图 LLM 选 Tool（1c）；understand 仅 fallback
  上传/写入 = 控制台可直接写库；对话侧只提案 + 显式批准
```

阶段顺序（已拍板）：**runtime/persistence → Main Agent → Tool/Subgraph → HITL**。

| 阶段 | 交付 | 用户可见变化 |
|------|------|----------------|
| P0 | Compose Postgres、schema、工单导入/查询走 SQL；checkpointer 可空转 | 控制台行为接近现在，数据活在库里 |
| P1 | 主图替换 `handle_turn` 主路径；LLM 关则 fallback understand | 对话可多步调只读能力；仍无对话写库 |
| P2 | Tool 注册表 + 数据子图（数据域内部执行封装，无 LLM） | 主 Agent 仍直接选择数据 Tool；子图不承担意图路由 |
| P3 | pending_actions + approve/reject；敏感 Tool 只提案 | 对话可提导入；点批准才写 |

回滚：每阶段 feature 开关或 `AFVC_AGENT_GRAPH=false` 回到 `handle_turn`；P0 保留文件读取作紧急 fallback **仅运维开关**，默认走 SQL。

---

## 2. 文件级变更地图

### 保留（逻辑几乎不动）

| 路径 | 原因 |
|------|------|
| `backend/application/risk.py` `fault_type.py` `advice.py` `manual.py` `diagnose.py` | 业务算法 |
| `backend/domain/*` | 规则 |
| `backend/infrastructure/risk_table.py` `fault_table.py` `manual_search.py` | 模型 CSV / 手册；不改 `data/mock/` |
| `backend/schemas/*` | 契约逐步被 API 使用，不删 |
| `backend/core/llm.py` | 已清理 |
| `frontend/styles.py` `ui_components.py` | UI 壳 |
| `tests/application/*` `tests/test_services.py` 等用例测试 | 改 IO 后修 fixture，不断言文件路径死值 |

### 修改

| 路径 | 改什么 |
|------|--------|
| `backend/infrastructure/workorders.py` | 读路径改为 Postgres；保留 Excel parser 供 import |
| `backend/application/overview.py` `history.py` | 基于 SQL/仓储，不读最新文件 |
| `backend/api/upload_api.py` | 解析并 **bulk insert**（控制台路径：人已点上传，视为已批准） |
| `backend/api/interaction_api.py` | `turn` 走主图；加 `approve`/`reject`；进行中 409 |
| `backend/interaction/service.py` | 薄封装：LLM 开 → graph；关/失败 → `understand`+用例 |
| `backend/interaction/narrate.py` | 主路径由主图叙述；模板仍给 fallback |
| `backend/core/config.py` | `DATABASE_URL`、`AFVC_AGENT_GRAPH` |
| `backend/main.py` | lifespan 里 checkpointer/engine |
| `frontend/streamlit_app.py` | 待批卡片 + approve/reject；不锁输入框 |
| `docs/architecture.md` | P1 完成后回写「主图 Agent」 |
| `.env.example` `requirements.txt` | `psycopg` / `langgraph-checkpoint-postgres` |

### 新建

| 路径 | 职责 |
|------|------|
| `backend/infrastructure/db.py` | Engine / session，search_path |
| `backend/infrastructure/workorder_repo.py` | 行级 CRUD + 统计查询 |
| `scripts/sql/001_init.sql` 等 | business + agent.pending_actions + 预留 actor_id |
| `docker-compose.yml` | 仅 postgres（+ 可选） |
| `backend/agent/graph.py` | 主图 compile + checkpointer |
| `backend/agent/state.py` | messages、last_assetnum、pending_action_ids |
| `backend/agent/tools.py` | 注册表：包装 application 用例；敏感工具只写 pending |
| `backend/agent/guardrails.py` | 系统提示：科学边界、禁止把闲聊当批准 |
| `backend/agent/pending_actions.py` | 审批单仓储 |
| `backend/agent/data_subgraph.py` | P2：读路径子图节点 |
| `tests/agent/*` `tests/infrastructure/test_workorder_repo.py` | 新契约 |

### 最终淘汰（P1 稳定后，不要第一周删）

| 路径 | 何时 |
|------|------|
| `backend/infrastructure/session_memory.py` | checkpointer 成为会话真相后 |
| 规则一次一用例作为**主路径** | 已降为 fallback；文件保留 |
| `get_latest_raw_file()` 作为查询真相 | import 完成后 |

不新建空的 repository/manager/factory 层；仓储只加 `workorder_repo` 与 `pending_actions` 两处 IO。

---

## 3. PostgreSQL 与 migration 落地方案

同一实例，两个 schema。不重新选型。

### `business`

**`import_batches`**

- `id` uuid PK  
- `source_filename`  
- `stored_path`（原文件引用，不进 checkpoint）  
- `mode` `replace` | `append`（控制台默认 `replace`，贴近「一份工作集」）  
- `row_count`  
- `created_at`  
- `actor_id` uuid NULL  

**`workorders`**

- `id` uuid PK  
- `import_batch_id` FK  
- 现有字段：`assetnum` `station_name` `cust_linenum` `current_faildate` `prev_faildate` `total_failure_count` `description` `cust_brand` 以及文件里已有的 `cust_subsys` `worktype` `pre_type` `pre_value`（有则存）  
- `created_at` / `updated_at`  
- `actor_id` NULL  
- 索引：`assetnum`，`(current_faildate)`  

查询/统计/历史 **只打 `workorders`**。Excel 不是本体。

**第一版 CRUD**

| API/能力 | 行为 |
|----------|------|
| 控制台上传 | 解析 → 可选清空当前集 → bulk insert（人已确认文件） |
| `insert_workorder` | 单行插入 |
| `update_workorder` / `delete_workorder` | 仓储实现；**对话 Tool 第一版不暴露**，表和 API 可内部具备 |
| 概览/历史 | SQL 聚合 / 按 assetnum |

种子：启动或 `scripts/import_default_xlsx.py` 把默认 xlsx 导入一次（幂等：空表才导入）。

### `agent`

- LangGraph `PostgresSaver.setup()` 表（`checkpoints` / `checkpoint_blobs` / `checkpoint_writes`），连接 `search_path=agent`。  
- **`pending_actions`**：`id`，`thread_id`，`tool_name`，`payload jsonb`，`status` (`pending|approved|rejected|expired|executed|failed`)，`created_at`，`resolved_at`，`actor_id` NULL，`result jsonb`。  
- 不把文件字节写入 checkpoint；只存 path / batch id。

### 迁移方式

与 Forge 类似的 **SQL 文件 + 顺序执行**（`scripts/sql/` + `schema_migrations` 表），另一次 `PostgresSaver.setup()`。不上 Flyway/Liquibase。本阶段不上 Alembic，除非 SQL 手写开始失控。

### 配置

`DATABASE_URL=postgresql://afvc:afvc@localhost:5432/afvc`  
Compose 只起 Postgres。应用仍本机 uvicorn（3a）。

`thread_id` 用 UUID 字符串，&lt; 255 字符（官方限制）。

---

## 4. LangGraph State / thread / checkpoint

**State（会话 thread）**

- `messages`（add reducer）  
- `last_assetnum`（模型或工具成功后更新，便于 UI）  
- `pending_action_ids: list[str]`（展示用；真相在表）  

**thread_id**

- 现在：`session_id`（前端已有 UUID）。  
- 以后多用户：**不改表结构**，改为 `thread_id = session_id` 仍成立，另用 `pending_actions.actor_id` / configurable 里可选 `user_id`。禁止把 thread 写成死常量 `"default"`。

**Checkpointer**

- 仅主图 `compile(checkpointer=PostgresSaver)`。  
- 数据子图作为节点调用，不 compile 第二份 saver。  
- 长对话裁剪：工具结果压缩后再进 messages（token）；checkpoint 保留策略本阶段可只文档化「N 天清理」，不写复杂 TTL。

**Store**

- 本阶段不用 LangGraph Store 做人批；人批用 SQL 表，查询/UI/审计更直。

---

## 5. Main Graph 节点与流转

```text
START → model（GLM + tools）
          ├─ 无 tool call → END（自然语言，含自己提出的澄清）
          └─ tool 节点
                ├─ safe → 执行 application → 回 messages → model
                └─ sensitive → 写 pending_actions，返回「未执行」→ model → END
```

- 最大 tool 步数（例如 8），防空转。  
- 系统提示：科学边界；缺参就问；**禁止**把用户口语当成写操作批准；列出 pending 时引导去点 UI 按钮。  
- **没有** `understand` 节点。  
- Fallback：`AFVC_AGENT_GRAPH=false` 或 LLM 异常 → 现 `handle_turn`（understand + 单用例 + 模板/GLM narrate）。

控制台 `/usecases/*` **不进图**。

---

## 6. Data Subgraph 与 Tool Registry

**P1：** 主图直接绑 Python tools，内部调 application（已 SQL）。不必先上子图。

**P2（Agent-first）：** 数据子图是数据域内部的职责组织与执行封装（无 LLM、不单独挂 checkpointer）。Main Agent 理解用户目标后，**自己**决定调用 `get_overview` / `get_device_history` 等能力、顺序和是否继续。子图 **不** 向模型暴露 `data_op` / `use_case` / `op` 枚举，也 **不** 重做 `_detect_device_use_case` 式语义路由。子图内部的 capability 名由已经被 Agent 选中的 Tool 传入，只负责执行。写能力在 P3 改为只创建 pending，仍不把「用户属于哪个功能」交给子图判断。

**Registry（一份表/一份 dict）**

| name | 层 | 档 | 第一版对话暴露 |
|------|----|----|----------------|
| get_overview | data | safe | 是 |
| get_device_history | data | safe | 是 |
| insert_workorder | data | sensitive | P3 提案 |
| import_workorders | data | sensitive | P3 提案（对话侧）；控制台上传直接执行 |
| list_high_risk | prediction | safe | 是 |
| predict_device_risk | prediction | safe | 是 |
| predict_fault_type | prediction | safe | 是 |
| advise_maintenance | app | safe | 是 |
| search_manual | app | safe | 是 |
| diagnose_device | app 组合 | safe | 是 |
| update_workorder | data | sensitive | 是（只提案） |
| delete_workorder | data | sensitive | 是（只提案） |

新能力 = 加一行 + 实现仍在 application。

---

## 7. HITL interrupt / approval / resume

### 原则对照

| 原则 | 实现 |
|------|------|
| Agent 自己决定何时调工具、如何继续聊 | 1c 主图；会话 thread 从不因人批而 `interrupt()` |
| 有副作用必须显式 Human Approval | 只有 `approve` API（及控制台上传按钮）调用 repo 写方法 |
| 不能从自然语言推断已批准 | 敏感 tool 无执行分支；系统提示禁止；不把「确认」映射成 approve |
| pending 不锁会话 | 提案后图结束；新 turn 普通 invoke |

### 进行中 double-text（图还在跑）

OSS 无官方 multitask。应用层 **reject**：返回 409 `run_in_progress`。Streamlit 已有 processing flag。

### 人批后的 resume

**不是** 对会话 thread `Command(resume=用户这句话)`。

批准流程：

1. 校验 `action_id` 属于该 `thread_id` 且 `pending`。  
2. 事务执行对应 repo 写。  
3. `status=executed`。  
4. 向会话 thread **append** 一条明确的工具结果消息（普通 input / update 消息，不是把用户原话当 resume）。  
5. 可选：再 invoke 主图一拍，让模型叙述结果（仍不能再偷偷写）。

拒绝：`status=rejected`，同样注入「用户拒绝了 {tool}」，可叙述。

多个 pending 并存；UI 列出；新对话不自动取消（避免误伤），提供拒绝按钮。

控制台上传：**人已经选文件并点按钮** = 该通道的显式批准，不走 pending 卡。避免同一人批两次。

---

## 8. API 迁移方案

| 端点 | 变化 |
|------|------|
| `POST /interaction/turn` | 保留。主路径主图。响应增加 `pending_actions[]`；进行中 409 |
| `POST /interaction/approve` | **新建** `{session_id, action_id}` |
| `POST /interaction/reject` | **新建** 同上 |
| `GET /interaction/sessions/{id}` | 可选：pending 列表 |
| `GET /usecases/*` | 保留；读 SQL |
| `POST /upload/workorders` | 保留路径；语义改为 import 进库 |

兼容：旧前端只要 `final_answer` + `session_id` 仍能聊；看不见批准按钮则**无法在对话里完成写入**（安全默认）。Streamlit 必须升级才能用对话导入。

`use_case` / `assetnum` / `last_assetnum` 继续返回（从 state / 最后 tool 填），状态条不用改协议。

---

## 9. Streamlit 兼容方案

- 六页导航、控制台 usecases **保留**。  
- `agent_session_id` 继续当 `thread_id`（不强制改名，减少测试噪音）。  
- 对话：`turn` 后若 `pending_actions` 非空，渲染卡片 + 批准/拒绝；**输入框不禁用**。  
- processing 仅覆盖「当前 run 未结束」。  
- 加载文案保持「调用诊断能力」，不要八节点口吻。  
- 上传页走 `/upload/workorders` 新语义；成功后概览应立刻反映库内数据。

---

## 10. 分阶段实施、验收、风险、回滚

### P0 — Persistence + 行级工单（先）

**做：** Compose Postgres；`001` SQL；`db.py` + `workorder_repo`；import 默认 xlsx；overview/history/upload 改 SQL；PostgresSaver.setup 连通（可先不接图）；config `DATABASE_URL`。

**验收：** pytest 绿；导入后 `get_data_overview` 与改前数量级一致；重启进程数据还在；无登录。

**风险：** Excel 类型/空列。缓解：沿用现有 Polars 清洗再 insert。  
**回滚：** `AFVC_DATA_BACKEND=file` 读最新 raw 文件。

### P1 — Main Agent

**做：** `graph.py` + tools 只读；`service.py` 分支；系统提示；LangSmith thread_id=session_id；fallback understand。

**验收：** `AFVC_USE_LLM=false` 仍 134+ 且走 fallback；LLM 开时多步只读（历史+风险）有集成测试可用 Fake 工具。

**风险：** 模型乱调工具。缓解：封闭 registry + 步数上限；出问题再加约束（1c）。  
**回滚：** `AFVC_AGENT_GRAPH=false`。

### P2 — Data subgraph + registry 收口

**做：** 只读数据能力的内部子图/模块封装 + 一份 Tool 注册表。主图继续暴露独立数据 Tool，**不要**改成单一 `data_op` 规则路由器。

**验收：** 概览/历史仍正确；子图无 LLM、不解析用户意图；父图仍唯一 checkpointer；模型侧 Tool 列表仍是具体能力而非 op 枚举。

**回滚：** 数据 Tool 改回直接调 application。

### P3 — HITL

**状态：已落地（本轮）。**

**做了：** `pending_actions` 状态机；敏感 tool 只提案；approve/reject API；Streamlit 待批卡片；控制台上传仍直接写。approve 使用 `FOR UPDATE` + 同一事务业务写入。Graph/DB 程序错误不再静默 fallback 到 `understand.py`。

**验收：** 对话提案不改库直到 approve；approve 后库变；reject 后永不执行；重复 approve 幂等；pending 时仍能只读聊天；口语「确认」不写库；进行中第二次 turn → 409。

### 不在本计划

登录、RBAC、预测训练、改 `data/mock` 路径、Agent Server / 官方 double-texting、多级 supervisor、pending 自动过期任务。

---

## 实施时任务切分（给执行 agent）

按 P0→P3 各开独立可测提交。每阶段：先测（仓储/API 契约）→ 改 IO/图 → 全量 pytest + text integrity + ruff。不要一提交里同时迁库又换主图又上 HITL。
