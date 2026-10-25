# AFVC 编排层（Agent 架构）

本文描述**对话入口内部**怎么搭。产品边界见 [PRODUCT.md](./PRODUCT.md)；两大业务模块见 [ARCHITECTURE.md](./ARCHITECTURE.md)。  
本文**不是** Cursor 用的 `AGENTS.md`。

## 1. 选型（先读这节）

| 类型 | 含义 | 本项目 |
|------|------|--------|
| **A. 工具循环 Agent** | 模型决定是否调 Tool → 执行 → 再决策 → 叙述；业务在 Tool 里 | **采用** |
| **B. 业务多节点图** | 固定/半固定：意图→预测→建议→派工… | **不采用** |

实现上可用 LangGraph，但图只表达 **model ⇄ tools** 循环，**不**把「预测 / 维修作业」画成主图上的业务节点。这两大模块通过 **Tool → Application 原子能力** 接入。

```text
用户 → 对话入口 → 主图(model ⇄ tools) → Tool → Application
                                      ↘ 控制台/HTTP 也可直达 Application
```

## 2. 主图（运行时）

```text
        START
          │
          ▼
       ┌──────┐  有 tool_calls   ┌───────┐
       │ model│ ───────────────▶ │ tools │
       └──┬───┘                  └───┬───┘
          │ 无 tool_calls            │
          ▼                          │
         END ◀───────────────────────┘
              （tools 后再回 model）
```

| 节点 | 职责 |
|------|------|
| `model` | 带系统提示与会话消息调 LLM；未达轮次上限时 `bind_tools` |
| `tools` | 执行已注册 Tool（内部调 Application）；更新 `last_assetnum`、工具轮次 |

约束示例：单轮工具轮次上限（实现中有 `MAX_TOOL_ROUNDS`）；超出则结束循环并给出当前可给的答复。

## 3. 运行时组件

| 组件 | 职责 |
|------|------|
| 对话入口 | `/interaction/*`：组会话、调主图或兜底、返回叙述与待批列表 |
| 主图 | 上文 model ⇄ tools |
| Tool 注册表 | 名称 → Application 用例；按预测 / 维修作业 / 知识 / 数据分组 |
| 会话状态 | 消息、`last_assetnum`、工具轮次等；外层可挂 checkpointer |
| 护栏 | 系统提示与策略：缺参澄清、敏感写只提案、**禁止对建议列表 LLM 重排** |
| HITL | 工单类敏感写 → `pending_actions` → 显式批准/拒绝 |
| 规则兜底 | LLM 关闭或供应商不可用时走规则路径；图/DB 程序错误不静默吞掉 |

## 4. Tool 与模块

| 分组 | 能力方向 | 说明 |
|------|----------|------|
| 预测 | 风险、高风险榜、故障类型 | 可占位；只读为主 |
| 维修作业（只读已接线） | `list_maintenance_suggestions`、`list_maintenance_tasks` | 与 HTTP 共用 Application；建议顺序与 `reasons` 由服务端决定，**禁止**模型重排 |
| 维修作业（写，未暴露为 Tool） | 创建 / 调整 / 反馈 / 接受建议 | **明确确认路径 = 控制台或 HTTP**（`/usecases/maintenance/*`）；**不**并入 `pending_actions`；Agent 只读建议/任务后引导用户走该路径 |
| 知识 | 手册/SOP 检索 | 支撑；按需 Tool 调用，不以 Prompt 当唯一库 |
| 数据 | 概览、历史等 | 按需 |
| 敏感写 | 工单增删改/导入等 | 仅提案，须 HITL（与检修任务两条线） |

`advise_maintenance` 为单设备 SOP/巡检向参考；`list_maintenance_suggestions` 为今日检修排序清单——二者不同。`diagnose_device` 为设备综合聚合快捷，不是今日安排主路径。

HTTP 形状见 [API.md](./API.md)。

## 5. 写操作两条线

```text
对话里的工单类写  ──▶ pending_actions ──▶ 批准 / 拒绝（口语「好的」≠ 批准）
检修任务写        ──▶ Application maintenance_tasks（HTTP/控制台显式调用）
                 Agent 不注册写 Tool，避免与工单 HITL 混线
```

## 6. 一轮对话（逻辑顺序）

1. 用户话进入对话入口，载入会话状态  
2. `model` 决定调 Tool 或直接答  
3. 若调 Tool：执行原子能力，结果回消息列表，再进 `model`  
4. 若敏感写：只产待批提案，本轮正常结束并提示确认  
5. 无更多 Tool 时输出自然语言答复  

## 7. 降级

| 情况 | 行为 |
|------|------|
| `AFVC_USE_LLM=false` 或模型供应商不可用 | 规则兜底：可映射今日建议 / 检修任务列表（及原有概览、高风险、单设备用例）；任务写仍请走控制台 / HTTP |
| 主图 / DB / 用例抛错 | 按错误返回；不伪装成「模型繁忙」 |

## 8. 非目标

- 业务多节点流水线（选型 B）  
- 多 Agent 联邦、演示用复杂子 Agent 树  
- 在编排层重写风险/打分/任务状态机  

## 9. 相关文档

| 文档 | 内容 |
|------|------|
| [PRODUCT.md](./PRODUCT.md) | 产品是什么 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 预测 / 维修作业 / 分层 |
| [API.md](./API.md) | HTTP 与对话契约 |
| [DATA.md](./DATA.md) | 数据约定 |
