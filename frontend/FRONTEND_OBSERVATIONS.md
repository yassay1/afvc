# AFVC 前端观察记录（与 LLM/API 结果分开）

## 记录规则
- 每条都关联用户提供的页面截图和具体交互现象；截图没有提供时标明“未提供”。
- 单独记录设备/浏览器尺寸、页面路径、可复现步骤、实际视觉/交互结果、预期结果。
- 将 LLM 答复内容、HTTP 状态、工具选择/trace、后端错误标为“LLM/API 证据”，不单独归类成 UI 缺陷。
- 只在截图或交互现象指出呈现、布局、可访问性或操作反馈问题时建立 UI 项；不虚构数据，保留现有业务逻辑和 API。
- 一组明确问题一次处理。修完后运行真实页面、提供真实截图、记录剩余差距，然后等待用户确认才开始下一组。
- 界面评审或修改前应用 `frontend-design` 与 `ui-ux-pro-max` 技能。

## UI 观察

_当前没有用户提供的页面截图或交互现象，尚无 UI 问题项。_

| 编号 | 轮次/页面 | 截图 | 用户描述的现象/复现步骤 | UI 证据与问题 | 排除的 LLM/API 因素 | 优先级/状态 |
|---|---|---|---|---|---|---|

## 已处理问题与复核

- UI-01 助手回答 Markdown 呈现：已完成并在真实助手页复核；AssistantMarkdown 模块按需加载，构建产物拆出约 160 KB（gzip 49 KB）的助手格式 chunk，入口 chunk 约 368 KB；无 500 KB chunk 警告。
- 复核截图：当前任务内嵌浏览器工具输出（T3 宽表横向滚动、T4 手册长答格式化）；运行时 transcript 保留，未另存 PNG 文件。


## UI-01：助手回答将 Markdown 语法作为纯文本展示（已修复）

- 页面/设备：本地 React 助手页 `/assistant`，内嵌浏览器移动视口约 459×600。
- 证据：同会话 T2 风险结果、T3 历史结果、T4 手册摘要截图可见 `|---|` 表格分隔符、`**粗体标记**` 等未被格式化。T2/T3 结果结构化程度较高，字符语法增加阅读负担；输入框固定在底部，用户需滚动长对话查看。
- 分类：**前端呈现**。回答内容及数据由接口返回；页面当前将整段 `final_answer` 放入 `<p>`，按 `white-space: pre-wrap` 呈现。此项不是 tool routing 或 API 状态问题。
- 页面 API 方面的测试证据另见 `LLM_TEST_LOG.md`；UI 会话的网络响应/trace 未能单独提取，不借用独立 API 会话的 trace。
- 风险/范围：只改善安全显示的 Markdown 子集（标题、粗体、列表、表格、行内代码）；保留服务端文本、API、业务流程和模拟数据，不运行不受信任的 HTML。移动表格须限制宽度并允许横向滚动，长段正文保持易读行距。
- 技能评审：`frontend-design` 要求围绕移动现场操作保持安静清晰层级，避免改动蓝/藏蓝业务色；`ui-ux-pro-max` UX 检索命中“移动端表格可能溢出，采用横向滚动或卡片布局”，并建议正文行高 1.5–1.75。React stack 检索未命中 Markdown 安全渲染建议。
- 修复状态：完成。`AssistantMarkdown.tsx` 将标题、段落、列表、强调和 GFM 表格渲染为语义 HTML；原始 HTML 跳过、Markdown 图片不加载；宽表可键盘聚焦并横向滚动。助手回答 Markdown 实现按需分包。

## UI 轮次截图和交互现象

- T1：回复请求设备编号并提及可查询高风险清单；页面成功显示助手回答。
- T2：风险结果成功展示，Markdown 原样显示；截图在当前任务工具输出。
- T3：上下文设备编号延续成功，最近工单历史展示；Markdown 表格在窄视口易读性差；截图在当前任务工具输出。
- T4：长输入成功提交并收到助手回复，输入框仍可用；回答文案声称的工具次数不作为证据；截图在当前任务工具输出。
- 本地真实数据模式为 demo；不把任何示例设备/任务数据作为生产事实。

## UI-02：工作台建议卡片的横向滑动提示不足（已修复）

