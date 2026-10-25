# `backend/data/mock/`

可公开提交的**合成 DEMO**（明确标注，非真实线路运营数据）：

| 文件 | 用途 |
|------|------|
| `workorders_demo.csv` | 无本地真实 xlsx 时的工单种子 / file 回退 |
| `prediction_results.csv` | 复发风险模型样例（`DEMO-AGM-*`） |
| `fault_prediction_results.csv` | 故障类型条件概率样例 |
| `station_importance.csv` | V1 站点重要度（模拟） |
| `crew_availability.csv` | V1 人员可用性（模拟排班） |
| `spare_parts.csv` | V1 备件库存（模拟） |

真实工单 / 真实模型输出 **不要提交到 Git**。本地可将 xlsx 放到 `backend/data/raw/`。
