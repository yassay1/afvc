import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { withLoggedInFetch } from '../../test/authFetch'
import { AssistantPage } from './AssistantPage'

function json(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status }) }
function response(sessionId: string, overrides: Record<string, unknown> = {}) {
  return { status: 'success', use_case: null, assetnum: null, final_answer: '已答复', session_id: sessionId, last_assetnum: null, result: null, pending_actions: [], ...overrides }
}
function renderPage(path = '/assistant') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AssistantPage /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => sessionStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('workbench quick question sends once in the existing assistant session', async () => {
  let turns = 0
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path.includes('/pending')) return json({ session_id: 's-quick', pending_actions: [] })
    if (path.endsWith('/turn')) {
      turns += 1
      expect(JSON.parse(String(init?.body)).query).toBe('查询检修建议')
      return json(response('s-quick', { final_answer: '检修建议已找到' }))
    }
    throw new Error(path)
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-quick', exchanges: [] }))
  renderPage('/assistant?question=%E6%9F%A5%E8%AF%A2%E6%A3%80%E4%BF%AE%E5%BB%BA%E8%AE%AE&send=1')
  expect(await screen.findByText('检修建议已找到')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'AI 助手' })).toBeInTheDocument()
  expect(screen.getByText('在线')).toBeInTheDocument()
  expect(document.querySelector('.assistant-answer__label')).toHaveTextContent('AI 助手')
  expect(document.querySelector('.assistant-answer__label')).toHaveTextContent('已回复')
  expect(turns).toBe(1)
})

test('current device context shows demo name and keeps the raw ID in the link', async () => {
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    if (String(input).endsWith('/health')) return json({ status: 'ok', data_profile: 'demo' })
    if (String(input).includes('/pending')) return json({ session_id: 's-context', pending_actions: [] })
    throw new Error(String(input))
  })))
  renderPage('/assistant?assetnum=DEMO-AGM-018')
  expect(await screen.findByText('月港站闸机 03')).toBeInTheDocument()
  expect(screen.getByText('设备编号 DEMO-AGM-018')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /月港站闸机 03/ })).toHaveAttribute('href', '/devices/DEMO-AGM-018')
})

test('failed assistant response is labeled clearly and can be retried', async () => {
  const user = userEvent.setup()
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/health')) return json({ status: 'ok', data_profile: 'demo' })
    if (path.includes('/pending')) return json({ session_id: 's-error', pending_actions: [] })
    if (path.endsWith('/turn')) {
      calls += 1
      return json(response('s-error', calls === 1
        ? { status: 'error', final_answer: '处理失败：设备不存在' }
        : { status: 'success', final_answer: '查询完成' }))
    }
    throw new Error(path)
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-error', exchanges: [] }))
  renderPage()
  await user.type(screen.getByRole('textbox', { name: '输入问题' }), '分析设备 DEMO-AGM-019 的风险')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByText('处理失败：设备不存在')).toBeInTheDocument()
  expect(document.querySelector('.assistant-answer__label')).toHaveTextContent('查询失败')
  expect(screen.getByText('本次查询未完成。请检查设备编号，或重试本问题。')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '重试本问题' }))
  expect(await screen.findByText('查询完成')).toBeInTheDocument()
  expect(calls).toBe(2)
})

test('clarification, response, fallback and tab transcript restoration', async () => {
  const user = userEvent.setup()
  let turn = 0
  const fetchMock = vi.fn(withLoggedInFetch(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path.includes('/pending')) return json({ session_id: 's-1', pending_actions: [] })
    if (path.endsWith('/turn')) {
      const body = JSON.parse(String(init?.body)) as { session_id: string }
      expect(body.session_id).toBe('s-1')
      turn += 1
      return json(response('s-1', turn === 1
        ? { status: 'clarified', final_answer: '请补充设备编号' }
        : { final_answer: '设备已分析', assetnum: 'DEMO-1', result: { source: 'legacy_fallback', degraded: 'llm_unavailable', device_profile: { assetnum: 'DEMO-1' }, risk_prediction: { risk_30d: null } } }))
    }
    throw new Error(path)
  }))
  vi.stubGlobal('fetch', fetchMock)
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-1', exchanges: [] }))
  const view = renderPage()
  await user.type(screen.getByRole('textbox', { name: '输入问题' }), '分析设备')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByText('请补充设备编号')).toBeInTheDocument()
  await user.type(screen.getByRole('textbox', { name: '输入问题' }), 'DEMO-1')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByText('智能分析服务暂不可用，以下为基础查询结果。')).toBeInTheDocument()
  expect(screen.getByText('未来 30 日工单复发风险：不可用')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '查看设备详情' })).toHaveAttribute('href', '/devices/DEMO-1')
  view.unmount()
  renderPage()
  expect(screen.getByText('请补充设备编号')).toBeInTheDocument()
  expect(screen.getByText('设备已分析')).toBeInTheDocument()
  expect(turn).toBe(2)
})

