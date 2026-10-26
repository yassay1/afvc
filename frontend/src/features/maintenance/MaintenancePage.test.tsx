import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../../app/App'
import { withLoggedInFetch } from '../../test/authFetch'

const suggestions = {
  status: 'success', message: '建议生成成功', prediction_tier: 'statistical_baseline', model_note: '统计基线',
  suggestions: [
    { assetnum: 'DEMO-Z', station_name: '乙站', fault_focus: '暂停服务', warning_level: '高', reasons: ['先看历史', '模拟班组可用'], data_note: '班组为模拟', score: 0.2, suggested_crew_id: 'CREW-A' },
    { assetnum: 'DEMO-A', station_name: '甲站', fault_focus: '暂停服务', warning_level: '中', reasons: ['另一条理由'], data_note: null, score: 0.9, suggested_crew_id: null },
  ],
}

type Task = Record<string, unknown> & { id: string; assetnum: string; status: string }

function setupApi(options: { createStatus?: number; patchStatus?: number; feedbackStatus?: number; deferredCreate?: boolean } = {}) {
  const tasks: Task[] = []
  const calls: { path: string; method: string; body: Record<string, unknown> | null }[] = []
  let resolveCreate: ((response: Response) => void) | undefined
  const respond = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : null
    calls.push({ path, method, body })
    if (path.includes('/suggestions')) return Promise.resolve(respond(suggestions))
    if (path.endsWith('/maintenance/tasks') && method === 'GET') return Promise.resolve(respond({ status: 'success', tasks, count: tasks.length }))
    if (path.endsWith('/maintenance/tasks') && method === 'POST') {
      if (options.createStatus) return Promise.resolve(respond({ detail: 'failed' }, options.createStatus))
      const task: Task = { ...body, id: 'task-1', assetnum: String(body?.assetnum ?? ''), status: 'planned', feedback_result: null, feedback_note: null }
      tasks.push(task)
      const response = respond({ status: 'success', task })
      if (options.deferredCreate) return new Promise<Response>((resolve) => { resolveCreate = resolve }).then(() => response)
      return Promise.resolve(response)
    }
    const task = tasks[0]
    if (!task) return Promise.resolve(respond({ detail: 'not found' }, 404))
    if (method === 'GET') return Promise.resolve(respond({ status: 'success', task }))
    if (method === 'PATCH') {
      if (options.patchStatus) return Promise.resolve(respond({ detail: 'failed' }, options.patchStatus))
      Object.assign(task, body)
      return Promise.resolve(respond({ status: 'success', task }))
    }
    if (path.endsWith('/feedback') && method === 'POST') {
      if (options.feedbackStatus) return Promise.resolve(respond({ detail: 'failed' }, options.feedbackStatus))
      task.status = 'done'
      task.feedback_result = body?.result
      task.feedback_note = body?.note
      return Promise.resolve(respond({ status: 'success', task }))
    }
    return Promise.resolve(respond({ detail: 'unknown path' }, 404))
  })
  vi.stubGlobal('fetch', withLoggedInFetch(fetchMock))
  return { calls, tasks, releaseCreate: () => resolveCreate?.(respond({ status: 'success' })) }
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

function renderAt(path = '/maintenance?view=suggestions') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /><LocationProbe /></MemoryRouter></QueryClientProvider>)
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('keeps server order while filtering and preserves URL state', async () => {
  setupApi()
  renderAt()
  const list = await screen.findByRole('list', { name: '检修建议列表' })
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-Z', 'DEMO-A'])
  expect(screen.getAllByText('先看历史')).toHaveLength(2) // visible lead and the service's full reason record
  await userEvent.setup().type(screen.getByRole('searchbox', { name: '搜索设备或车站' }), '甲站')
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-A'])
  expect(screen.getByTestId('location')).toHaveTextContent(`q=${encodeURIComponent('甲站')}`)
})

test('runs suggestion to task, patch and feedback without interaction approval', async () => {
  const api = setupApi()
  const user = userEvent.setup()
  renderAt()
  await screen.findByRole('list', { name: '检修建议列表' })
  await user.click(screen.getAllByRole('button', { name: '安排检修' })[0])
  await user.click(screen.getByRole('button', { name: '确认安排检修' }))
  expect(screen.getByText(/请填写班组、计划日期/)).toBeInTheDocument()
  const form = screen.getByRole('form', { name: '核对检修安排' })
  await user.type(within(form).getByLabelText('计划日期'), '2026-11-03')
  await user.clear(within(form).getByLabelText(/优先级/))
  await user.type(within(form).getByLabelText(/优先级/), '4')
  await user.click(within(form).getByRole('button', { name: '确认安排检修' }))
  expect(await screen.findByRole('heading', { name: '调整计划' })).toBeInTheDocument()
  const created = api.calls.find((call) => call.method === 'POST' && call.path.endsWith('/maintenance/tasks'))
  expect(created?.body).toMatchObject({ assetnum: 'DEMO-Z', assignee_crew_id: 'CREW-A', planned_date: '2026-11-03', priority: 4, suggestion_reasons: ['先看历史', '模拟班组可用'] })
  expect(api.calls.filter((call) => call.method !== 'GET').every((call) => call.path.startsWith('/usecases/maintenance/'))).toBe(true)

  const editor = screen.getByRole('form', { name: '调整计划' })
  expect(within(editor).getByLabelText('任务状态').querySelector('option[value="done"]')).toBeNull()
  expect(within(editor).getByText('提交现场执行反馈后，任务会自动标记为已完成。')).toBeInTheDocument()
  await user.selectOptions(within(editor).getByLabelText('任务状态'), 'in_progress')
  await user.click(within(editor).getByRole('button', { name: '保存任务调整' }))
  await waitFor(() => expect(within(screen.getByText('状态').parentElement!).getByText('执行中')).toBeInTheDocument())

  const feedback = screen.getByRole('form', { name: '执行反馈' })
  await user.click(within(feedback).getByRole('button', { name: '提交执行反馈' }))
  expect(screen.getByText('请填写现场执行结果。')).toBeInTheDocument()
  await user.type(within(feedback).getByLabelText(/现场结果/), '现场已处理')
  await user.click(within(feedback).getByRole('button', { name: '提交执行反馈' }))
  expect(await screen.findByText('已提交的执行反馈')).toBeInTheDocument()
  expect(screen.getByText('现场已处理')).toBeInTheDocument()
  expect(within(screen.getByText('状态').parentElement!).getByText('已完成')).toBeInTheDocument()
  expect(api.calls.some((call) => call.path.includes('/interaction/approve'))).toBe(false)
})

