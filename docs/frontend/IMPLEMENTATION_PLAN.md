# AFVC 手机端 Web 前端渐进式实施计划

> 实施状态（2026-10-25）：阶段 0–8 已按顺序完成本地实现和验收；阶段 6b 工单上传因受控部署/权限准入条件未满足而延期。阶段 7/8 验收命令和限制见 [`frontend/QA.md`](../../frontend/QA.md)。以下阶段条目保留原计划与验收口径，历史时态不代表当前代码状态。

## 实施原则

- 每个阶段都可独立运行、验证和回滚；阶段末检查端到端演示点。
- React 只处理展示、路由和输入，通过 API client 调用现有 FastAPI；除单独批准外不改 API 契约。
- 先按 `docs/frontend/DESIGN_AND_ARCHITECTURE.md` 实现四项固定导航和设计令牌；不新增主导航。
- 不把 DEMO、模拟班组/备件、图片示例值当作线上事实。
- 每阶段完成后先 review diff、运行该阶段测试，再进入下一阶段。

## 本计划采用的项目级建议

- **设备页：** 完整设备列表是固定“设备”入口的必要数据。实现阶段增加只读 `GET /usecases/devices`，薄路由复用现有 `get_device_list()`，不造第二套业务聚合；同步 API 文档、OpenAPI schema 与 pytest。当前先列计划，本轮没有改后端。
- **部署：** 优先静态 Vite 资源与 FastAPI 通过同源反向代理托管；开发环境用 Vite proxy。只有部署条件不支持同源时才设置浏览器侧 API origin 并限制 CORS。
- **数据上传：** `overview` 与风险榜属于低风险只读次级能力，可进入阶段 6；文件上传会写入并导入工单，且 API 暂无角色授权，作为阶段 6b 的 gated item：只有确认站点是受控内网或权限方案已就绪才迁入，否则延后。
- **依赖基线：** npm + lockfile；当前官方 Vite React 插件；React Router Declarative mode；`fetch` 小封装；TanStack Query 管理跨页服务端缓存与 mutation invalidation；Lucide 图标；Vitest + React Testing Library；核心流程加 Playwright；ESLint + typescript-eslint 轻配置。无 UI 套件、无 Redux、无 axios。
- **实现方法：** 先把真实参考图和 API 映射成静态页面/组件层级，再接数据，再接写操作。React 官方建议从 mock/API 形状拆分 UI、构造静态版本、只保存最小 state；自动化检查面向用户可见行为而非 CSS 实现细节。成熟实践来源与适用边界见设计文档 §7。

## 阶段 0：先补齐设备列表只读契约

**目标与范围：** 完成设备列表能力缺口；确定单一前端 API 接入方式、OpenAPI contract snapshot 和次级写操作暴露规则。

**页面/功能：** 本阶段仅后端只读 API 切片，不交付前端页面：将 `get_device_list()` 从 `backend/application/history.py` 加入 `backend/application/usecases.py` 门面，然后在 `backend/api/usecases_api.py` 新增 `GET /devices`（完整外部路径 `/usecases/devices`）；响应字段沿用现有 Application `status/message/device_count/devices[]` 输出，并以 Pydantic response model 固化 OpenAPI schema。首版由客户端基于返回的 assetnum/station/line/brand 搜索，不新增未有数据来源的设备类型筛选。

**关键文件/模块：** `backend/application/usecases.py`、`backend/api/usecases_api.py`、必要时 `backend/schemas/device_list.py`、`backend/application/history.py`、`docs/API.md`、`tests/api/test_usecases_api.py`。

**前置依赖：** 用户明确确认开始实现；核对运行后端的 `/docs` 与 Pydantic schema；不改 Application 业务逻辑。

**验收标准：** 新路由仅包装 `get_device_list()`，不复制设备聚合逻辑；成功响应字段与 schema 一致；无设备/数据列缺失/错误均可解释；`docs/API.md` 与 `/docs` 一致；阶段 4 有可直接消费的真实完整列表。

