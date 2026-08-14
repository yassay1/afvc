# `backend/data/mock/`

目录名是历史遗留，**不是** statistical baseline，也不是随机假数据。

这里放的是**外部预测模型结果表**（CSV）：

| 文件 | 用途 | 读取方 |
|------|------|--------|
| `prediction_results.csv` | 各设备多窗口复发风险 | `backend.infrastructure.risk_table` |
| `fault_prediction_results.csv` | 故障类型条件概率 | `backend.infrastructure.fault_table` |

有表则 `prediction_tier=model`；没有风险表时，`application/risk.py` 使用工单频次/间隔的 **statistical baseline**（与本目录无关）。

后续若做目录规范化，可迁到 `backend/data/model_outputs/`，并同步改两个 PATH 常量。当前不移动，避免打断已有 CSV 与测试。
