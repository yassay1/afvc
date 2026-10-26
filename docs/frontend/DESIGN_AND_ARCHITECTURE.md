# AFVC 手机端 Web 前端设计与工程架构

> 状态：阶段 0–8 已实施并通过本地验收，阶段 6b 工单上传因准入条件未满足而延期；实测记录见 [`frontend/QA.md`](../../frontend/QA.md)。本文保留设计决策与实施前的 API 差距记录；运行时路径和字段以 `docs/API.md`、FastAPI `/docs`、Pydantic 与当前实现为准。

## 1. 产品目标与约束

面向地铁 AFC 设备检修负责人和值班调度，用手机优先的 Web 前端支持“看风险 → 看建议 → 人工安排任务 → 执行 → 回填反馈”，同时让 AI 助手成为主要交互入口。Agent 不取代检修建议/任务页面，且不决定建议顺序。

本轮固定底部导航与顺序：**工作台、AI 助手、检修、设备**。检修页内含“检修建议 / 任务跟进”两个视图。本轮确定目标栈为 **React + TypeScript + Vite + CSS**，不对 Streamlit 做局部改造。

产品与数据规则：

- 建议顺序和 `reasons[]` 来自服务端确定性规则，前端按原顺序展示，不按模型/本地规则重排。
- 检修任务使用 `maintenance_tasks` 用例与 `/usecases/maintenance/*`；对话工单敏感写走 `pending_actions`，显式批准/拒绝。两条操作线不能混用。
- 预测输入可能来自外部结果表或统计基线；页面展示返回的来源/说明，不能把“工单复发风险”说成物理故障日期。
- 故障类型预测可返回 `unavailable`；诊断中的建议是参考，不是根因结论。
- 公开演示、站点重要度、班组和备件资源均可能是模拟数据，必须就地标明；设计稿里的设备编号、日期、分数、数量与照片不是线上数据。
- 不设计大型监控大屏或复杂后台，不增加一级导航。

## 2. 五张已确认参考图

| 文件 | 页面/用户任务 | 层级、信息和入口 | 视觉观察与跨图关系 | 当前能力核对 |
|------|--------------|-----------------|----------------|----------------|
| [01-page-map-and-maintenance-flow.png](01-page-map-and-maintenance-flow.png) | 总体导航和闭环路径参考 | 工作台、AI 助手、检修、设备四入口；串联工作台、建议列表、建议详情、任务跟进、执行反馈 | 蓝色选中态、浅色底、手机框；全局关系图而非实际页面 | 业务主路径有对应 API；图中的页面标题与分层遵从本设计文档固定导航 |
| [02-workbench.png](02-workbench.png) | 值班时快速判断“先看什么” | 助手提问入口、检修建议摘要/查看全部、任务状态/查看全部；跳至 AI、检修建议、任务跟进 | 顶部设备运营语境、重点建议卡片、状态摘要；白/浅蓝背景、藏蓝文字、操作蓝 CTA | 建议与任务数据可分别由两个 API 读取；汇总数值需基于真实响应计算，不沿用示意数值 |
| [03-ai-assistant-and-action-confirmation.png](03-ai-assistant-and-action-confirmation.png) | 通过对话查风险/原因/建议并继续到对应业务页 | 快捷问题、对话、诊断卡片、检修参考/手册、转至建议或设备详情 | 逐步呈现结构化诊断卡片，输入框固定可达；蓝色消息与深色回复 | 只读查询能力存在；图中 assistant 批准“创建检修任务”与现行 Agent 契约冲突，不能照搬。Agent 可引导至检修页创建；待批卡只用于现有工单敏感写 |
| [04-device-query-and-detail.png](04-device-query-and-detail.png) | 找设备并查看单机风险、历史与建议 | 设备列表/搜索/高风险设备筛选 → 设备详情；详情入口通向检修建议、相关任务、AI 助手 | 列表状态标签、单机信息分组、主 CTA；图片只作示意素材 | 单机诊断、风险、历史、故障类型、SOP 有按编号 API；全设备列表 API 缺失（Application 有 `get_device_list()` 但未注册 HTTP 路由） |
| [05-maintenance-suggestions-and-task-follow-up.png](05-maintenance-suggestions-and-task-follow-up.png) | 比较优先建议并推进/回顾任务 | 检修内双视图；建议含优先级/理由/查看详情/安排检修，任务含状态/调整计划/执行反馈 | 搜索与筛选位于列表顶部，卡片突出设备和可执行动作；两视图共用检修一级入口 | 建议、任务列表/详情/调整/反馈接口存在；“进度百分比”目前没有 API 字段，不能显示图中的百分比；需按状态/已有字段呈现 |