test('pending approval and rejection use explicit ids and block new session until resolved', async () => {
  const user = userEvent.setup()
  const actions = [{ action_id: 'a-1', thread_id: 's-2', tool_name: 'insert_workorder', status: 'pending', summary: '插入工单 DEMO-1', payload: {}, executed: false }]
  const writes: { path: string; body: { session_id: string; action_id: string } }[] = []
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path.includes('/pending')) return json({ session_id: 's-2', pending_actions: actions })
    if (path.endsWith('/approve') || path.endsWith('/reject')) {
      writes.push({ path, body: JSON.parse(String(init?.body)) })
      actions.pop()
      return json(response('s-2', { final_answer: path.endsWith('/approve') ? '已批准并执行' : '已拒绝' }))
    }
    throw new Error(path)
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-2', exchanges: [] }))
  renderPage()
  expect(await screen.findByText('插入工单 DEMO-1')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '新会话' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '批准并执行：插入工单 DEMO-1' }))
  expect(await screen.findByText('已批准并执行')).toBeInTheDocument()
  expect(writes).toEqual([{ path: '/interaction/approve', body: { session_id: 's-2', action_id: 'a-1' } }])
  expect(screen.getByRole('button', { name: '新会话' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '新会话' }))
  expect(screen.queryByText('已批准并执行')).not.toBeInTheDocument()
})

test('running conflict and approval conflict show actionable errors without duplicate writes', async () => {
  const user = userEvent.setup()
  let turns = 0
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.includes('/pending')) return json({ session_id: 's-3', pending_actions: [{ action_id: 'a-3', thread_id: 's-3', tool_name: 'delete_workorder', status: 'pending', summary: '删除工单', payload: {}, executed: false }] })
    if (path.endsWith('/turn')) { turns += 1; return json({ detail: { code: 'run_in_progress' } }, 409) }
    if (path.endsWith('/reject')) return json({ detail: { code: 'action_conflict' } }, 409)
    throw new Error(path)
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-3', exchanges: [] }))
  renderPage()
  await screen.findByText('删除工单')
  await user.type(screen.getByRole('textbox', { name: '输入问题' }), '进度如何')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('仍有一轮对话在执行')
  expect(turns).toBe(1)
  await user.click(screen.getByRole('button', { name: '拒绝：删除工单' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('已被处理')
  expect(screen.getByRole('button', { name: '新会话' })).toBeDisabled()
})

test('reject resolves the pending item without calling approve', async () => {
  const user = userEvent.setup()
  let pending = true
  const writes: string[] = []
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/health')) return json({ status: 'ok', data_profile: 'demo' })
    if (path.includes('/pending')) return json({ session_id: 's-4', pending_actions: pending ? [{ action_id: 'a-4', thread_id: 's-4', tool_name: 'update_workorder', status: 'pending', summary: '更新工单', payload: {}, executed: false }] : [] })
    writes.push(path)
    pending = false
    return json(response('s-4', { final_answer: '已拒绝写操作，不会执行' }))
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-4', exchanges: [] }))
  renderPage()
  await screen.findByText('更新工单')
  await user.click(screen.getByRole('button', { name: '拒绝：更新工单' }))
  expect(await screen.findByText('已拒绝写操作，不会执行')).toBeInTheDocument()
  expect(writes).toEqual(['/interaction/reject'])
})

test('timeout and server error leave the draft available for retry', async () => {
  const user = userEvent.setup()
  let count = 0
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/health')) return json({ status: 'ok', data_profile: 'demo' })
    if (path.includes('/pending')) return json({ session_id: 's-5', pending_actions: [] })
    count += 1
    if (count === 1) throw new DOMException('timed out', 'TimeoutError')
    return json({ detail: 'failed' }, 500)
  })))
  sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 's-5', exchanges: [] }))
  renderPage()
  const input = screen.getByRole('textbox', { name: '输入问题' })
  await user.type(input, '设备风险')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('本轮等待超时')
  expect(input).toHaveValue('设备风险')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('服务端处理失败')
  expect(count).toBe(2)
})
