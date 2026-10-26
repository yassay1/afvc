import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { DataManagementPage } from './DataManagementPage'

function json(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status }) }
function renderPage(path = '/data') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><DataManagementPage /></MemoryRouter></QueryClientProvider>)
}
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('shows overview metrics from API and leaves server file path off page', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => json({
    status: 'success', message: 'ok', data_backend: 'file', current_file: 'private.xlsx', file_path: 'C:\\secret\\private.xlsx',
    basic_metrics: { workorder_count: 8, column_count: 10, device_count: 3, station_count: 2, line_count: 1, brand_count: 2 },
    time_range: { start_time: '2025-01-01', end_time: '2025-03-01', note: '工单记录时间' },
    brand_distribution: [{ name: '甲品牌', count: 5 }], line_distribution: [{ name: '1号线', count: 8 }], fault_description_top: [{ name: '闸门故障', count: 4 }], field_note: { description: '故障现象仅供参考', current_faildate: '工单记录时间' },
  })))
  renderPage()
  expect(screen.getByText('正在读取数据概览')).toBeInTheDocument()
  expect(await screen.findByText('工单记录时间')).toBeInTheDocument()
  expect(screen.getByText('甲品牌')).toBeInTheDocument()
  expect(screen.getByText('闸门故障')).toBeInTheDocument()
  expect(document.body).not.toHaveTextContent('C:\\secret')
  expect(document.body).not.toHaveTextContent('private.xlsx')
})

test('high risk view preserves server order, shows a friendly source label and unavailable values', async () => {
  const user = userEvent.setup()
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => String(input).includes('high-risk')
    ? json({ status: 'success', message: 'ok', prediction_source: 'statistical_baseline', prediction_tier: 'statistical_baseline', model_note: '统计基线排序', devices: [
      { assetnum: 'B', station_name: '乙站', line: '2号线', brand: null, risk_30d: null, risk_90d: 0.8, warning_level: '高', main_risk_factors: ['频次高'] },
      { assetnum: 'A', station_name: '甲站', line: '1号线', brand: null, risk_30d: 0, risk_90d: 0.1, warning_level: '低', main_risk_factors: [] },
    ] })
    : json({ status: 'success', basic_metrics: { workorder_count: 0 } }))
  vi.stubGlobal('fetch', fetchMock)
  renderPage('/data?view=risk')
  const list = await screen.findByRole('list', { name: '高风险设备排序' })
  expect(Array.from(list.querySelectorAll('.device-identity__name')).map((node) => node.textContent)).toEqual(['B', 'A'])
  expect(screen.getByText(/历史工单统计估算/)).toBeInTheDocument()
  expect(screen.getByText('不可用')).toBeInTheDocument()
  expect(screen.getByText('0%')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '数据概览' }))
  expect(await screen.findByText('暂无工单记录')).toBeInTheDocument()
})

test('demo risk list uses the shared display name and keeps its identifier link', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).endsWith('/health')) return json({ status: 'ok', data_profile: 'demo' })
    if (String(input).includes('high-risk')) return json({ status: 'success', message: 'ok', prediction_tier: 'model', devices: [
      { assetnum: 'DEMO-AGM-018', station_name: '月港站', line: 'D02', brand: null, risk_30d: null, risk_90d: 0.6, warning_level: '关注', main_risk_factors: [] },
    ] })
    return json({ status: 'success', basic_metrics: { workorder_count: 0 } })
  }))
  renderPage('/data?view=risk')
  const list = await screen.findByRole('list', { name: '高风险设备排序' })
  expect(within(list).getByText('月港站闸机 03')).toBeInTheDocument()
  expect(within(list).getByText('设备编号 DEMO-AGM-018')).toBeInTheDocument()
  expect(within(list).getByRole('link', { name: /月港站闸机 03/ })).toHaveAttribute('href', '/devices/DEMO-AGM-018')
})

test('read-only pages show API failure and empty risk list', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => String(input).includes('overview') ? json({ detail: 'failed' }, 500) : json({ status: 'success', message: 'ok', devices: [], model_note: '统计基线' })))
  const view = renderPage('/data?view=overview')
  expect(await screen.findByText('数据概览读取失败')).toBeInTheDocument()
  view.unmount()
  renderPage('/data?view=risk')
  expect(await screen.findByText('暂无风险设备')).toBeInTheDocument()
})
