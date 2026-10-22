# `backend/data/mock/`

目录名是历史遗留，**不是** random 假业务库。

这里只放**可公开提交的合成示例**预测结果表（CSV），供本地无真实模型输出时演示 `prediction_tier=model` 路径：

| 文件 | 用途 | 读取方 |
|------|------|--------|
| `prediction_results.csv` | 各设备多窗口复发风险 | `backend.infrastructure.risk_table` |
| `fault_prediction_results.csv` | 故障类型条件概率 | `backend.infrastructure.fault_table` |

真实线路的模型输出、工单 Excel **不要提交到 Git**。本地可覆盖这两个 CSV，或把工单放到 `backend/data/raw/`（已 gitignore）后走 statistical baseline。

有表则 `prediction_tier=model`；没有风险表时，`application/risk.py` 使用工单频次/间隔的 **statistical baseline**。