- 页面/设备：本地 React 工作台 `/workbench`，真实 IAB 截图视口约 459×600；截图显示第一张建议卡完整，右侧第二张卡只露出一部分。
- 实现证据：`.suggestion-list` 使用 `overflow-x: auto` 和 scroll-snap，但隐藏 WebKit/Firefox 滚动条；列表没有可见的“左右滑动”说明或前后按钮。数据仍由 API 给出，当前只显示返回顺序的前 3 项。
- 分类：候选 UI 可发现性问题。第二张卡的露出可能已构成滑动暗示，需要在真实触摸操作中确认用户是否容易发现，暂不认定为已确认缺陷。
- 推荐解法：若确认难发现，保留卡片 peek 和服务端顺序，在两条及以上建议时加一条轻量“左右滑动查看更多建议”提示；不添加虚构计数，不改变建议排序或 API。复核触摸横滑、键盘 Tab/焦点滚动与无障碍树。
- 附带可选观察：卡片箭头链接的 CSS 命中区为 32×32 CSS px；这超过 WCAG 常见的 24×24 CSS px 最低尺寸，但低于 iOS 44pt / Android 48dp 的平台舒适建议。若用户选择触控目标优化，应作为独立问题组，扩大到不遮挡文案的范围。
- UI Pro Max 检索提示触控目标需区分平台单位，网页以 24 CSS px WCAG 规则为基线；故 32px 记录为可用性优化候选，不标为合规缺陷。
- 修复：在建议列表前加入双向箭头和“左右滑动查看更多建议”提示，仅当服务端建议超过 1 项时显示；保留卡片 peek、scroll-snap、列表顺序、接口和卡片内容。
- 复核：390×844 CSS px 移动视口下真实截图显示提示和卡片 peek；实际横向滚动从第一项到第三项，再返回第一项成功。body clientWidth=375、scrollWidth=375，无页面级横向溢出；建议列表 clientWidth=317、scrollWidth=807、overflow-x=auto、scroll-snap-type=x mandatory。单条建议的条件由单测验证为不显示提示。
- 构建验证：工作台测试 4 passed；typecheck、lint、build 通过。
- 状态：完成；代码位于 `Workbench.tsx`、`workbench.css`，测试位于 `Workbench.test.tsx`。

## UI-03：建议卡片箭头触控命中区偏小（已修复）

- 页面/设备：本地 React 工作台 `/workbench`；由当前 IAB 页面在 390×844 CSS px 移动视口捕获真实截图。用户未另附截图；截图在本轮工具输出。
- 问题证据：UI-02 检查时发现卡片箭头链接原为 32×32 CSS px。它超过 WCAG 2.2 AA 2.5.8 常见的 24×24 CSS px 最低尺寸，但触控更容易点击的目标可更大；单独作为舒适度改进，不标成合规缺陷。
- 修复：把链接透明命中区扩为 44×44 CSS px，圆形白底和箭头保持 32×32；通过调整外框偏移保持原圆形视觉中心不变。保留链接目标、无障碍名称及卡片布局。
- 复核：真实页面测得链接 44×44、圆形图标 32×32；无障碍名称仍为“查看 DEMO-AGM-011 的全部建议”；body clientWidth=375、scrollWidth=375，无页面级横向溢出。移动截图中圆形图标尺寸和位置观感不变。
- 验收：工作台测试 4 passed；typecheck、lint、build 均通过。未执行链接导航，避免改变页面状态。
- 剩余差距：无；当前页面使用 demo 体验数据，未涉及后端/LLM。
- 状态：完成；代码位于 `Workbench.tsx`、`workbench.css`。

## UI-04：移动端输入框显示无用的原生缩放手柄（已修复）

- 页面/设备：本地 React 助手 `/assistant`，真实 IAB 390×844 CSS px 视口；本轮截图中输入框右下角有一条原生 textarea resize 手柄。用户未另附截图；截图在本轮工具输出。
- 分类：前端视觉细节。页面层级、服务端回答及工具路由未涉及。
- 修复：窄屏（≤620px）将 composer textarea 的 `resize` 设为 `none`，去掉触屏设备难以操作且视觉突兀的原生手柄；桌面端垂直调整能力保留，textarea 的 500 字限制和输入方式不变。
- 复核：真实页面计算样式确认窄屏 `resize=none`，截图确认手柄不再显示；页面宽度和滚动未变化。桌面规则未更改。
- 剩余差距：本组只处理静态欢迎态输入框装饰细节；助手长对话的滚动行为未在本组实测，也不据此做缺陷结论。
- 状态：完成；代码位于 `assistant.css`。

## 组 A：体验数据与来源表达（2026-10-26）

