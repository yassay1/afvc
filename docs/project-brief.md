# AFVC 项目简述

AFVC 是地铁 AFC 设备的**诊断能力平台**，产品上分三层：

| 层 | 职责 |
|----|------|
| 数据 | 工单上传、查询、统计、设备历史 |
| 预测 | 复发风险、故障类型（有模型表则用模型，否则风险走 statistical baseline） |
| 对话 | 当前为 Interaction（规则路由 + 可选 GLM 叙述）；下一阶段见 Agent 架构 spec |

业务编排在 Application；综合诊断只有一个聚合用例。HTTP 与对话暴露同一组能力。

详见 [architecture.md](./architecture.md)、[engineering.md](./engineering.md)、根目录 [README.md](../README.md)。
