# AFVC Agent 架构设计

日期：2026-08-14  
状态：V1 已落地；当前验收 provider 为 DeepSeek（OpenAI 兼容）  
范围：对话 Agent 怎么挂在「数据 / 预测 / 对话」三模块上；不包含具体训练预测模型。

---

## 1. 产品定位

AFVC 仍是地铁 AFC 工单的**诊断能力平台**。对外三块：

| 模块 | 职责 |
|------|------|
| **数据管理** | 工单等业务数据的增删改查 + 统计/分布/时间范围等数据侧分析。设备历史查询属于这里。 |
| **预测模型** | 机器学习等算法产出复发风险、故障类型等；对外是预测服务。模型未到位前可用可解释统计基线，须如实标注。 |
| **Agent 对话** | 会用这个系统的人：理解意图、选能力、补参、多步、叙述。不拥有业务算法，只编排前两块及建议/手册等工具。 |

控制台仍可直接打 HTTP 用例 API（不经过 Agent）。对话工作台只走 Agent API。

科学边界不变：风险 ≠ 故障日期；建议 ≠ 根因；条件概率 ≠ 必然发生。

---

## 2. 已拍板的决策

| 议题 | 决策 |
|------|------|
| 工具开放度 | 对**平台已注册能力**开放（function calling + 工具注册表）。不是无边界上网/写代码。新功能 = 注册新工具。 |
| 综合诊断 | 保留 `diagnose_device` 作为**可选组合快捷工具**；Agent 也可逐步串原子工具。不是只能二选一。 |
| LLM 职责 | 主路径上像「一个人」：意图、选工具、多步、叙述。规则路由仅作 LLM 不可用时的兜底。 |
| 副作用 | 读写都开放，但写操作必须 **Human-in-the-Loop**：提案 → 人确认/拒绝 → 再执行。 |
| 数据「子代理」 | **产品上**叫数据子代理；**实现上**用 LangGraph **子图节点**，不要用 `@tool` 包一层带 LLM 的子 Agent（否则 HITL 时父图看不到内部状态）。 |
| 预测第一版 | 不必单独做带 LLM 的子代理；只读、工具少，由主 Agent 直接调。 |
| 可观测 | 上 LangSmith：每次对话 `thread_id` = `session_id`。 |
| 数据库 | 同一 Postgres：**业务库**（工单 CRUD）+ **Agent 状态库**（Checkpointer / 会话 / 待确认）。只给**最外层图**挂 checkpointer。 |

---

## 3. 子代理 vs 子图（实现约束）

二者不是同义词：

- **Subagent**：协作模式。主 Agent 协调专项能力，官方常见写法是把子 Agent 包成 tool。默认无会话记忆、上下文隔离；多一次模型回传。包成 tool 后父图 **get_state 看不到内部**，interrupt 不好做。
- **Subgraph**：LangGraph 机制。图套图，管状态传递与 checkpoint。里面可以没有 LLM（纯 SQL/规则）。要在暂停时读嵌套状态，应把子图 **当作节点** 调用。

AFVC 数据域：读路径尽量确定性（SQL/用例），不必再套一层 LLM；写路径 `interrupt` 必须对父图可见 → **数据子图节点**。

工具变多时：膨胀发生在子图内部，主对话只看到少数「部门入口」，避免把几十个 tool schema 塞进主模型上下文。

参考：

