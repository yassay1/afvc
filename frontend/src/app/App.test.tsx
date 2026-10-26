import { cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { App } from './App'
import { withLoggedInFetch } from '../test/authFetch'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    const payload = path.endsWith('/health')
      ? { status: 'ok', data_profile: 'demo' }
      : path.includes('/suggestions')
      ? { status: 'success', suggestions: [], prediction_tier: 'statistical_baseline' }
      : path.includes('/diagnosis')
        ? { status: 'success', assetnum: 'DEMO-AGM-001', analysis_statement: '工单复发风险说明' }
        : { status: 'success', tasks: [], count: 0 }
    return new Response(JSON.stringify(payload), { status: 200 })
  })))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function LocationProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(-1)}>返回 {location.pathname}{location.search}</button>
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('fixed navigation has four entries in the required order', async () => {
  renderAt('/workbench')
  const nav = await screen.findByRole('navigation', { name: '主导航' })
  expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual(['工作台', 'AI 助手', '检修', '设备'])
  expect(within(nav).getByRole('link', { name: '工作台' })).toHaveAttribute('aria-current', 'page')
})

test('experience notice is driven by backend health', async () => {
  renderAt('/workbench')
  const notice = await screen.findByRole('status', { name: /体验环境说明/ })
  expect(notice).toHaveTextContent('设备、检修任务与风险数据为演示内容')
  expect(notice).toHaveTextContent('设备配图为生成素材，并非现场实拍')
})

test('production pages do not show demo data notices', async () => {
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async () =>
    new Response(JSON.stringify({ status: 'ok', data_profile: 'production' }), { status: 200 }),
  )))
  renderAt('/assistant')
  await screen.findByRole('heading', { name: '有什么可以帮您？' })
  expect(screen.getByRole('heading', { name: 'AI 助手' })).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: /体验环境说明/ })).not.toBeInTheDocument()
})

test('maintenance deep link, tab switch and browser back retain the view', async () => {
  const user = userEvent.setup()
  renderAt('/maintenance?view=tasks')
  expect(await screen.findByRole('button', { name: '任务跟进' })).toHaveAttribute('aria-pressed', 'true')
  await user.click(screen.getByRole('button', { name: '检修建议' }))
  expect(screen.getByRole('button', { name: '检修建议' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: /返回 \/maintenance\?view=suggestions/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /返回 \/maintenance\?view=suggestions/ }))
  expect(screen.getByRole('button', { name: '任务跟进' })).toHaveAttribute('aria-pressed', 'true')
})

test('device detail is directly addressable and keeps devices selected', async () => {
  renderAt('/devices/DEMO-AGM-001')
  expect(await screen.findByRole('heading', { name: /设备编号 DEMO-AGM-001/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '设备' })).toHaveAttribute('aria-current', 'page')
})
