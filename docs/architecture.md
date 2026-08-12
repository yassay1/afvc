# AFVC 目标架构

本文只描述**目标设计**：诊断能力平台 + 薄对话入口。不描述历史实现对照。

## 1. 定位

AFVC 提供可复用的 AFC 运维**诊断能力**（Application 用例）。自然语言入口（Interaction）可选，用于：

- 将用户意图路由到既有用例
- 在缺参时澄清（如设备编号）
- 多轮指代（如沿用上一设备）
- 将结构化结果叙述为可读答复，并附带科学边界

**Application 是业务唯一编排者。** Interaction 不得二次拼装风险、历史、建议等业务步骤。

## 2. 分层

```
┌─────────────────────────────────────┐
│  Frontend（控制台 / 可选 Chat）       │
├─────────────────────────────────────┤
│  API                         │ Interaction（可选）│
│  HTTP → Application          │ 理解→澄清→调用→叙述 │
├─────────────────────────────────────┤
│  Application（用例）                  │
├─────────────────────────────────────┤
│  Domain（纯规则）                     │
├─────────────────────────────────────┤
│  Infrastructure（IO / LLM / 检索实现） │
└─────────────────────────────────────┘
```

依赖只允许向下。Interaction 与 API 都只依赖 Application（及必要时的会话存储），不直连 Domain 规则实现细节以外的旁路业务拼装。

## 3. 模块分工

### 3.1 产品核心

| 模块 | 职责 | 不负责 |
|------|------|--------|
| **Application** | 用例：概览、高风险榜、历史、风险、建议、手册、故障类型、**综合诊断** | 对话状态机、意图闲聊策略 |
| **Interaction** | 理解意图、补参、调用**一个**主用例（或明确的只读组合策略）、叙述、短记忆 | 业务聚合、工具规划主路径、证据 replan 引擎 |

综合诊断只在 Application 的 `diagnose_device`（名称可调整）中编排一次。

### 3.2 支撑模块

| 模块 | 职责 | 不负责 |
|------|------|--------|
| **Domain** | 预警阈值、故障类别枚举、概率组合、边界文案常量 | 文件 IO、HTTP、LLM |
| **API** | 校验、鉴权占位、调用 Application、错误映射 | 业务计算、对话记忆 |
| **Infrastructure** | 工单读写、外部结果适配、手册检索实现、LLM 客户端 | 领域决策、用例流程 |
| **Frontend** | 展示与调用 API | 内嵌业务规则 |

### 3.3 目标目录

```
backend/
  api/
  application/
  domain/
  infrastructure/
  interaction/
frontend/
docs/
  architecture.md
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

**同一用例**同时服务 HTTP 与 Interaction；Chat 不增加平行业务实现。

## 5. Interaction 设计要点

### 5.1 只做四步

1. **理解** — 映射到用例（或闲聊 / 越界 / 需澄清）
2. **补参** — 缺 `assetnum` 等则追问；多轮可继承 `last_assetnum`
3. **调用** — 调用 Application；主路径一次一个主用例
4. **叙述** — 基于用例返回的结构生成答复，禁止编造数值与手册条目

### 5.2 禁区

- 不在 Interaction 内串联多个底层能力来「手搓」综合诊断（应调 `diagnose_device`）
- 不以「工具规划 + 证据评估 + replan」作为主路径骨架
- 不把 Application 能力伪装成需模型自主挑选的开放 Tool Calling 平台（本域工具集封闭、意图可枚举）

### 5.3 会话

进程内或外置均可；语义上只需保留短对话历史与 `last_assetnum`（及必要的上一用例摘要）。会话存储属于 Infrastructure，策略属于 Interaction。

## 6. 科学边界（硬约束）

1. 不预测具体故障发生日期；只表达窗口内再次产生故障工单的可能性  
2. 建议是巡检方向，不是根因鉴定  
3. 不得将条件概率表述为实际发生概率或「一定发生」  
4. 手册检索内容须可追溯来源，不得编造条目  

Application 输出与 Interaction 叙述均须遵守；叙述层不得放松。

## 7. 前端与 HTTP 入口

- **控制台页**：直接打用例 API — `GET /usecases/overview`、`/usecases/high-risk`、`/usecases/devices/{assetnum}/diagnosis` 等；上传走 `POST /upload/workorders`
- **对话工作台**：只走 `POST /interaction/turn`（`query` + `session_id`）→ Interaction → Application，不在浏览器拼业务
- 完整路径表见 [README.md](../README.md)

## 8. 质量期望

- 用例可单测，不依赖 LLM  
- Interaction 在关闭 LLM 时仍能规则路由到用例并给出模板/结构化叙述兜底  
- 文本与编码按仓库既有 UTF-8 规范治理  