- [Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents)
- [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangSmith observability](https://docs.langchain.com/langsmith/observability-concepts)

---

## 4. 运行时结构

```text
Frontend 控制台 ──► /usecases/* 、/upload/* （不经 Agent）
Frontend 对话台 ──► Agent API
                         │
                    主图（LangGraph）
                    checkpointer = Postgres
                    tracing = LangSmith thread_id
                         │
         ┌───────────────┼────────────────┐
         ▼               ▼                ▼
   数据子图节点      预测工具（只读）    建议 / 手册工具
   读：SQL/统计      risk / fault_type   advise / search_manual
   写：interrupt
         │
         ▼
   Postgres business schema
```

主图职责：对用户说话、决定调哪个部门/工具、把 HITL 冒泡到前端、压缩工具结果再进上下文。

数据子图职责：执行数据模块能力；写操作先暂停等人。

Application 用例（概览、历史、风险、建议、手册、故障类型、综合诊断）仍是**业务实现**；Agent 调的是包装后的工具，不是把 SQL 写进提示词。

---

## 5. 工具注册表

### 5.1 Safe（直接执行）

| Tool | 模块 |
|------|------|
| `get_overview` | 数据 |
| `get_device_history` | 数据 |
| `list_high_risk` | 预测 |
| `predict_device_risk` | 预测 |
| `predict_fault_type` | 预测 |
| `advise_maintenance` | 知识/应用 |
| `search_manual` | 知识/应用 |
| `diagnose_device` | 可选组合 |

数据类 Safe 工具由**数据子图**执行（主图一次调用可在子图内完成多次读）。预测/知识第一版可由主图直接绑工具。

### 5.2 Sensitive（必须人批）

| Tool | 说明 | 第一版 |
|------|------|--------|
| `upload_workorder` | 上传/写入工单 | 实现 |
| `update_workorder` | 修改工单 | 可占位，暂不暴露给模型 |
| `delete_workorder` | 删除工单 | 可占位，暂不暴露给模型 |

人批卡片至少包含：拟执行工具名、关键参数摘要、不可回滚提示。拒绝则不写库，Agent 用自然语言说明已取消。

---

## 6. 一轮对话状态机

```text
用户发言 → 主图 LLM
    ├─ 直接回话（闲聊 / 解释 / 要补参）
    └─ 调能力
           ├─ Safe → 执行 → 结果回灌（可多步）→ 叙述
           └─ Sensitive → interrupt
                  ├─ POST approve → 执行 → 回灌 → 叙述
                  └─ POST reject  → 不执行 → 告知取消
```

约束：

- 单轮可多步 Safe；不是每一步都问人。
- 工具返回进模型前做压缩（截断 JSON、只留关键字段），控制 token。
- 限制最大工具步数，防止空转。
- 会话记住：`session_id`、短消息窗、`last_assetnum`、待确认的 tool call。
- LLM 不可用时：回退现有规则路由 + 模板叙述（测试 `AFVC_USE_LLM=false` 仍可跑）。

---

## 7. HTTP API 演进

现有：`POST /interaction/turn`（`query` + `session_id`）→ 规则 `handle_turn`，一次一个用例。

目标：同一前缀演进，前端仍只打对话 API。

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/interaction/turn` | 用户一句话。可能直接结束，或返回 `status=awaiting_approval` |
| POST | `/interaction/approve` | 批准当前会话挂起的写操作 |
| POST | `/interaction/reject` | 拒绝 |
| GET | `/interaction/sessions/{id}` | 可选：会话摘要 / 待确认内容 |

`turn` 响应形态（概念字段，实现时可微调）：

- `status`: `success` | `clarified` | `awaiting_approval` | `rejected` | `error`
- `final_answer`: 给用户看的文本（待确认时为「拟执行…请确认」）
- `session_id`
- `pending_action`: 仅待确认时有（tool 名、参数摘要）
- `use_case` / `assetnum` / `last_assetnum`: 可保留，便于 UI 状态条
- `result`: 可选结构化结果，控制台调试用

兼容策略：

- 路径 `/interaction/turn` **保留**，语义从「一次一用例」升级为「一轮 Agent」。
- 旧前端若忽略新字段，只要仍读 `final_answer` + `session_id` 就能说话；待确认时必须升级以渲染批准按钮。
- 控制台 `/usecases/*` 不变；上传页可与 Agent 的 `upload_workorder` 共用数据模块，避免两套写入逻辑。

---

## 8. 数据库

同一 Postgres 实例，两套 schema：

| Schema | 内容 |
|--------|------|
| `business` | 工单主表及查询所需字段（从 Excel/CSV 迁入或双写过渡） |
| `agent` | LangGraph checkpointer 表；会话与 interrupt 状态。不要把大文件塞进 checkpoint，文件存对象路径，状态里只存引用。 |

迁移节奏建议：

1. 先挂 Agent checkpointer（对话/HITL 可恢复），业务读路径仍可暂时读文件。  
2. 工单迁 `business`，数据子图改走 SQL。  
3. 上传写库；文件仅作导入源或备份。

默认数据文件仍可作为**导入种子**，不再作为运行时唯一真相。

---

## 9. LangSmith

- `LANGSMITH_TRACING=true` 时自动打点（LangChain/LangGraph 集成）。
- `thread_id` = `session_id`，多轮在同一 thread。
- 主图节点、数据子图、模型调用、工具调用同属一条 trace。
- 元数据建议带：`prediction_tier`、是否 HITL、环境（dev/prod）。
- 大 payload 不要整包进 trace（与 checkpoint 同一原则）。

---

## 10. 明确不做（本设计）

- 恢复旧八节点 Agent / 开放 Tool Calling 平台（工具集仍是平台注册表）。
- 预测模型训练本身（只定如何消费结果表/服务）。
- 第一版暴露改/删给模型（表结构可预留）。
- 多级 Supervisor 套 Supervisor。
- 子图各自再挂 checkpointer。

---

## 11. 分阶段落地（实现时再拆计划）

1. 主图 + 现有只读工具 + GLM 叙述 + LangSmith thread。  
2. Postgres checkpointer + `approve`/`reject` + `upload_workorder` HITL。  
3. 数据子图 + 工单进 `business`。  
4. 视工具膨胀再拆预测子图或工具检索。

---

## 12. 与现行文档的关系

`docs/architecture.md` 仍写「薄 Interaction、一次一用例、Application 唯一聚合」。本设计是 Agent 方向的**下一目标**；批准并实现后应回写 architecture：Interaction 升级为主图 Agent，Application 仍实现业务能力，综合诊断仍可在 Application 聚合，但不再禁止 Agent 逐步调用原子工具。
