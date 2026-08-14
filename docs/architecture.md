# AFVC 架构

当前已实现：Postgres 行级工单 + 诊断能力平台 + LangGraph 主图 Agent + HITL 写操作审批。  
人批路径是：Agent 提案 → `pending_actions` → 当前 run 正常结束 → 显式 approve/reject API → DB 写入。不是会话 thread 暂停/恢复。

产品三层：

| 层 | 代码位置 | 职责 |
|----|----------|------|
| 数据 | `application/overview.py` `history.py`；`infrastructure/workorder_repo.py`；`api/upload_api.py` | 导入、CRUD、统计、历史。Excel 只是 import 源 |
| 预测 | `application/risk.py` `fault_type.py`；`infrastructure/risk_table.py` `fault_table.py` | 风险与故障类型 |
| 对话 | `backend/agent/`；`interaction/` 兜底；`api/interaction_api.py` | LLM+Graph 开启时主图选 Tool；写操作只提案；LLM 关闭时 understand 规则兜底 |

建议与手册是应用/知识能力，由 Application 实现、Agent 可调用，**不属于数据管理**。

---

## 1. 定位

AFVC 提供可复用的 AFC 运维**诊断能力**（Application 用例）。自然语言入口在 `AFVC_USE_LLM=true` 且 `AFVC_AGENT_GRAPH=true` 时走 LangGraph 主 Agent：理解目标、自主选工具、多步调用、叙述。写工具只生成待审批提案。LLM 关闭或模型供应商不可用时，退回 `understand.py` 规则路由 + 单用例 + 叙述。图/工具/数据库的程序错误 **不会** 静默降级。

**Application 仍是业务算法唯一实现者。** Agent 只编排已注册工具，不重写 risk / fault / advice / manual / diagnose。

## 2. 分层

```
┌──────────────────────────────────────────┐
│  Frontend（控制台 / Chat）                 │
├──────────────────────────────────────────┤
│  API /usecases /upload    │ /interaction │
│  不经 Agent               │ 主图或兜底     │
├──────────────────────────────────────────┤
│  LangGraph 主图（可选）                     │
│  model ⇄ tools；无 understand 节点         │
├──────────────────────────────────────────┤
│  Application（用例）                        │
├──────────────────────────────────────────┤
│  Domain（纯规则）                           │
├──────────────────────────────────────────┤
│  Infrastructure（Postgres / CSV / LLM）    │
└──────────────────────────────────────────┘
```

控制台 `/usecases/*` 不进图。对话主路径不经过 `understand.py`。

## 3. 模块分工

### 3.1 产品核心

| 模块 | 职责 | 不负责 |
|------|------|--------|
| **Application** | 用例：概览、高风险榜、历史、风险、建议、手册、故障类型、**综合诊断**；写操作审批服务 | 对话状态机、意图闲聊策略 |
| **Agent** | 理解用户目标、选择/组合 Tool、澄清缺参、叙述；sensitive Tool 只提案 | 业务数值算法、直接写库、批准/拒绝 |
| **Interaction 兜底** | `AFVC_USE_LLM=false` / `AFVC_AGENT_GRAPH=false` / 模型供应商不可用：understand → 单用例 → 叙述 | 工具规划主路径；吞掉 Graph/DB 程序错误 |

综合诊断只在 Application 的 `diagnose_device` 中编排一次；Agent 也可逐步串原子工具。

### 3.2 支撑模块

| 模块 | 职责 | 不负责 |
|------|------|--------|
| **Domain** | 预警阈值、故障类别枚举、概率组合、边界文案、pending 状态机 | 文件 IO、HTTP、LLM |
| **API** | 校验、调用 Application / Interaction、错误映射 | 业务计算、审批状态机 |
| **Infrastructure** | 工单 SQL、pending_actions IO、Excel 解析、手册检索、LLM 客户端、checkpointer | 领域决策、用例流程 |
| **Frontend** | 展示与调用 API，含待批卡片 | 内嵌审批/写库逻辑 |

