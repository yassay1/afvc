# AFVC

面向地铁 AFC（自动售检票）设备的**诊断能力平台**。

基于维修工单，提供可调用的数据概览、复发风险与预警、故障类型、维修建议、手册检索与综合诊断等能力。可选提供薄层自然语言入口，用于选用例、补全参数与结果叙述。

> 核心是 **Application（诊断用例）** 与 **Interaction（薄对话入口）**；Domain / Infrastructure 支撑前者，API / Frontend 暴露二者。

## 能力

| 用例 | 说明 |
|------|------|
| 数据概览 | 工单整体统计 |
| 高风险设备 | Top N 排行 |
| 设备历史 | 单设备历史工单 |
| 风险预测 | 多时间窗口复发风险与红橙黄绿预警 |
| 维修建议 | 巡检方向与 SOP 参考 |
| 手册检索 | 维修手册相关段落 |
| 故障类型 | 类别条件概率与综合估计（有数据时） |
| 综合诊断 | 单设备聚合分析（**唯一业务聚合点**） |

API 与对话入口暴露**同一组用例**；对话不单独发明业务能力。

## 架构鸟瞰

```
API            HTTP 契约
Application    用例编排（业务唯一主人）
Domain         纯规则（预警、故障类别、概率等）
Infrastructure 工单/文件、检索实现、LLM 客户端等
Interaction    可选：理解 → 澄清 → 调用用例 → 叙述
Frontend       控制台 + 可选 Chat
```

分层、边界与禁区见 [docs/architecture.md](docs/architecture.md)。

## 科学边界

- 风险表示未来窗口内再次产生故障工单的可能性，**不等于**精确故障日期
- 维修建议是巡检参考，**不是**最终根因结论
- 故障类型概率表示相对可能性，**不得**把条件概率说成必然发生

## 技术栈

Python · FastAPI ·（可选）薄对话层 · Streamlit 前端 · Polars / Pydantic

## 快速开始

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 按需配置；对话/LLM 可关闭

# 终端 1：API
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# 终端 2：前端
streamlit run frontend/streamlit_app.py
```

健康检查：`GET http://127.0.0.1:8000/health`

## HTTP 路径

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/upload/workorders` | 上传工单文件 |
| GET | `/usecases/overview?top_n=` | 数据概览 |
| GET | `/usecases/high-risk?top_n=` | 高风险设备 Top N |
| GET | `/usecases/devices/{assetnum}/history` | 设备历史 |
| GET | `/usecases/devices/{assetnum}/risk` | 设备风险预测 |
| GET | `/usecases/devices/{assetnum}/advice` | 维护建议 |
| GET | `/usecases/devices/{assetnum}/fault-type` | 故障类型预测 |
| GET | `/usecases/devices/{assetnum}/diagnosis` | 综合诊断 |
| GET | `/usecases/manuals/search?query=` | 手册检索 |
| POST | `/interaction/turn` | 薄对话一轮（body: `query`, `session_id`） |

前端控制台直接调用 `/usecases/*` 与 `/upload/workorders`；对话工作台只调用 `POST /interaction/turn`。

## 测试

```bash
pytest
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 目标架构、模块分工、Interaction 边界 |
| [docs/project-brief.md](docs/project-brief.md) | 项目简述 |
| `.env.example` | 环境变量模板 |
