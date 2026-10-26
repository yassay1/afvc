# AFVC HTTP API

面向控制台与集成方的接口说明。编排层如何调同一套能力见 [ORCHESTRATION.md](./ORCHESTRATION.md)。

**写法约定（参考常见工程实践）：** 按资源分组写清方法、路径、用途与关键参数；请求/响应字段的权威来源是运行中的 FastAPI 与代码里的 Pydantic 模型（本地 `http://127.0.0.1:8000/docs`）。本文不重复维护第二份字段表，避免与实现漂移。

默认基址：`http://127.0.0.1:8000`。JSON 请求/响应，编码 UTF-8。

## 1. 通用约定

| 项 | 说明 |
|----|------|
| 成功 | 多数用例返回 JSON，业务上常带 `status` 字段（如 `success`） |
| 校验失败 | `422`（FastAPI / 业务窗口不合法等） |
| 未登录 | `401`，`detail` 多为「未登录」或「用户名或密码错误」 |
| 资源或业务找不到 | 当前实现多为 `404`，`detail` 为字符串或结构化对象 |
| 冲突 | 对话审批等：`409`，`detail` 常含 `code`（如 `action_conflict`、`run_in_progress`） |
| 服务器错误 | `500`，`detail` 含错误信息 |

审批类错误优先看 `detail.code`，不要依赖文案。

**门禁：** 固定账号、无自助注册。`/usecases/*`、`/interaction/*`、`/upload/*` 均要求有效会话 Cookie（默认名 `afvc_session`，HttpOnly）。账号由运维在服务器执行 `python -m backend.scripts.manage_user create|disable|enable|reset-password <username>` 管理（交互输入密码）。前端登录后同源请求自动带 Cookie。

| 方法 | 路径 | 用途 | 关键参数 |
|------|------|------|----------|
| POST | `/auth/login` | 登录并设置会话 Cookie | `username`，`password` |
| POST | `/auth/logout` | 撤销会话并清除 Cookie | 无 |
| GET | `/auth/me` | 当前登录用户 | 无；未登录 `401` |

健康检查：`GET /health` **可匿名**（本机/反代探活）；返回 `data_profile=demo|production`；前端全局“演示数据”标记只根据此字段显示，无法由 Vite 变量伪装。

## 2. 维修作业（主路径）

| 方法 | 路径 | 用途 | 关键参数 |
|------|------|------|----------|
| GET | `/usecases/maintenance/suggestions` | 检修建议排序清单（服务端排序 + reasons） | `top_n`，`fault_focus` |
| POST | `/usecases/maintenance/accept-suggestion` | 由一条建议生成检修任务 | body：`suggestion` 或扁平字段；可选 `priority` |
| GET | `/usecases/maintenance/tasks` | 列出检修任务 | 可选 `status`：`planned` / `in_progress` / `done` / `cancelled` |
| POST | `/usecases/maintenance/tasks` | 创建检修任务 | `assetnum` 必填；可选车站、班组、优先级、日期等；新建时不能直接设为完成 |
| GET | `/usecases/maintenance/tasks/{task_id}` | 单条任务 | 路径 `task_id` |
| PATCH | `/usecases/maintenance/tasks/{task_id}` | 调整优先级/日期/班组/状态 | body 字段均可选；从未完成状态转为完成须先提交现场执行反馈 |
| POST | `/usecases/maintenance/tasks/{task_id}/feedback` | 记录现场执行反馈并将任务置为完成 | `result` 必填；可选是否匹配故障类、是否按建议执行、备注 |

直接将新任务或未完成任务改为完成会返回 `409`，须先通过反馈接口记录现场结果；任务仍使用 `maintenance_tasks` 流程，与工单对话的 `pending_actions` 审批分离。任务优先级须为大于 0 的整数；空白现场反馈和空调整请求返回 `422`。

建议排序由服务端确定性规则完成；客户端**不应**再把列表交给模型重排。

## 3. 预测（可占位）

| 方法 | 路径 | 用途 | 关键参数 |
|------|------|------|----------|
| GET | `/usecases/high-risk` | 高风险设备 Top N | `top_n` |
| GET | `/usecases/devices/{assetnum}/risk` | 单设备多窗口风险 | 路径 `assetnum` |
| GET | `/usecases/devices/{assetnum}/fault-type` | 故障类型参考 | `window_days`（须为支持窗口），`top_k` |

无外部预测表或与工单对不齐时，服务端可能走统计基线或返回不可用类结果，以响应字段为准。

## 4. 数据基础与知识

| 方法 | 路径 | 用途 | 关键参数 |
|------|------|------|----------|
| POST | `/upload/workorders` | 上传工单 Excel/CSV 并导入 | multipart 文件；`mode`=`replace`\|`append` |
| GET | `/usecases/overview` | 工单数据概览 | `top_n` |
| GET | `/usecases/devices` | 完整设备列表（复用 Application 设备聚合）；返回 `status`、`message`、`device_count`、`devices[]` | 无；设备项含 `assetnum`、`workorder_count`、`station_name`、`line`、`brand`、`last_record_time`，后四项可为空 |
| GET | `/usecases/devices/{assetnum}/history` | 设备历史 | `limit` |
| GET | `/usecases/devices/{assetnum}/advice` | 单设备巡检/SOP 向参考（≠ 检修建议排序清单） | 路径 `assetnum` |
| GET | `/usecases/devices/{assetnum}/diagnosis` | 遗留：设备综合诊断聚合（非维修作业主路径） | `history_limit` |
| GET | `/usecases/manuals/search` | 手册检索 | `query` 必填；可选 `assetnum`，`top_k` |

上传通道视为控制台已确认写入；与对话侧工单 HITL 不是同一条路径。`demo` profile 对上传返回 `403`，且在写入 raw 文件前拒绝；新 React 前端不提供上传入口。

## 5. 对话（编排入口）

| 方法 | 路径 | 用途 | 关键参数 |
|------|------|------|----------|
| POST | `/interaction/turn` | 一轮对话（主路径 Agent；LLM 关则规则兜底） | `query`；可选 `session_id` |
| POST | `/interaction/approve` | 批准待写操作 | `session_id`，`action_id` |
| POST | `/interaction/reject` | 拒绝待写操作 | 同上 |
| GET | `/interaction/sessions/{session_id}/pending` | 列出待批 | 路径 `session_id` |

口语确认（如「好的」）**不会**批准写操作；必须打 approve/reject。

`POST /interaction/turn` 的业务响应 `status` 可能为 `success`、`clarified`、`rejected` 或 `error`。规则兜底中的只读用例失败时仍返回对话响应，但 `status=error`；前端应将其呈现为查询未完成。主图/接口级异常仍按 HTTP 错误返回。

典型 `409`：`run_in_progress`（同会话上一轮未结束）、`action_conflict` / `action_failed`（审批状态冲突或执行失败）。

## 6. 与实现的关系

| 来源 | 用途 |
|------|------|
| 本文 | 有哪些资源、为何调用、主路径是哪些 |
| `GET /docs`（Swagger UI） | 当前请求/响应 schema 与试调 |
| `backend/api/*.py` | 路由与状态码映射的真相 |

新增或变更对外路径时：先改代码与 `/docs`，再改本文表格，保持三者一致。