### 3.3 目标目录

```
backend/
  api/
  application/
  agent/              主图、Tool 包装、数据子图（内部执行）
  domain/             含 pending 状态机
  infrastructure/     db / workorder_repo / pending_action_repo / Excel 解析
  interaction/        对话编排；LLM 关闭或供应商不可用时的规则兜底
  application/        用例 + capabilities 目录 + approvals
frontend/
docs/
README.md
```

## 4. Application 用例

| 用例 | 说明 |
|------|------|
| `get_data_overview` | 工单数据概览 |
| `list_high_risk_devices` | 高风险设备 Top N |
| `get_device_history` | 单设备历史 |
| `predict_device_risk` | 多窗口风险 + 预警 |
| `advise_maintenance` | 维修建议 / SOP 参考 |
| `search_manual` | 手册检索 |
| `predict_fault_type` | 故障类型（有数据则提供） |
| `diagnose_device` | 综合诊断（唯一聚合） |

平台类接口（如健康检查、工单上传）属于 API/运维面，不计入上表「诊断用例核心」。

**同一用例**同时服务 HTTP 与 Agent Tool；Chat 不增加平行业务实现。

## 5. Agent 主路径

```
START → model（GLM + 封闭 Tool）
          ├─ 无 tool call → END
          └─ tools → model → …（最多 8 轮）→ END
```

- 没有 `understand` 节点，也没有 `data_op` / `use_case` 规则路由器。
- 数据子图是数据域内部执行封装：capability 名由已被 Agent 选中的 Tool 传入。
- Checkpointer 只挂最外层图（PostgresSaver，schema `agent`）。
- 进行中的同一 `session_id` 再发 turn → 409 `run_in_progress`。
- safe / sensitive 分类的唯一来源是 `application/capabilities.py`。
- 写工具只调用 `approvals.propose_write`；真正写入只发生在 `approvals.approve`（`FOR UPDATE` + 同一事务业务写 + `pending → executed`）。
- 口语「好的 / 确认」不会走 approve API。
- 回滚对话主路径：`AFVC_AGENT_GRAPH=false` 或 `AFVC_USE_LLM=false` → understand 兜底。模型供应商不可用 → 可观测降级。图/DB/程序错误 → 500，不降级。

## 5.1 HITL 状态机

`pending → executed | rejected | failed | expired`

`executed` / `rejected` / `failed` / `expired` 为终态。重复 approve 已 executed 的单据返回幂等成功，不二次写入。rejected 不能再 approve。业务写失败时事务回滚，再把仍为 pending 的行标为 `failed`。

控制台 `POST /upload/workorders` 仍直接写库（人已点上传 = 该通道已批准）。

## 6. 科学边界（硬约束）

1. 不预测具体故障发生日期；只表达窗口内再次产生故障工单的可能性  
2. 建议是巡检方向，不是根因鉴定  
3. 不得将条件概率表述为实际发生概率或「一定发生」  
4. 手册检索内容须可追溯来源，不得编造条目  

Application 输出与 Agent 叙述均须遵守；叙述层不得放松。

## 7. 前端与 HTTP 入口

- **控制台页**：直接打用例 API — `GET /usecases/overview`、`/usecases/high-risk`、`/usecases/devices/{assetnum}/diagnosis` 等；上传走 `POST /upload/workorders`（落盘 + import 进 Postgres）
- **对话工作台**：`POST /interaction/turn`；待批卡片走 `POST /interaction/approve` / `reject`。输入框在 pending 时不禁用。
- 完整路径表见 [README.md](../README.md)

## 8. 质量期望

- 用例可单测，不依赖 LLM  
- `AFVC_USE_LLM=false` 时仍走 understand 兜底并给出模板叙述  
- HITL 契约测试覆盖提案不写库、重复批准、拒绝后不可批准、写失败回滚、口语确认无效  
- 文本与编码按仓库既有 UTF-8 规范治理  