test('disables repeat create and shows 422, 404 and feedback errors', async () => {
  const api = setupApi({ deferredCreate: true, patchStatus: 404, feedbackStatus: 422 })
  const user = userEvent.setup()
  renderAt()
  await screen.findByRole('list', { name: '检修建议列表' })
  await user.click(screen.getAllByRole('button', { name: '安排检修' })[0])
  const form = screen.getByRole('form', { name: '核对检修安排' })
  await user.type(within(form).getByLabelText('计划日期'), '2026-11-03')
  await user.click(within(form).getByRole('button', { name: '确认安排检修' }))
  expect(within(form).getByRole('button', { name: '正在安排…' })).toBeDisabled()
  expect(api.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/maintenance/tasks'))).toHaveLength(1)
  api.releaseCreate()
  const editor = await screen.findByRole('form', { name: '调整计划' })
  await user.click(within(editor).getByRole('button', { name: '保存任务调整' }))
  expect(await screen.findByText(/任务未找到/)).toBeInTheDocument()
  const feedback = screen.getByRole('form', { name: '执行反馈' })
  await user.type(within(feedback).getByLabelText(/现场结果/), '已检查')
  await user.click(within(feedback).getByRole('button', { name: '提交执行反馈' }))
  expect(await screen.findByText(/提交内容未通过校验/)).toBeInTheDocument()
})

test('explains a task transition conflict with the feedback next step', async () => {
  setupApi({ patchStatus: 409 })
  const user = userEvent.setup()
  renderAt()
  await screen.findByRole('list', { name: '检修建议列表' })
  await user.click(screen.getAllByRole('button', { name: '安排检修' })[0])
  const arrange = screen.getByRole('form', { name: '核对检修安排' })
  await user.type(within(arrange).getByLabelText('计划日期'), '2026-11-03')
  await user.click(within(arrange).getByRole('button', { name: '确认安排检修' }))
  const editor = await screen.findByRole('form', { name: '调整计划' })
  await user.click(within(editor).getByRole('button', { name: '保存任务调整' }))
  expect(await within(editor).findByText('任务状态已变化。请先核对并提交现场执行反馈，再刷新任务详情。')).toBeInTheDocument()
})

test('filters task status without changing server order', async () => {
  const api = setupApi()
  api.tasks.push(
    { id: 'task-z', assetnum: 'DEMO-Z', status: 'done', planned_date: '2026-11-03' },
    { id: 'task-a', assetnum: 'DEMO-A', status: 'planned', planned_date: '2026-11-04' },
    { id: 'task-x', assetnum: 'DEMO-X', status: 'done', planned_date: '2026-11-05' },
  )
  renderAt('/maintenance?view=tasks')
  const list = await screen.findByRole('list', { name: '检修任务列表' })
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-Z', 'DEMO-A', 'DEMO-X'])
  expect(within(list).getByText('任务 task-z')).toBeInTheDocument()
  expect(within(list).getByRole('link', { name: '调整计划' })).toHaveAttribute('href', '/maintenance/tasks/task-a#task-plan')
  await userEvent.setup().click(screen.getByRole('button', { name: '已完成 2' }))
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-Z', 'DEMO-X'])
  expect(screen.getByTestId('location')).toHaveTextContent('status=done')
  await userEvent.setup().type(screen.getByRole('searchbox', { name: '搜索任务或设备' }), 'DEMO-X')
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-X'])
})

test('keeps the arrange form and user inputs when server rejects creation', async () => {
  setupApi({ createStatus: 422 })
  const user = userEvent.setup()
  renderAt()
  await screen.findByRole('list', { name: '检修建议列表' })
  await user.click(screen.getAllByRole('button', { name: '安排检修' })[0])
  const form = screen.getByRole('form', { name: '核对检修安排' })
  await user.type(within(form).getByLabelText('计划日期'), '2026-11-03')
  await user.click(within(form).getByRole('button', { name: '确认安排检修' }))
  expect(await within(form).findByText(/提交内容未通过校验/)).toBeInTheDocument()
  expect(within(form).getByLabelText('计划日期')).toHaveValue('2026-11-03')
  expect(screen.getByTestId('location')).toHaveTextContent('/maintenance?view=suggestions')
})
