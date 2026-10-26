# AFVC 手机端 Web

React + TypeScript + Vite 前端接入工作台、检修闭环、设备查询/详情、AI 助手和次级只读数据管理。

## 本地启动

需要 Node.js 24 LTS、npm，以及运行中的 FastAPI（默认 `http://127.0.0.1:8000`）。从仓库根目录启动后端：

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

在另一个终端：

```powershell
cd frontend
npm ci
npm run dev
```

打开 Vite 输出的本地地址。开发服务器将 `/usecases`、`/interaction`、`/upload`、`/health`、`/auth` 转发至 FastAPI。若后端地址不同，在 `frontend/.env.local` 设置 `AFVC_API_PROXY_TARGET`。前端默认使用同源相对 API 路径；只有部署平台无法做同源反向代理时才设置公开的 `VITE_API_BASE_URL`。任何 `VITE_*` 值都会进入浏览器构建，不能放密钥。生产环境建议将静态资源与 API 放在同一域名反向代理下。站点需登录（固定账号，无自助注册）；账号由服务器 CLI 创建。

本地合成演示库的 Compose 启动方式见根目录 `README.md`。“体验环境”说明只依据后端 `/health.data_profile` 显示，并统一放在每页内容顶部；后端不可达或未返回有效模式时，页面提示“数据模式未确认”。体验环境中的设备、检修任务、风险数据和配图属于演示内容；生成配图不对应任何接口设备，也不是现场实拍。建议顺序、设备编号和任务信息仍来自后端。工作台快捷问题和输入框会把问题发送到现有 AI 助手会话。

检修任务卡按服务端返回顺序显示状态、设备、计划日期和执行班组；主操作根据状态进入任务详情的计划或反馈区域。当前任务接口没有执行进度百分比和展示级别字段，列表不推断这些信息。

设备列表的“全部设备”保持 `/usecases/devices` 返回顺序；“风险关注”展示 `/usecases/high-risk?top_n=10` 的前 10 台及服务端预警级别。线路和品牌筛选仍使用设备列表字段。设备配图只是场景示意，不代表单台设备实物；当前列表接口没有运行状态字段，因此不显示“运行正常”等推测状态。

深链由 React Router 处理。生产 Web 服务器需将非 API 页面路径回退到 `index.html`。

## 验证

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

首次运行 Playwright 测试需 `npx playwright install chromium`。本地已有 Chrome 时，可在 PowerShell 先设置 `$env:AFVC_PLAYWRIGHT_CHANNEL='chrome'`，再运行 `npm run test:e2e`。持续集成运行 typecheck、lint、单测和构建；浏览器测试在发布验收时单独执行。

## 依赖取舍

`package-lock.json` 固定完整依赖树，使用 `npm ci` 复现。`react-router` 管理深链及浏览器返回；`@tanstack/react-query` 管理跨页服务端缓存，写请求不自动重试；`lucide-react` 提供一致的 SVG 图标。网络层使用原生 `fetch`，样式使用 CSS 变量和原生 CSS。Vitest、Testing Library、ESLint、typescript-eslint 负责交互与静态检查；Playwright 只用于关键浏览器流程。助手回答使用安全的 CommonMark/GFM 子集渲染段落、列表、强调和表格；窄屏表格可横向滚动，原始 HTML 不会执行，Markdown 图片不会请求外部资源。未引入 UI 套件、Redux 或 Axios。

AI 助手的会话标识与可见对话只保存在当前标签页 `sessionStorage`。刷新后从服务端重新查询待批工单操作；后端没有读取完整历史对话的 API。生产部署应配置同源反向代理，并限制站点访问，因为当前 API 尚无用户身份与角色授权。

体验环境中的设备显示名由本地稳定映射生成，原业务编号始终作为“设备编号”显示并用于检索和跳转。体验环境设备卡片使用四款统一风格的生成闸机图，并按设备编号稳定分配；它们不是现场实拍。生产档案没有真实名称或有来源图片时，分别回退显示原设备编号和空图片占位，不复用体验资料。

工单上传仍处于阶段 6b 门槛之外。当前没有受控内网部署和数据负责人许可的证据，后端也没有用户身份/角色授权，因此新前端只开放概览与高风险只读入口；`POST /upload/workorders` 未连接到新页面。