图片中的 `JT-SZ-001`、`AFC-...`、2024 日期、0.78 风险、任务计数、机身照片、通知红点等均为视觉示例，不能作为接口数据或待实现功能要求。公开仓示例编号以 `DEMO-AGM-*` 为主。

## 3. 信息架构与页面跳转

```text
底部导航
├─ 工作台
│  ├─ 检修建议「查看全部」 ─────────────▶ 检修 / 检修建议
│  ├─ 任务跟进「查看全部」 ─────────────▶ 检修 / 任务跟进
│  └─ 助手输入/快捷问题 ────────────────▶ AI 助手
├─ AI 助手
│  ├─ 设备诊断卡片的设备编号 ───────────▶ 设备详情
│  ├─ 检修建议/任务快捷动作 ────────────▶ 检修对应视图
│  └─ 工单待批卡「批准/拒绝」 ──────────▶ Interaction 审批接口
├─ 检修
│  ├─ 检修建议 ──「生成任务」→ 人工核对计划表单 → 任务跟进/任务详情
│  ├─ 检修建议中的设备编号 ─────────────▶ 设备详情
│  └─ 任务跟进 ──任务详情→ 调整/执行反馈
└─ 设备
   ├─ 设备列表 ──设备行→ 设备详情
   └─ 设备详情 ──相关建议/任务/助手分析→ 相应入口（保留 assetnum）
```

建议使用可直达的路径：`/workbench`、`/assistant`、`/maintenance?view=suggestions`、`/maintenance?view=tasks`、`/devices`、`/devices/:assetnum`、次级数据管理路径。浏览器后退需恢复检修视图、搜索和筛选；底部导航始终固定为四项。

## 4. 页面规格

| 页面 | 首要任务和内容顺序 | 主操作 | 状态与限制 |
|------|------------------|--------|----------|
| 工作台 | 当前服务/数据状态（若能真实获取）→ 检修建议摘要 → 任务状态摘要 → 助手快捷提问 | “查看全部建议”“查看全部任务”“问 AI” | 两个主入口必须深链到检修对应视图；没有 overview 汇总端点可用于装饰性 KPI，不渲染虚构趋势/数量 |
| AI 助手 | 空态与建议问题 → 对话 → 有字段来源的结构化结果卡 → 相关页面入口；输入区底部可达 | 发送问题；待批工单显式批准或拒绝 | `POST /interaction/turn` 使用 session_id；转圈/禁用重复发送；Clarified/error/fallback 状态明示。Agent 不写 maintenance task。待批卡只能依 `pending_actions` 和接口结果呈现；批准/拒绝后展示结果，不以口语确认代替按钮。有未处理待批时不能直接丢弃当前 session 开新会话 |
| 检修 / 检修建议 | 标签切换 → 搜索/筛选 → 按 API 次序展示建议 → 展开 reasons 与模拟数据说明 | 打开设备详情；“安排检修”打开确认表单（班组、日期、优先级） | 排序服务端决定；提交中防重复；创建成功回任务详情/任务跟进；空数据与预测 unavailable 需要解释 |
| 检修 / 任务跟进 | 标签切换 → 状态筛选 → 按状态分组/列表 → 任务详情与建议来源 | 查看详情、调整计划、填写反馈 | 状态来自 `planned/in_progress/done/cancelled`；图中的百分比进度不存在，不伪造。反馈字段：结果必填，是否匹配故障/是否按建议执行/备注可选 |
| 设备列表 | 搜索设备编号、车站、线路/品牌 → 设备行与状态 | 打开设备详情 | **使用已新增的只读设备列表 HTTP 路由**。Application 输出 assetnum、station、line、brand、工单数、最近工单日期；筛选只针对真实返回字段。不能在浏览器聚合风险榜/建议子集冒充全量设备 |
| 设备详情 | 设备识别信息 → 风险窗口/来源说明 → 历史故障 → 单机检修参考/故障类型（如可用）→ 相关建议/任务 | 查看建议、打开相关任务、让 AI 分析 | 依据 diagnosis 聚合优先；按需有独立 history/risk/fault-type/advice/manual 接口。Unavailable/error 与“0 风险”区分；展示风险口径免责声明 |
| 次级数据管理 | 数据概览、风险列表、工单文件导入，按独立入口或工具区访问 | 刷新概览、上传/导入 | 不加入底栏。replace/append 需明确确认；上传已是 HTTP 确认写入，不使用 Agent HITL 冒充；原始本地路径不展示 |

