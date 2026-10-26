import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { Workbench } from './Workbench'

const suggestions = {
  status: 'success', message: '建议已生成', ranking_method: 'deterministic_weighted_rules',
  prediction_tier: 'statistical_baseline', model_note: '风险来自统计基线',
  suggestions: [
    { assetnum: 'DEMO-Z', station_name: '乙站', fault_focus: '暂停服务', warning_level: '关注', reasons: ['第一条理由', '第二条理由', '第三条理由'], data_note: '资源为模拟数据', score: 0.2 },
    { assetnum: 'DEMO-A', station_name: '甲站', fault_focus: '暂停服务', warning_level: null, reasons: ['另一个理由'], data_note: null, score: 0.9 },
    { assetnum: 'DEMO-X', station_name: '丙站', fault_focus: '暂停服务', warning_level: null, reasons: ['末位理由'], data_note: null, score: 0.5 },
  ],
}

const tasks = {
  status: 'success', message: '任务列表', count: 3,
  tasks: [
    { id: '1', status: 'planned', assetnum: 'DEMO-A' },
    { id: '2', status: 'in_progress', assetnum: 'DEMO-Z' },
    { id: '3', status: 'done', assetnum: 'DEMO-X' },
  ],
}

function mockResponses(suggestionResponse: unknown = suggestions, taskResponse: unknown = tasks) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => new Response(
    JSON.stringify(String(input).includes('/suggestions') ? suggestionResponse : taskResponse),
    { status: 200 },
  ))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderWorkbench() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><Workbench /></MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('shows service order, preview reasons, task counts and exact deep links', async () => {
  const fetchMock = mockResponses()
  renderWorkbench()
  expect(screen.getByRole('heading', { name: '检修工作台' })).toBeInTheDocument()
  expect(screen.queryByText('今日检修建议')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '哪些设备建议优先检修？' })).toBeInTheDocument()
  const list = await screen.findByRole('list', { name: '建议摘要' })
  expect(screen.getByText('左右滑动查看更多建议')).toBeInTheDocument()
  expect(Array.from(list.querySelectorAll('.device-identity__number')).map((node) => node.textContent?.replace('设备编号 ', ''))).toEqual(['DEMO-Z', 'DEMO-A', 'DEMO-X'])
  expect(screen.getByText('第一条理由')).toBeInTheDocument()
  expect(screen.queryByText('第三条理由')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: '查看 DEMO-Z 的全部建议' })).toHaveAttribute('href', '/maintenance?view=suggestions&q=DEMO-Z')
  expect(screen.getByRole('link', { name: /查看全部建议/ })).toHaveAttribute('href', '/maintenance?view=suggestions')
  expect(screen.getByRole('link', { name: /查看全部任务/ })).toHaveAttribute('href', '/maintenance?view=tasks')
  expect(screen.getByRole('link', { name: /AI 助手/ })).toHaveAttribute('href', '/assistant')
  expect(await screen.findByRole('link', { name: /查看全部任务/ })).toHaveTextContent('共 3 项')
  expect(screen.getByText('执行中').previousSibling).toHaveTextContent('1')
  expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain('/usecases/maintenance/suggestions?top_n=10')
})

test('hides the swipe hint when only one suggestion is shown', async () => {
  mockResponses({ ...suggestions, suggestions: [suggestions.suggestions[0]] })
  renderWorkbench()
  await screen.findByRole('list', { name: '建议摘要' })
  expect(screen.queryByText('左右滑动查看更多建议')).not.toBeInTheDocument()
})

test('shows loading, empty and unavailable states separately', async () => {
  let resolveFetch!: (value: Response) => void
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    if (String(input).includes('/suggestions')) return new Promise<Response>((resolve) => { resolveFetch = resolve })
    return Promise.resolve(new Response(JSON.stringify({ ...tasks, count: 0, tasks: [] }), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  renderWorkbench()
  expect(screen.getByText('正在读取检修建议')).toBeInTheDocument()
  expect(await screen.findByText('暂无检修任务')).toBeInTheDocument()
  resolveFetch(new Response(JSON.stringify({ ...suggestions, status: 'unavailable', suggestions: [], model_note: '预测输入暂不可用' }), { status: 200 }))
  expect(await screen.findByText('检修建议暂不可用')).toBeInTheDocument()
  expect(screen.queryByText('暂无检修建议')).not.toBeInTheDocument()
})

test('shows read failure and lets the user retry', async () => {
  let attempts = 0
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (!String(input).includes('/suggestions')) return new Response(JSON.stringify(tasks), { status: 200 })
    attempts += 1
    return attempts === 1
      ? new Response(JSON.stringify({ detail: '暂时失败' }), { status: 500 })
      : new Response(JSON.stringify({ ...suggestions, suggestions: [] }), { status: 200 })
  }))
  renderWorkbench()
  expect(await screen.findByText('检修建议读取失败')).toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: '重试' }))
  await waitFor(() => expect(screen.getByText('暂无检修建议')).toBeInTheDocument())
  expect(attempts).toBe(2)
})
