# AFVC

面向地铁 AFC（自动售检票）设备的诊断能力平台。

基于维修工单提供数据查询/统计、风险与故障类型预测、维修建议与手册检索；控制台走 HTTP 用例，对话入口调用同一组能力。

## 产品三层

| 层 | 做什么 | 代码 |
|----|--------|------|
| **数据** | 工单导入、概览统计、设备历史、行级 CRUD。Postgres 是真相，Excel 只是 import | `backend/application/overview.py` `history.py`，`infrastructure/workorder_repo.py`，`api/upload_api.py` |
| **预测** | 复发风险、故障类型。有外部结果表则 `prediction_tier=model`，否则风险为 `statistical_baseline` | `backend/application/risk.py` `fault_type.py`，`infrastructure/risk_table.py` `fault_table.py` |
| **对话** | `AFVC_USE_LLM=true` 时 LangGraph 主 Agent 自主选 Tool；写操作只提案，需界面批准；关闭则 understand 规则兜底 | `backend/agent/`，`backend/interaction/`，`api/interaction_api.py` |

建议 / 手册在 Application，对话可调用，不算数据管理。

写操作 HITL：对话侧提案 → `pending_actions` → `POST /interaction/approve` 或 `/reject`。控制台上传仍直接写库。口语「好的」不会批准。

分层细节：[docs/architecture.md](docs/architecture.md)。工程约定：[docs/engineering.md](docs/engineering.md)。

## 科学边界

- 风险 = 窗口内再次产生故障工单的可能性，不是故障日期
- 维修建议 = 巡检参考，不是根因结论
- 故障类型条件概率不得说成必然发生

## 技术栈

Python 3.12 · FastAPI · Streamlit · Polars · PostgreSQL · LangGraph · OpenAI-compatible LLM（当前验收：DeepSeek）

工单工作集在 Postgres `business.workorders`。Excel/CSV 经 `POST /upload/workorders` 或 `scripts/import_default_xlsx.py` 导入。模型结果仍读 `backend/data/mock/`（目录名历史遗留，见该目录 README）。紧急回退：`AFVC_DATA_BACKEND=file`。

## 安装与配置

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：填 OpenAI 兼容 API Key（DeepSeek 或智谱等）；对话主 Agent 设 `AFVC_USE_LLM=true`（并保持 `AFVC_AGENT_GRAPH=true`）。配置只从 `backend/core/config.py` 读取。

## 启动

```bash
docker compose up -d
python scripts/import_default_xlsx.py   # 空库时应用启动也会自动导入默认 xlsx
# 终端 1
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
# 终端 2
streamlit run frontend/streamlit_app.py
```

健康检查：`GET http://127.0.0.1:8000/health`

## HTTP

| 方法 | 路径 | 层 |
|------|------|-----|
| GET | `/health` | 运维 |
| POST | `/upload/workorders` | 数据 |
| GET | `/usecases/overview` | 数据 |
| GET | `/usecases/high-risk` | 预测 |
| GET | `/usecases/devices/{assetnum}/history` | 数据 |
| GET | `/usecases/devices/{assetnum}/risk` | 预测 |
| GET | `/usecases/devices/{assetnum}/advice` | 应用 |
| GET | `/usecases/devices/{assetnum}/fault-type` | 预测 |
| GET | `/usecases/devices/{assetnum}/diagnosis` | Application 聚合 |
| GET | `/usecases/manuals/search` | 应用 |
| POST | `/interaction/turn` | 对话 |
| POST | `/interaction/approve` | 对话 HITL |
| POST | `/interaction/reject` | 对话 HITL |
| GET | `/interaction/sessions/{session_id}/pending` | 对话 HITL |

控制台打 `/usecases/*` 与上传；对话工作台打 `/interaction/turn`，待批卡片打 approve/reject。

## 测试

```bash
pytest
python scripts/check_text_integrity.py
python -m ruff check backend frontend tests scripts
```

默认 `AFVC_USE_LLM=false`，不打真实模型。真实 Agent 验收 / eval：

```bash
pytest -m llm
```

需要 `.env` 里有效的 `OPENAI_API_KEY` 和可用的 Postgres。当前验收 provider 为 DeepSeek。若同时配置了 `LANGSMITH_API_KEY`，测试会打开 tracing，并用 `session_id` / case id 前缀方便在 LangSmith 里定位。

## 目录

```
backend/api/             FastAPI 路由
backend/application/     用例（业务编排）
backend/agent/           LangGraph 主图、Tool 注册表、数据子图
backend/domain/          纯规则
backend/infrastructure/  Postgres / Excel 解析 / CSV / 会话内存 / 手册检索
backend/interaction/     LLM 关闭或主图失败时的规则兜底
backend/core/            配置、LLM 客户端
backend/schemas/         Pydantic 契约
backend/data/            raw 工单（import 源）、模型结果 CSV、手册
frontend/               Streamlit
tests/                  pytest
docs/                   架构、工程约定、Agent spec
scripts/                SQL 迁移、默认 xlsx 导入、文本检查、LLM 连通性
```