- **页面与视口：** 本地运行 React 页面 `/workbench`、`/maintenance?view=suggestions`、`/assistant`；IAB 视口为 1023×879 CSS px（布局内容宽 1008 px）。截图由真实页面在本对话浏览器工具中捕获。
- **修改前：** 工作台截图中体验环境说明在页面最底部，需滚动后才看到；助手和数据页提示在顶部，形成不一致。工作台、检修建议卡均把 `90 日复发风险 0.75` 直接展示为理由。
- **修改后工作台截图：** 顶部一条体验说明写明设备、检修任务和风险数据为演示内容，设备配图为生成素材而非现场实拍。三张工作台建议卡把风险说明显示为“未来 90 天内再次出现故障工单的风险参考值：75%”。
- **修改后检修页截图：** 卡面仍显示风险和首要解释；展开“查看完整依据与数据来源”后看到完整服务端理由、外部预测结果文件名和“接口未提供该数据的更新时间”。明确模拟资源不代表现场排班或库存。
- **可访问性/状态：** 体验说明 `role=status` 且由后端 profile 驱动；未知 profile 保留 `role=alert`；展开控件使用语义化 `<details>/<summary>`，焦点轮廓保留且触达高度至少 44 px。未声称完整 WCAG 合规审计。
- **Production UI 测试：** profile 为 production 时没有体验说明；真实 production 服务与真实来源数据仍待部署验证。
- **截图证据：** 本对话中有修改前 `/workbench`、修改后 `/workbench`、展开依据的 `/maintenance?view=suggestions` 真实截图输出。
## 组 B：设备名与体验配图（2026-10-26）

- **真实页面/视口：** 本地运行 `http://127.0.0.1:5173`，Chrome 1023×879 CSS px。逐页核对 `/workbench`、`/maintenance?view=suggestions`、`/maintenance?view=tasks`、`/devices?q=DEMO-AGM-018`、`/devices/DEMO-AGM-018`、`/assistant?assetnum=DEMO-AGM-018`。
- **观察与结果：** 同一 demo 编号 `DEMO-AGM-018` 在设备列表、设备详情和助手上下文均显示“月港站闸机 03”，并保留“设备编号 DEMO-AGM-018”；设备列表搜索编号后结果仍可用，详情/助手链接仍指向原编号 URL。工作台、检修建议及任务卡显示同一设备身份。
- **图片：** 真实卡片中看到不同闸门外形的生成图片；相同编号跨列表和详情图像一致。全局体验横幅注明“设备配图为生成素材，并非现场实拍”，卡片未重复贴标。真实生产图片没有证据，production profile 用中性占位，不展示体验图。
- **接口证据：** 只读 `/health` 返回 `demo`；`/usecases/devices` 返回 36 台，字段无名称或图片来源；固定映射完整覆盖 36 台，显示站点与接口站点一致。显示名/图片不改 API 响应。
- **截图：** 当前仓库任务目录 `.planning/afvc-llm-qa-2026-10-26/screenshots/group-b-*.png`，包含以上 6 个页面的 1023×879 视口截图。
- **可访问性/局限：** 编号辅助行 12px；原始 ID 仍可读和可复制。此组未做完整 WCAG 审计，也未验证真实生产名称与图源，因为生产接口没有该字段/来源证据。

## 组 C：术语一致性和任务动作（2026-10-26）

- **统一显示：** 工作台标题“检修工作台”；导航与答复主体“AI 助手”；建议列表“检修建议”；任务入口“任务跟进”；风险清单“高风险设备”。无服务端生成时间时移除“今日”，计划任务 CTA 改为“调整计划”，与详情页实际落点一致。
- **设备引用：** 在 demo 助手 Markdown 表格/段落里，系统已知的设备编号显示为设备名并在下方保留“设备编号 …”；检查 `href` 仍为原 assetnum URL。production 模式保持接口标识原样。答复原文、排序、数据和接口没有被前端改写。
- **复核页面：** `/workbench`、`/assistant` 空态与只读回答、`/maintenance?view=tasks`、`/devices?view=attention`、`/data?view=risk`，常规截图视口 1023×879 CSS px。截图 `group-c-workbench.png`、`group-c-assistant-empty.png`、`group-c-assistant-query-final.png`、`group-c-maintenance-tasks.png`、`group-c-device-risk-filter.png`、`group-c-risk-data.png`。助手完整表格另以 1023×1400 CSS px 截取 `group-c-assistant-table.png`，十台设备名称和编号均可见；风险页标题与设备入口一致。
- **验收：** 相关前端测试 18 passed，AssistantMarkdown 定向用例 4 passed；typecheck、lint、build 通过。LLM 回答内容与工具路由观察另记 `frontend/LLM_TEST_LOG.md`；本组的助手查询未创建任务、无待批卡。
- **遗留：** `warning_level` 橙/黄色的业务含义接口/文档未定义，保持现有数据标签，不擅自解释。一次 AssistantPage 全文件测试中两个待批拒绝/超时交互断言失败；它们非本组改动，尚未归因或修复。

## 组 D：任务完成和现场反馈（2026-10-26）