## 5. 视觉系统

### 方向
“设备现场的清晰操作面板”：让风险等级、设备编号、建议理由和下一步操作比装饰更醒目。以现有 Streamlit 主题和参考图为基底做收敛，而不是搬用通用营销 Hero、绿色主色或整页玻璃渐变。卡片只用于把设备/任务聚成可比较单元，不让所有内容都长成同一种卡片。

### 初始设计令牌（实现前做对比度验证）

| 令牌 | 建议值 | 用途 |
|------|--------|------|
| `ink` | `#0B1F3A` | 主标题、导航底色/强调文字 |
| `action` | `#1D4ED8` | 当前入口、主按钮、链接 |
| `canvas` | `#F5F7FB` | 页面底色 |
| `surface` | `#FFFFFF` | 内容表面 |
| `text` | `#172033` | 正文 |
| `muted` | `#5E6B80` | 次级说明（需验证小字对比度） |
| `border` | `#DFE5EF` | 分隔与输入边界 |
| `danger` | `#B42318` | 高优先级/失败；辅以图标和文字 |
| `caution` | `#B45309` | 中优先级/待处理 |
| `success` | `#047857` | 完成/服务正常 |

字体用系统中文无衬线回退栈（`"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif`），避免额外网络字体依赖。正文目标 16px、行高约 1.5，辅助信息通常不低于 12px；设备编号和数字用等宽数字但仍沿用正文字体家族。

### 响应式布局草图

手机（主目标，窄屏垂直单列；安全区与滚动底部留白）：

```text
┌──────────────────────────┐
│ 页面标题 / 当前设备或日期 │
│ 快速操作 / 关键风险信息   │
│ 建议卡 / 任务 / 诊断结果  │  ↕ 页面滚动
│                          │
├──────────────────────────┤
│ 工作台  AI助手  检修  设备│  固定底栏 + safe area
└──────────────────────────┘
```

平板/桌面：仍保留固定底部四项导航（不改成侧栏或额外主入口）；主内容居中限宽，卡片可双列或摘要/详情分栏。横屏、键盘弹出与系统安全区不可遮挡主操作。

### 组件与无障碍约定

