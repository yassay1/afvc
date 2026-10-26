# `backend/data/mock/`

可公开提交的 **v1 固定合成 DEMO**（36 台虚构设备、288 条工单、18 条任务；非真实线路运营数据）。使用 `python scripts/generate_demo_data.py` 可复现所有文件；生成器使用固定日期和 UUID，不依赖运行时间或随机数。

| 文件 | 用途 |
|------|------|
| `workorders_demo.csv` | demo 模式的唯一工单种子 |
| `prediction_results.csv` | 复发风险模型样例（`DEMO-AGM-*`） |
| `fault_prediction_results.csv` | 故障类型条件概率样例 |
| `station_importance.csv` | V1 站点重要度（模拟） |
| `crew_availability.csv` | V1 人员可用性（模拟排班） |
| `spare_parts.csv` | V1 备件库存（模拟） |
| `maintenance_tasks_demo.json` | 首次初始化的版本化任务与合成反馈 |

所有站名、线路 D01–D04、品牌、班组、备件和设备编号都是虚构的。真实工单 / 真实模型输出 **不要提交到 Git**。production profile 可以将 xlsx 放到 `backend/data/raw/`；demo profile 不会读取该目录。
