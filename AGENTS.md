# AGENTS.md

给在本仓库改代码的 Agent 用。人读的产品/工程说明在 `docs/`；这里只放**短指针**与**每轮都要守的约定**。

## 读哪份文档

- **产品定位、范围、非目标** → 改叙事、加功能、砍范围前读 [`docs/PRODUCT.md`](docs/PRODUCT.md)
- **预测 / 维修作业模块、分层、seam** → 动目录或模块边界前读 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **对话入口、model⇄tools、Tool、HITL、降级** → 改 `backend/agent` 或 `/interaction` 前读 [`docs/ORCHESTRATION.md`](docs/ORCHESTRATION.md)
- **HTTP 路径与错误约定** → 加/改对外路由前读 [`docs/API.md`](docs/API.md)；字段以 FastAPI `/docs` 与 Pydantic 为准
- **真相源、DEMO、assetnum 对齐、禁止提交** → 动数据路径或种子前读 [`docs/DATA.md`](docs/DATA.md)
- **历史计划勿跟** → [`docs/archive/`](docs/archive/) 仅对照

## 常驻约定

1. **原子能力在 Application**（及 Domain 规则）；编排层只选 Tool、叙述、提案，不重写风险/打分/任务状态机。
2. **建议排序用确定性规则**并带 `reasons`；模型只做理解与编排。
3. **检修任务**走 `maintenance_tasks`；工单对话写走 `pending_actions` HITL——两条线分开。
4. **公开仓只用 DEMO/模拟数据**；真实工单进 `backend/data/raw/`（已 gitignore），不要提交 xlsx/线路报告。
5. **文档套件**是 PRODUCT · ARCHITECTURE · ORCHESTRATION · API · DATA；改行为时同步改对应文档，避免第二套故事。
6. **开发优先级：先后端与契约，前端靠后。** 默认先做 Application / Domain / API（及需要时的编排 Tool），用 pytest 与 `/docs` 验收；除非用户明确点名 UI，否则不主动改 `frontend/`、不把 Streamlit 当本轮交付物。

## 实现功能时

1. 对照 PRODUCT 确认落在「预测 / 维修作业 / 知识 / 编排」哪一块。完成：能指出模块与是否 V1 范围。  
2. 在 Application（必要时 Domain）实现或扩展用例；HTTP 与 Tool 共用同一实现。完成：用例可经 API 调用；对话 Tool 不另起第二套业务逻辑。  
3. 补测试与（若对外）`docs/API.md` / `DATA.md` 表格行。完成：默认 `pytest` 相关用例通过；文档路径与代码一致。  
4. 前端：仅在用户要求时再改 `frontend/`。完成：本步可跳过。

启动与依赖以根目录 `README.md`、`requirements.txt`、`.env.example` 为准，此处不重复。