- 统一 `AppShell`、底部导航、顶部标题、检修分段切换、建议卡、任务卡、设备卡、风险/状态标签、空/加载/错误视图、确认表单、反馈表单、toast、聊天消息和待批卡。
- 每个页面仅一个视觉主 CTA；按钮文字直接描述动作（“安排检修”“提交反馈”）。图标使用单一 SVG 图标家族，图标按钮有可访问名称。
- 手机 Web 主操作以至少 44×44 CSS px 为舒适目标、相邻操作留至少 8px；WCAG 2.2 AA 的 Web 最小目标尺寸是 24×24 CSS px（带例外），不能把 iOS pt/Android dp 直接当 CSS px。若后续嵌入原生 WebView，再按平台触控单位复核。焦点清晰、键盘可操作，弹层关闭路径明确。[WCAG 2.2 SC 2.5.8](https://www.w3.org/TR/wcag/#target-size-minimum)
- 状态不只用颜色表示：始终同时给文字和图形/语义标签；正常文本对比度目标至少 4.5:1；尊重 `prefers-reduced-motion`。
- 异步状态需有 loading/disabled、成功和可恢复错误；错误贴近对应操作或字段。空状态说明数据源/恢复动作。预测不可用不能显示成 0%。
- 长标识允许换行；筛选项空间不足时换行，不将重要状态只藏在悬停提示里。

## 6. 工程架构建议

### 结构

```text
frontend/
├─ index.html / package.json / tsconfig*.json / vite.config.ts
└─ src/
   ├─ app/                 # App、路由、AppShell、四入口
   ├─ features/
   │  ├─ workbench/        # 摘要与快捷入口
   │  ├─ assistant/        # session、turn、结构化结果、工单待批
   │  ├─ maintenance/      # suggestions、tasks、task detail、feedback
   │  ├─ devices/          # list、detail（待设备列表契约）
   │  └─ data-management/  # overview、high risk、upload（次级）
   ├─ shared/
   │  ├─ api/              # fetch client、错误归一、请求/响应类型
   │  ├─ query/            # QueryClient、服务端数据 query keys
   │  ├─ components/       # 业务无关的表单、状态、卡片基础件
   │  └─ styles/           # tokens.css、base.css、responsive.css
   └─ test/                # 单元/集成测试
└─ e2e/                    # 核心闭环浏览器验收（如采用 Playwright）
```

页面读取和提交只经 `shared/api` 的薄适配层调用 FastAPI；页面负责展示、导航和表单输入。建议排序、风险等级、任务状态机及写入规则仍留后端 Application/Domain。前端不重复算分、不拼凑替代数据、不直接调用数据库。

### 依赖建议

| 需要 | 建议 | 理由/边界 |
|------|------|-----------|
| 路由 | `react-router`（Declarative mode） | 主导航、设备详情深链、浏览器返回与筛选状态 URL；避免手写路由；按项目初始化时官方当前安装方式锁版本 |
| Vite React integration | `@vitejs/plugin-react` | 使用官方 Vite React 插件，不自写 JSX/TS 转译配置 |
| 图标 | `lucide-react` | 统一 SVG 图标；不引入整套组件库 |
| 网络 | 浏览器 `fetch` + 小型封装 | 足以支持现有 JSON/multipart API；不先加 Axios 与全局数据框架 |
| 服务端数据状态 | `@tanstack/react-query` | 工作台与检修页重复读取建议/任务，创建/调整/反馈后需统一刷新；query key + mutation invalidation 比手写跨页缓存更稳。只管理服务端缓存，不当作领域业务规则 |
| 聊天 Markdown | `react-markdown`（仅当 Agent 回答确有 Markdown） | 不启用 raw HTML 插件；外链做安全属性处理 |
| UI/CSS | 原生 CSS，CSS variables 与按 feature 命名的样式 | 无额外 CSS 框架；保留品牌和布局控制 |
| 表单 | 原生语义控件 + 明确的字段校验提示；复杂表单增多后再评估 React Hook Form | 任务字段少，先避免抽象和依赖；保留输入并把后端 422/业务错误映射到字段/表单 |
| 测试 | `Vitest` + `@testing-library/react` + `@testing-library/user-event` | 与 Vite 配合测页面交互和状态；浏览器端到端测试在闭环阶段评估 Playwright |
| 静态检查 | ESLint + `typescript-eslint` | 统一 React/TS 静态检查；不额外加格式化框架，先用现有编辑器/团队格式配置 |
| 客户端界面状态 | React state；跨页面仅存导航参数与会话标识 | 表单草稿/开合状态留在页面附近；不引入 Redux/Zustand。服务端缓存由 TanStack Query 单独管理 |

推荐开发环境由 Vite dev server 将 `/usecases`、`/interaction`、`/upload`、`/health` 代理到 FastAPI，生产环境将静态前端与 API 放在同源反向代理之后；这样不必在浏览器配置可变后端域名。若托管条件不支持同源，再以 `VITE_API_BASE_URL` 指向后端并将 CORS 收窄到实际站点。Vite `VITE_*` 值会进入客户端构建，只放公开 API base，不放密钥或数据凭据。当前没有前端身份认证/角色契约，数据管理先作为受控部署的次级能力，不宣称有权限隔离。

## 7. 成熟工程实践的取舍

- React 官方 UI 工作方法是从 mock/API 形状拆出组件，先呈现静态版本，再只为真实交互保留最小 state；本项目据此采用“可导航静态壳 → 真实读取 → 写入流程”的渐进顺序，派生计数不重复存一份状态。[Thinking in React](https://react.dev/learn/thinking-in-react)、[Managing State](https://react.dev/learn/managing-state)
- 用 React Router 声明式嵌套路由保持 AppShell 和四项底栏跨页面稳定，子路由承载检修视图与设备详情；按初始化时官方当前 package/API 决定版本，不在文档中长期钉死过期写法。[React Router routing](https://reactrouter.com/start/declarative/routing)
- 借鉴 GitHub Primer 的 base → functional → component token 分层，但只借用 token 命名与语义色原则，不引入 Primer 全套组件或更换 AFVC 品牌色。[Primer color tokens](https://primer.style/product/getting-started/foundations/color-usage/)
- 表单错误说明原因和修复方式、保留用户已填内容；服务端仍是最终校验者，多字段错误需有汇总/焦点管理。参考 GOV.UK 验证错误恢复模式，不照搬其视觉皮肤。[GOV.UK validation](https://design-system.service.gov.uk/patterns/validation/)
- 工作台和检修页复用建议/任务 query，成功写入后按 query key 失效并拉取真实结果，不做乐观伪成功。TanStack Query 明确支持 mutation 后失效关联 query。[TanStack Query mutation invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)
- 单测从用户可访问名称、可见 DOM 与动作验证；关键 E2E 使用隔离会话和用户可见 locator，Playwright 设备模拟做移动视口冒烟。[Testing Library](https://testing-library.com/docs/react-testing-library/intro/)、[Playwright best practices](https://playwright.dev/docs/best-practices)、[Playwright device emulation](https://playwright.dev/docs/emulation)
- 工程环境变量只包含公开配置，敏感值绝不编译到前端 bundle。[Vite env variables](https://vite.dev/guide/env-and-mode)

以上是方法参考，不要求安装 Primer/GOV.UK 组件库或复制其他产品的页面风格。

## 8. API 映射摘要

本表仅列路径与职责，不维护第二套完整字段字典。字段应以运行 `/docs` 和对应 Pydantic 模型为准。

| 页面动作 | 接口（状态） | 已核实请求/响应要点 |
|----------|----------|------------------|
| 工作台检修建议 | `GET /usecases/maintenance/suggestions?top_n=&fault_focus=` | 返回 `suggestions[]`、`reasons[]`、`ranking_method`、`model_note`、`prediction_tier`；服务端确定顺序，接口未提供生成时间 |
| 首页任务摘要 / 任务页 | `GET /usecases/maintenance/tasks?status=` | 返回 `tasks[]`、`count`；状态筛选可选 |
| 从建议排任务 | `POST /usecases/maintenance/tasks` 或 `POST /usecases/maintenance/accept-suggestion` | create 可接 `assetnum`、站点、故障焦点、优先级、日期、班组、status、建议分数/理由；accept 只接 suggestion 与 priority，若需编辑计划字段优先用 create |
| 任务详情/修改/反馈 | `GET /usecases/maintenance/tasks/{task_id}`、`PATCH /usecases/maintenance/tasks/{task_id}`、`POST /usecases/maintenance/tasks/{task_id}/feedback` | patch 字段 priority/date/crew/status；feedback 的 result 必填，matched_fault/followed_suggestion/note 可选；成功反馈通常置 done |
| 风险榜 | `GET /usecases/high-risk?top_n=` | 高风险设备列表及 prediction tier/note（以当前实现响应为准） |
| 设备列表（已实现） | `GET /usecases/devices`，经 `application.usecases` 门面调用 `application.history.get_device_list()` | 薄路由及 Pydantic 响应模型已加入；响应沿用 `status/message/device_count/devices[]`，不另写业务聚合 |
| 单设备详情 | `GET /usecases/devices/{assetnum}/diagnosis` | 聚合 profile、history summary、risk prediction、maintenance advice、fault prediction、说明 |
| 单设备分项 | `GET .../{assetnum}/history?limit=`、`/risk`、`/fault-type?window_days=&top_k=`、`/advice` | 故障类型仅支持特定窗口，可能 `unavailable`；risk 是未来工单复发风险 |
| 手册 | `GET /usecases/manuals/search?query=&assetnum=&top_k=` | 结果来自样例/本地手册检索 |
| 对话 | `POST /interaction/turn` | body `query`（1–500 字）与可选 `session_id`；响应含 status、final_answer、result、session_id、assetnum、pending_actions 等；前端仅在当前 tab 的 `sessionStorage` 保留 session_id/可见 transcript，刷新时配合 pending GET 恢复待办，没有服务端 transcript 读取接口 |
| 待批查询/解决 | `GET /interaction/sessions/{session_id}/pending`；`POST /interaction/approve` 或 `/reject` | approval body 要 session_id/action_id；显式按键；409 可含 `run_in_progress`、`action_conflict`、`action_failed`，404 有 `action_not_found` |
| 概览/数据导入 | `GET /usecases/overview?top_n=`、`POST /upload/workorders?mode=replace|append` | 上传接受 xlsx/xls/csv；SQL 模式会保存原文件并导入；replace/append 是已确认写操作 |

通用错误：FastAPI 参数校验 `422`；用例找不到/ValueError 常映射 `404`；未分类异常常返回 `500`。交互待批有上述结构化 `detail.code`，UI 按 code 映射提示并允许重试/返回。默认配置 `AFVC_USE_LLM=false` 走规则兜底；模型供应商不可用时 interaction 会回退并标注 `result.source=legacy_fallback`、`degraded=llm_unavailable`；程序/DB/图错误不会静默伪装成降级。当前没有 API 获取历史对话全文的路由；前端会话 UI 不可假设可从服务器恢复完整 transcript。

前端 API client 的行为约定：

- GET 可在明确的网络错误/5xx 场景有限重试；422/404 不自动重试。对话“运行中”409 允许用户等待后显式重试。
- POST/PATCH 写入默认**不自动重试**，避免不确定响应导致重复建任务或重复提交反馈。网络中断后先刷新任务/待批状态，再由用户决定下一步。
- 写入按钮提交中禁用并给即时状态；成功后失效相关 TanStack Query key，从服务器重新读取最终对象，不以乐观 UI 声称成功。
- 输入搜索改变导致旧请求过期时取消/忽略旧响应，避免慢响应覆盖新条件。

### API 缺口与计划建议

- **全设备列表：** 阶段 0 已将 `get_device_list()` 经 Application 门面导出，并新增只读 `/usecases/devices`、Pydantic 响应模型、`docs/API.md` 和 API pytest。前端使用完整列表，不把风险榜或建议子集称作全量设备。
- **任务百分比进度：** 图中有 60%，`maintenance_tasks` API/schema 没有进度百分比；按真实状态展示。
- **Agent 创建检修任务：** Agent write tools 对 create/adjust/feedback 为 `exposed=False`；现有可审批敏感操作是工单增删改/导入。助手只读检修建议/任务并导航到检修页。

## 9. 前端阶段验收的共通要求

每阶段只交付可运行、可回滚的切片；页面在手机窄屏可用并保留桌面响应式；数据接口、加载/空/失败/不可用各状态均有可检查表现；关键交互有单测，核心闭环有浏览器级验收；不把截图示例值作为 fixture 之外的真实结果。具体阶段、文件、测试和产物见 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)。