- **页面/任务证据：** 只读 GET 列出 demo tasks。`981617e5-7b21-5177-aea8-be942207ec5c`（DEMO-AGM-007）为 `in_progress` 且没有反馈；已完成 demo 任务均含合成反馈。未向服务发送创建、PATCH、feedback 或工单写请求。
- **修复后实页：** `/maintenance/tasks/981617e5-7b21-5177-aea8-be942207ec5c`，Chrome 1023×879 CSS px；状态下拉只有“待执行/执行中/已取消”，提示“提交现场执行反馈后，任务会自动标记为已完成”，现场结果为必填。执行反馈滚动视口截图 `group-d-feedback-form-viewport.png`，完整详情截图 `group-d-task-feedback-gate.png`。
- **行为边界：** 真实页面仅加载数据并截图，没有提交反馈。状态变化和禁用直接完成行为由应用/API mocked repository 单测及前端 mock 测试覆盖。检修任务走 `/usecases/maintenance/tasks`；pending_actions/HITL 未显示或写入。
- **验收：** 应用/API 隔离用例 4 passed，MaintenancePage 6 passed（含 409 下一步提示），typecheck、lint、build 通过。HTTP 409 和具体文案由 mock API 测试覆盖，未向运行中服务发送变更请求。
- **生产限制：** 未验证生产任务、身份权限或真实现场反馈流程；身份/角色授权仍搁置。DEMO 的任务反馈是体验数据，不可作为现场完成证据。

## 组 E：任务详情的建议依据（2026-10-26）

- **问题证据：** 组 D 的真实 demo 任务详情截图中，“检修建议依据”直接显示“合成风险输入 / 模拟站点重要度 / 模拟班组及备件资源”。这是界面映射问题，不是 API 错误或模型答复。
- **修复和结果：** 卡面改为“风险参考信息（体验数据） / 站点参考信息（体验数据） / 班组与备件参考信息（体验数据）”。原服务端短语仍在“查看服务端返回的完整依据”折叠区，展开后逐字可见。
- **截图与视口：** 真实 `/maintenance/tasks/981617e5-7b21-5177-aea8-be942207ec5c`，1023×879 CSS px。`group-e-task-reasons-collapsed.png` 与 `group-e-task-reasons-expanded.png` 分别记录折叠/展开。
- **验收：** formatter + MaintenancePage 测试 9 passed；typecheck、lint、build 通过。没有发起任何 API 写请求；没有 LLM/UI 工具调用。

## 组 F：Demo 配图外观差异（2026-10-26）

- **修改依据：** 用户反馈现有设备图片差别偏小。旧图四张都属于相近的不锈钢摆门结构，设备列表卡片缩略图难区分。
- **修改：** 四张生成图变为白色机壳摆门、三辊闸、宽通道摆门和高翼门；统一地铁站环境与写实光线，去除厂牌/文字。设备编号→图片的稳定哈希逻辑和资源名未更改；全局 DEMO 条仍说明图片生成、并非实拍。
- **真实页面：** `/devices`，Chrome viewport 1023×879 CSS px，截图 `group-f-images-variety.png`。30 张加载卡中用到全部 4 个资源；刷新后 26 台交集设备的编号对应图片保持一致；页面无横向溢出。当前列表首屏分页为 30 台，截图为 full page。
- **验证：** deviceIdentity、Devices、Workbench 3 个前端测试文件 12 passed；typecheck、lint、build passed。未触发 API/LLM/任务写入；production UI 代码路径未变。

## 组 G：橙/黄预警颜色区分（2026-10-26）

- **用户截图问题：** 截图中“黄色预警”和“橙色预警”都是红色徽标。
- **原因：** Workbench/检修建议类名没有区分状态，一条固定红底 CSS 覆盖所有标签；设备详情/风险入口也缺少统一映射。
- **修复：** 建共享精确标签展示类，在工作台、检修建议、设备列表、设备详情、高风险列表使用同一映射。`橙色预警`深橙底白字，`黄色预警`浅黄底深棕字，`绿色关注`浅绿底深绿字，接口未见标签用中性色。徽标文字保留；颜色只是呈现原标签，不解释优先级或风险级别。
- **实页证据：** demo `/maintenance?view=suggestions`，Chrome 1023×879 CSS px，页面实测 class 和 computed background/color；橙色 rgb(194,65,12)/白字，黄色 rgb(254,243,199)/深棕字；body 宽度 1023/1023。截图 `group-g-warning-colors.png`。
- **API 证据：** 只读 `/health` profile=demo；`/maintenance/suggestions` 与 `/high-risk` 返回橙色 9、黄色 9、绿色关注 18。未调用 LLM 或写入端点。
- **验证：** warningLevel helper + Devices、MaintenancePage、Workbench、DataManagement 共 5 个测试文件 21 passed；typecheck、lint、build passed。
