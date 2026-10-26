# AFVC 架构

本文描述系统怎么拆、主路径怎么走。产品边界见 [PRODUCT.md](./PRODUCT.md)。对话 Agent（工具循环）见 [ORCHESTRATION.md](./ORCHESTRATION.md)；接口见 [API.md](./API.md)；数据见 [DATA.md](./DATA.md)。

成熟预测性维护 / PHM 实践普遍把 **推理（预测）** 与 **作业执行（类 CMMS）** 分开，中间经建议与人工确认再落到任务；入口可以是 Agent、控制台或 API，**领域模块不依赖入口而存在**。

## 1. 总览

```text
        Agent（主入口）     控制台 / HTTP（无 Agent 也可用）
                 \               /
                  \             /
                   ▼           ▼
              原子能力（Application 用例）
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   ┌───────────┐      ┌─────────────┐
   │ 预测模块   │ ───▶ │ 维修作业模块 │
   │（可占位）  │      │ 建议·调度·反馈 │
   └───────────┘      └──────┬──────┘
                             │
                      知识检索（支撑能力）
```

| 原则 | 说明 |
|------|------|
| 业务算法唯一实现 | 风险、建议打分、任务状态等只在 Application / Domain；Agent 只编排 |
| 模块可独立使用 | 预测、维修作业均可通过 HTTP/控制台验收，不强制经过 Agent |
| 预测可占位 | 外部结果表或统计基线即可；不阻塞维修作业主设计 |
| 同一能力多入口 | Tool 与 `/usecases/*` 指向同一用例实现 |

## 2. 领域模块

### 2.1 预测

**职责：** 提供设备侧复发风险、高风险排序、故障类型等输入。

**典型原子能力：** `predict_device_risk`、`list_high_risk_devices`、`predict_fault_type`。

**实现要点：** 优先读外部预测表；无表或与工单 `assetnum` 对不齐时回退统计基线或标明不可用。算法本身不是本仓库的产品核心。

### 2.2 维修作业

**职责：** 把预测用起来——生成可解释的检修建议、可调整的检修任务（调度/分配）、执行反馈写回。

**典型原子能力：** `list_maintenance_suggestions`、检修任务创建/列表/调整、执行反馈。

**实现要点：** 建议排序为确定性加权规则并输出 `reasons[]`；任务对象独立于工单对话审批（见 §5）。

### 2.3 知识检索（支撑）

**职责：** 手册 / SOP 等检索，供 Agent 与作业侧调用。

**典型原子能力：** `search_manual`。

不单开第三业务域；在架构图上作为维修作业旁的支撑能力。

### 2.4 数据基础

工单导入、概览、设备历史等为两大模块提供工作集，不单独命名为业务域。真相源与文件约定见 [DATA.md](./DATA.md)。

## 3. 运行时分层

| 层 | 职责 | 不负责 |
|----|------|--------|
| Frontend | 对话为主入口；控制台直调用例 | 业务计算、写库策略 |
| API | 路由、校验、错误映射 | 业务算法 |
| Agent | 理解目标、选 Tool、多步编排、叙述；敏感写只提案 | 打分公式、直接写库 |
| Application | 原子能力编排与用例 | 对话状态机、意图闲聊策略 |
| Domain | 纯规则（预警、建议权重、任务状态） | IO、HTTP、LLM |
| Infrastructure | Postgres、CSV、手册检索、会话、LLM 客户端 | 领域决策 |

代码上大致对应：`backend/api`、`backend/agent`、`backend/application`、`backend/domain`、`backend/infrastructure`、`frontend/`。

## 4. 主路径

### 4.1 有 Agent（产品主路径）

1. 用户提出检修相关目标  
2. Agent 选择并组合原子能力（读预测 → 拉检修建议 / 查任务 → 可选知识补充）
3. 工单类敏感写经 `pending_actions` 明确批准后落库；**检修任务写**经控制台或 `/usecases/maintenance/*` 显式调用（与 HITL 分线，见 §5）  
4. 执行反馈经维修作业 HTTP 写回，供复盘  

### 4.2 无 Agent

同一能力经 `/usecases/maintenance/*`（及预测相关用例）与控制台完成建议 → 计划 → 反馈。

## 5. 关键决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 建议如何排序 | 确定性规则 + 可解释 `reasons` | 可测、可复盘；避免 LLM 静默改优先级 |
| 检修计划存哪 | 独立 `maintenance_tasks` | 与工单 CRUD 的对话 HITL（`pending_actions`）语义不同 |
| 预测深度 | 允许占位 | V1 价值在作业闭环；预测可后接真实模型表 |
| 知识放哪 | 支撑原子能力，非第三域 | 体量小；服务 Decide/现场，不服务「再训一个模型」 |

## 6. 相关文档

| 文档 | 内容 |
|------|------|
| [PRODUCT.md](./PRODUCT.md) | 产品是什么、范围 |
| [ORCHESTRATION.md](./ORCHESTRATION.md) | Agent：model⇄tools、Tool、HITL、降级 |
| [API.md](./API.md) | HTTP / 对话契约 |
| [DATA.md](./DATA.md) | 数据源与对齐 |
| [../README.md](../README.md) | 启动方式 |