**必要测试：** API pytest 覆盖 200 结构、空列表、Application 异常映射；现有 `get_device_list()` Application 测试继续通过；检查 `/openapi.json` 对设备 list 路由的呈现。

**交付物：** 可被 UI 使用的设备列表 API、OpenAPI 契约、API 文档行与测试；更新部署决定为 Vite proxy + 同源生产托管建议。

## 阶段 1：React 工程骨架与导航

**目标与范围：** 在 `frontend/` 建 Vite + React + TypeScript app，与旧 Python UI 共存。建立 CSS tokens、基础重置、路由、AppShell、四项底部导航、API client/QueryClient 和页面占位。

**页面/功能：** 四个固定入口、检修内建议/任务切换、页面标题和路由直达；底部导航在各屏宽保持底部位置，手机安全区与桌面留白自适应。

**关键文件/模块：** `frontend/package.json`、npm lockfile、`vite.config.ts`、`tsconfig*.json`、`eslint.config.*`、`src/main.tsx`、`src/app/*`、`src/shared/api/*`、`src/shared/styles/*`。

**前置依赖：** 阶段 0 的路径和运行方式约定；不需 API。

**验收标准：** `npm run dev` 可打开且 Vite proxy 到 FastAPI；四导航顺序/标签精确并始终固定于底部；链接、深链刷新、浏览器返回有效；手机/平板/桌面无横向溢出；主要手机操作目标约 44×44 CSS px、固定栏有 safe-area/滚动补偿；CSS token 集中维护；QueryClient 不启用持久化敏感缓存。

**必要测试：** `tsc --noEmit`、ESLint、路由/导航与 AppShell 单测；375/390px、768px、1024px 冒烟；检查 API base 仅为公开配置。

**交付物：** 空数据的可导航 app shell 和运行说明草案。

## 阶段 2：工作台与真实摘要

**目标与范围：** 实现建议、任务入口的真实摘要和快捷问答，不填充虚构 KPI。

**页面/功能：** 检修建议摘要（保留服务端首序）、任务状态摘要、AI 快捷入口；“查看全部”深链到精确的检修视图。

**关键文件/模块：** `src/features/workbench/*`、`src/shared/api/*`、`src/shared/query/*`、通用状态/卡片组件。

**前置依赖：** 阶段 1；建议和 task list 接口。

**验收标准：** 展示字段逐项来自 API；建议理由可读且首序不变；query key 在工作台/检修建议间复用；链接分别打开 `/maintenance?view=suggestions`、`/maintenance?view=tasks`； loading/empty/error/unavailable 不混淆。

**必要测试：** mock fetch 的页面状态/快捷链接单测；保证前端不排序 suggestions。

**交付物：** 真实数据驱动工作台。

## 阶段 3：检修建议—安排—执行反馈闭环

**目标与范围：** 完成产品 V1 主业务闭环中独立可用的检修作业页。

**页面/功能：** 建议列表与理由、优先筛选/搜索（只筛选、不重排业务优先级）；建议设备详情跳转；人工确认计划信息后创建任务；任务状态列表/详情/修改；执行反馈表单和完成状态。

**关键文件/模块：** `src/features/maintenance/suggestions/*`、`tasks/*`、`task-detail/*`、`feedback/*`、API 类型与表单组件。

**前置依赖：** 阶段 1、2；现有 suggestions、tasks、create/patch/feedback 接口。

**验收标准：** 建议原序不变且显示 `reasons[]`；班组/日期/优先级确实由用户核对后写入；feedback 的 result 必填且成功后回显 done；任务写请求只调用 `/usecases/maintenance/*`，不触发 `/interaction/approve`；创建与提交避免双击重复。

**必要测试：** 列表顺序与理由、表单验证、状态筛选、patch 和 feedback 成功/404/422 单测；至少一个 API 联调 smoke；e2e 走完建议→建任务→改状态→提交反馈。

