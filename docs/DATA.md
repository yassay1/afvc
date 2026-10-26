# AFVC 数据约定

说明数据从哪来、什么是真相、公开 DEMO 与本地真实如何区分。字段级 schema 以 SQL 迁移与解析代码为准，本文不维护第二份全量数据字典（避免与实现漂移；参见常见 data dictionary 实践：总述 + 关键键，细节跟 schema）。

产品与模块见 [PRODUCT.md](./PRODUCT.md)、[ARCHITECTURE.md](./ARCHITECTURE.md)。

## 1. 真相源

| 数据 | 运行时真相 | Import / 样例 |
|------|------------|----------------|
| 工单工作集 | Postgres `business.workorders`（默认） | Excel/CSV → `POST /upload/workorders` 或空库种子 |
| 检修任务 | Postgres `business.maintenance_tasks` | 紧急 file 回退：本地 JSON（不提交） |
| 对话待批写 | Postgres `agent.pending_actions` | 仅对话 HITL，不是检修任务 |
| 预测风险表 | 读 `backend/data/mock/prediction_results.csv`（可被本地覆盖策略扩展） | 合成 DEMO 或本地真实模型输出 |
| 故障类型表 | `backend/data/mock/fault_prediction_results.csv` | 同上 |
| 模拟资源 | `station_importance` / `crew_availability` / `spare_parts` CSV | **明确为模拟**，非真实排班/库存系统 |
| 手册 | `backend/data/knowledge/manuals/` | 样例 Markdown |

`AFVC_DATA_PROFILE=demo` 时仅允许 SQL 后端，连接本机 `127.0.0.1:55433/afvc_demo`，并只加载本仓 `backend/data/mock/` 的合成数据。`AFVC_DATA_PROFILE=production` 才保留原有的 raw 优先种子和紧急 file 回退。

Schema 迁移：`scripts/sql/001_*.sql`、`002_*.sql`、`003_maintenance_tasks.sql`。

## 2. 公开 DEMO vs 本地真实

对齐合成数据文档惯例（须**标明合成**、说明用途与限制，见 [CASRAI](https://casrai.org/guides/synthetic-data-in-research) / UK Data Service 最小说明）：

| | 公开仓库 | 本机开发 |
|--|----------|----------|
| 工单 | `mock/workorders_demo.csv`（`DEMO-AGM-*`） | `backend/data/raw/` 下真实 xlsx（**gitignore**） |
| 预测 | `mock/*prediction*.csv`（`DEMO-AGM-*`） | 可用真实模型 CSV 覆盖（勿提交） |
| 人员/备件/站点重要度 | `mock/*.csv`，文件内/README 标注模拟 | 同上 |

**限制：** DEMO 与模拟资源仅用于跑通链路与联调，**不得**当作真实线网运营结论或降本减故证据。

demo 首次初始化在一个事务中种入 288 条工单与 18 条检修任务（planned / in_progress / done；done 带合成反馈），并写入 v1 版本标记。重启只检查标记，不重插也不覆盖任务。若发现无标记的非空库、版本不符、文件缺失或跨表引用不齐，启动失败，不回退至 raw 或统计基线。production 空库只从 raw 默认文件种入；缺失时明确失败，避免将合成数据标为 production。

`backend/data/mock/` 中的固定 CSV 与 `maintenance_tasks_demo.json` 由 `scripts/generate_demo_data.py` 生成。设备、风险、故障类型、站点、班组和任务使用同一组虚构键。根目录 `docker-compose.yml` 是唯一的本地 Compose 入口，固定使用 `afvc-demo` 项目、端口 55433 和 `afvc_demo_pgdata` volume。普通 `docker compose up -d` 不重置数据；需要明确重置时，先停 demo 后端，再执行 `docker compose down --volumes` 后 `docker compose up -d`。该清理只会移除当前 demo Compose 项目的数据卷。

## 3. 对齐键与约定

| 键 / 字段 | 约定 |
|-----------|------|
| `assetnum` | 设备主键；预测表、工单、建议、任务必须能对齐同一编号 |
| `station_name` | 车站名；用于模拟站点重要度匹配 |
| `fault_focus` | 维修作业故障焦点；**V1 默认「暂停服务」**（`domain.maintenance.DEFAULT_FAULT_FOCUS`）；参与相关度与资源标签 |
| 预测对不齐 | 高风险等路径：无交集时回退统计基线或得到空/不可用结果（以实现为准） |

工单解析所需列见 `backend/infrastructure/workorders.py` 中 `REQUIRED_COLUMNS`（如 `assetnum`、`station_name`、`current_faildate`、`description` 等）。

## 4. 检修任务（逻辑字段）

表 `business.maintenance_tasks`（详见 `003_maintenance_tasks.sql`）：

| 概念 | 说明 |
|------|------|
| 身份 | `id`，`assetnum`，可选 `station_name` |
| 计划 | `priority`（越小越优先）、`planned_date`、`assignee_crew_id`、`status` |
| 建议溯源 | `suggestion_score`，`suggestion_reasons` |
| 反馈 | `feedback_*`；通过反馈接口记录非空现场结果后，任务才转为 `done` |

与 `agent.pending_actions`（工单对话审批）分离。

## 5. 禁止提交

已由 `.gitignore` 约束，开发时仍须遵守：

- `backend/data/raw/*`（除 `.gitkeep`）
- `*.xlsx` / `*.xls`、线路真实报告 PDF 等
- 本地 `maintenance_tasks.json`（file 回退产生的可变状态）

## 6. 相关文档

| 文档 | 内容 |
|------|------|
| [API.md](./API.md) | 上传与查询如何暴露 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 模块如何消费数据 |
| `backend/data/mock/README.md` | DEMO 文件清单 |
