# AFVC

面向地铁 AFC 闸机检修的 Agent 产品：在可独立使用的「预测 + 维修作业」能力上，用对话跑通建议、派工与反馈。

正式文档（人读）：

- [docs/PRODUCT.md](docs/PRODUCT.md) — 产品
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构
- [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md) — 对话 Agent（工具循环）
- [docs/API.md](docs/API.md) — HTTP 接口
- [docs/DATA.md](docs/DATA.md) — 数据约定

给 Cursor / 编码 Agent：[AGENTS.md](AGENTS.md)（短指针 + 常驻约定）。

## 快速启动

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
streamlit run frontend/streamlit_app.py
```

真实工单勿提交 Git；公开 DEMO 见 `backend/data/mock/`。
