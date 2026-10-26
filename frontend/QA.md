# 前端发布候选验收记录

2026-10-25，本地 Windows / Chrome。基于 `docs/frontend/IMPLEMENTATION_PLAN.md` 阶段 7。

## 已验证

| 检查 | 命令与结果 |
|---|---|
| TypeScript | `cd frontend; npm run typecheck`：通过 |
| ESLint | `cd frontend; npm run lint`：通过 |
| 单测 | `cd frontend; npm test`：22 passed |
| 浏览器 | `cd frontend; $env:AFVC_PLAYWRIGHT_CHANNEL='chrome'; npm run test:e2e`：10 passed |
| 构建 | `cd frontend; npm run build`：通过 |
| 依赖审计 | `cd frontend; npm audit --audit-level=moderate`：0 vulnerabilities |
| Python 基线 | `python -m pytest -q`：154 passed、29 skipped、8 deselected；`python -m ruff check .`：通过 |
| 文本检查 | `python scripts/check_text_integrity.py`：通过 |

浏览器用例覆盖 375×812、390×844、768×1024、1024×768 和 844×390；四项主导航、直接打开路由、设备→助手→建议、建议→建任务→改状态→反馈、工单待批按钮。检查了横向溢出、键盘焦点、底部目标尺寸和主要页面的自动化 WCAG A/AA 规则。390px 页面截图已逐页检查，内容层级、表单和固定底栏可辨认。主要文案颜色对比度：muted/surface 5.4:1、action/surface 6.7:1、caution/surface 5.02:1。

浏览器用例使用拦截响应，不会写入用户工单。阶段 3 曾使用隔离的临时任务文件跑通真实 FastAPI 建任务、状态调整和反馈。Postgres 相关测试在本地缺少运行服务时跳过；部署环境仍需联调真实工单审批。

## 阶段 8 清理后复验

删除旧 Streamlit 文件与专属测试后，`npm ci` 成功从锁文件安装；`python -m pytest -q` 为 142 passed、29 skipped、8 deselected；Python Ruff、文本检查、compileall、前端 22 项单测、10 项浏览器测试、typecheck、lint 与 build 均通过。

用隔离的 Docker Compose 项目启动 Postgres，再以显式本地环境变量启动 FastAPI 和 Vite：后端 `/health` 返回 200/ok，`/openapi.json` 包含 `/usecases/devices`，Vite `/` 返回 200，Vite `/health` 代理返回 200/ok。服务与隔离数据库卷已清理。该空库因本机存在 `backend/data/raw/` 文件，按后端既有优先级导入了本地文件；未查询或导出工单内容，也未修改用户原有数据卷。

## 发布边界

- 新前端只在次级数据管理页提供概览和高风险只读查询。工单上传阶段 6b 因缺少受控部署与数据负责人许可、后端也无用户身份/角色授权而延期。
- 对话响应在 Agent 图模式仅返回叙述、来源和工具名，没有完整结构化工具结果。页面可显示叙述及设备跳转；规则兜底直接返回诊断或手册结果时显示结构化卡片。若以后要展示图模式的结构化卡片，需要先扩展后端契约并加测试。
- 尚未部署或公开发布。生产运行应将 Vite 静态资源与 FastAPI API 放在同源反向代理后，并限制站点访问。

## 2026-10-26 阶段 7 跨页复核

阶段 3–6A 页面调整后重新执行发布候选检查：

| 检查 | 结果 |
|---|---|
| `npm test` | 25 passed |
| `npm run typecheck` | 通过 |
| `npm run lint` | 通过 |
| `npm run build` | 通过 |
| `AFVC_PLAYWRIGHT_CHANNEL=chrome npm run test:e2e` | 10 passed |

浏览器用例覆盖 375×812、390×844、768×1024、1024×768、844×390；检查四项导航、建议到任务反馈闭环、设备到助手的编号传递、待批操作显式批准、高风险页和主要路由的 axe WCAG A/AA 规则、键盘焦点与底部导航触控尺寸。用本机真实 API 在 390×844 下另行截取工作台、助手、检修建议/任务、设备列表/详情、数据概览/风险共 8 个页面；页面运行时错误为 0，横向溢出为 0，`/health` 返回 200。Playwright 交互测试使用路由拦截，不写入真实工单。

复核中修正了工作台任务链接的可访问名称、过期的设备到助手浏览器用例选择器，以及高风险指标小字未达到 4.5:1 的对比度。当前通过结果仅代表本地发布候选检查，尚未部署。
