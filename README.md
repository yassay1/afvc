# AFVC

面向地铁 AFC 闸机检修的 Agent 产品：在可独立使用的「预测 + 维修作业」能力上，用对话跑通建议、派工与反馈。

正式文档（人读）：

- [docs/PRODUCT.md](docs/PRODUCT.md) — 产品
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构
- [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md) — 对话 Agent（工具循环）
- [docs/API.md](docs/API.md) — HTTP 接口
- [docs/DATA.md](docs/DATA.md) — 数据约定

给编码 Agent：[AGENTS.md](AGENTS.md)（短指针 + 常驻约定）。

## 快速启动

需要 Python 3.12+、Node.js 24 LTS、npm 和 Docker Compose。从仓库根目录运行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linux 将虚拟环境激活与首次复制命令换成 `source .venv/bin/activate`、`test -e .env || cp .env.example .env`。若已有 `.env`，先手动核对其中的 `AFVC_DATA_PROFILE=demo` 和 `DATABASE_URL=postgresql://afvc_demo:afvc_demo@127.0.0.1:55433/afvc_demo`；上面的复制命令不会覆盖现有配置。`.env.example` 默认 demo，后端只连接独立的 `afvc_demo` 库（本机端口 55433、独立 volume），首次启动装入版本化合成工单与检修任务；即使 `backend/data/raw/` 有文件也不会读取。数据缺失或引用不一致会使启动失败。另开终端启动手机端 Web：

```powershell
cd frontend
npm ci
npm run dev
```

打开 Vite 输出的本地地址。开发服务器将 `/usecases`、`/interaction`、`/upload`、`/health` 代理到 `http://127.0.0.1:8000`；若后端地址不同，可在 `frontend/.env.local` 设置 `AFVC_API_PROXY_TARGET`。更多运行与验证命令见 [frontend/README.md](frontend/README.md)。

生产构建运行 `cd frontend; npm ci; npm run build`。将 `frontend/dist/` 静态资源与 FastAPI 放在同一域名反向代理后：API 路径（含 `/auth`）转发到 FastAPI，其他页面路径回退到 `index.html`。业务 API 需固定账号登录（Cookie 会话；无自助注册；`python -m backend.scripts.manage_user` 建号/停用）。新前端不开放工单上传。ECS Demo 部署步骤见 [deploy/README.md](deploy/README.md)。

回滚时切回迁移前的 Git 修订与对应部署配置，在隔离环境重新安装当时的 Python 依赖并启动旧 Streamlit 入口；数据库不应随前端切换回滚。建议在正式切换前保存该修订和原有反向代理配置。

### 演示数据重置与回滚

普通重启保留演示任务的新增、修改和反馈。需要**明确清空演示库并重新生成初始数据**时，先停止 demo 后端，再运行：

```powershell
docker compose down --volumes
docker compose up -d
```

根目录 `docker-compose.yml` 现在是唯一的本地 Compose 入口，只启动 `afvc-demo` 隔离项目、55433 端口和 `afvc_demo_pgdata` volume。普通 `docker compose up -d` 不会连接或重建其他 Compose 项目。若恢复 production 数据流，将 `.env` 改为 `AFVC_DATA_PROFILE=production` 并设置目标 `DATABASE_URL`；真实工单勿提交 Git，公开合成数据见 `backend/data/mock/`。