**交付物：** 不依赖 Agent 的可独立检修闭环。

## 阶段 4：设备查询与详情

**目标与范围：** 实现设备入口、搜索/筛选、单机详情和到建议/任务/助手的主跳转。

**页面/功能：** 全设备列表、设备详情中的画像、风险窗口、历史、维护参考、故障类型可用状态。

**关键文件/模块：** `src/features/devices/*`、`shared/api` 设备接口类型。

**前置依赖：** 阶段 0 的 route/schema/API 文档/pytest 已交付；只读 `GET /usecases/devices` 是该计划推荐的设备列表契约。

**验收标准：** 完整列表字段来自新增只读 API；搜索仅在 assetnum、station、line、brand 等真实字段上进行；diagnosis 缺项和 fault prediction `unavailable` 各自说明；风险说明不会被理解为故障日期；从设备到检修/助手跳转携带正确 `assetnum`。

**必要测试：** 搜索/筛选和 detail rendering 单测；风险 unavailable/找不到设备；列表 contract 联调。

**交付物：** 有真实来源的设备查询与单机详情。

## 阶段 5：AI 助手与工单 HITL

**目标与范围：** 集成主对话入口，保留当前对话回应、结构化结果、pending action 人工审批语义。

**页面/功能：** 新会话、推荐提问、持续输入、设备上下文、诊断卡片、手册结果、跳到设备/建议/任务；工单待批 approve/reject。

**关键文件/模块：** `src/features/assistant/*`、interaction API client、Markdown renderer（如需要）。

**前置依赖：** 阶段 1、设备/检修路由；interaction turn/approve/reject/pending API。对话 `session_id` 与当前 tab 可见 transcript 放入 `sessionStorage`，不使用跨浏览器重启的 `localStorage`；后端无 transcript GET。

**验收标准：** session_id 原样传递；刷新当前 tab 后 transcript 从 `sessionStorage` 恢复、待批由 GET 恢复；有未处理待批时先处理完再开新会话，避免丢失审批上下文；新会话清除当前 transcript 并换新 session；显示 status 与降级标记；重复提交防护；待批只由 pending_actions 生成，按钮用 action_id/session_id 显式批准或拒绝；绝不出现 Agent 直接创建 maintenance task 的写卡片。无服务端完整 history API 时不宣称跨设备恢复对话。

**必要测试：** clarify/success/legacy fallback/timeout/error/running conflict；approve/reject/重复审批冲突；e2e 待批卡显式操作。

**交付物：** 受现有编排契约约束的 AI 助手页面。

## 阶段 6：数据管理等次级能力

**目标与范围：** 先迁移数据概览与高风险只读列表；工单上传拆为 gated 阶段 6b。保持次级位置，不扩展主导航。

**页面/功能：** overview、high-risk 次级页面；阶段 6b 条件满足时再上 xlsx/xls/csv 上传、replace/append 确认和导入结果。

**关键文件/模块：** `src/features/data-management/*`、次级入口、上传 API adapter。

**前置依赖：** 阶段 1–5；确认部署环境及工单数据权限安排。上传是否纳入由阶段 6b 的安全/部署门槛决定。

**验收标准：** overview/high-risk 来自真实 API；数据上传只在受控部署/已具备授权时开放；replace 有二次确认；展示 row_count/import_batch_id 等可用结果，不露出服务器本地路径；没有授权能力时不宣称权限控制。不满足上传门槛时，阶段仍交付只读概览/风险页，上传明确延期。

**必要测试：** 阶段 6A 测 overview/high-risk 的 loading/empty/error 状态；若进入 6b，再测文件类型错误、网络失败、导入失败与成功、replace 确认拦截。

**交付物：** 旧 UI 次级功能的新入口与行为。

### 阶段 6b：工单上传（有门槛，可延期）

**准入条件：** 部署明确为受控内网且数据负责人确认可让该界面触发导入，或后端先补齐用户身份/权限。未满足时不开放上传页，阶段 6A 仍可完成。

**范围：** 单文件、显式 `replace`/`append` 选择、replace 二次确认、上传中状态、导入成功/部分失败回执；调用既有 `POST /upload/workorders`，不通过 Agent pending_actions。

**验收：** 页面不会把上传说成草稿；用户清楚上传会写入并导入；失败保留重试信息；不显示服务器路径；公网/无访问控制时此功能不可达。测试覆盖所有后端允许扩展名、400/422/500、replace 防误触。

## 阶段 7：跨页质量与发布候选

**目标与范围：** 对已完成页面做手机优先整体视觉、可访问性、稳定性和回归检查。

**页面/功能：** 四导航全页、建议→任务→反馈、设备→助手、助手→设备/建议、待批与数据管理流程。

**关键文件/模块：** 全部 `frontend/src`、CSS tokens、API adapter、test/e2e、Vite build config。

**前置依赖：** 阶段 1–6。

**验收标准：** 375/390px 窄屏、平板和桌面布局；横屏/键盘/安全区；对比度、键盘焦点、屏幕阅读顺序、主要手机 Web 操作约 44×44 CSS px（至少符合 WCAG 2.2 AA 目标尺寸条件）、减弱动画；loading/empty/404/422/409/500/timeout 都可理解；无虚构数值和 broken links。

**必要测试：** `tsc`、Vitest、关键 e2e、production build；逐页手工视觉检查（至少 iOS/Android 主流视口或浏览器模拟）。

**交付物：** 可供部署切换的发布候选及 QA 记录。

## 阶段 8：移除 Streamlit 并更新工程引用

**目标与范围：** 在 React 发布候选验收后移除旧实现及专属依赖/测试引用；本阶段不应提前开始。

**关键文件/模块：** 删除旧 `frontend/streamlit_app.py`、`frontend/styles.py`、`frontend/ui_components.py`；修改 `requirements.txt`、`README.md`、`pyproject.toml`、`.github/workflows/ci.yml`、`scripts/check_text_integrity.py`、`.gitignore`；迁移/替换 `tests/test_frontend_ui.py`、`tests/test_frontend_processing.py`。审查全仓 `streamlit`/旧入口引用。`docker-compose.yml` 当前仅运行 Postgres，无前端容器；若部署方案仍需 Compose，再另加配置并验收，不默认扩大本阶段。

**前置依赖：** 阶段 7 验收，且 React app 已有接管运行说明和部署方式。若阶段 6b 未满足准入条件，不阻塞旧前端替换，只保留被后端/部署保护的上传入口处理决策（不得把旧无授权上传默认暴露到新公开站点）。

**验收标准：** 根 README 启动 React 与 FastAPI/Postgres 的步骤可从干净环境完成；Python requirements 不再要求 Streamlit；CI 使用 Node LTS 并锁定 npm lockfile，分别运行后端 pytest/Ruff 和前端 typecheck/lint/test/build；无失效旧引用；回滚方式清楚。

**必要测试：** 删除前全量 Python/前端 CI 基线；删后全量 `pytest`、Ruff、文本检查、npm install/build/test 与引用扫描。

**交付物：** 新前端接管默认运行入口，旧 Streamlit 代码和依赖被干净移除。

## 本计划的默认建议（进入实现前确认环境即可）

1. **全设备列表：** 按本计划阶段 0 增加只读薄路由，复用现有 Application，补契约/pytest；这是固定“设备”入口所需的最小后端增量。
2. **工单上传：** 默认从第一版核心闭环延期；如确认部署为受控内网且数据负责人同意，阶段 6b 再纳入；否则只迁只读概览/风险。
3. **部署：** 默认 Vite proxy 本地开发、静态文件与 FastAPI 同源反向代理生产部署；若实际平台无法反代，再确定 CORS 与公开 API origin。

这些是规划采用的默认选项，不是本轮已修改 API 或配置。实际实现仍待用户明确确认后启动。
