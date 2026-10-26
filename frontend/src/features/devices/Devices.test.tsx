import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../../app/App'
import { withLoggedInFetch } from '../../test/authFetch'

const devices = {
  status: 'success', message: '设备列表获取成功', device_count: 3,
  devices: [
    { assetnum: 'DEMO-Z', station_name: '乙站', line: 'L02', brand: '乙牌', workorder_count: 7, last_record_time: null },
    { assetnum: 'DEMO-A', station_name: '甲站', line: 'L01', brand: '甲牌', workorder_count: 2, last_record_time: null },
    { assetnum: 'DEMO-X', station_name: '丙站', line: 'L02', brand: '甲牌', workorder_count: 4, last_record_time: null },
  ],
}

const diagnosis = {
  status: 'success', message: '完成', assetnum: 'DEMO-Z',
  device_profile: { assetnum: 'DEMO-Z', station_name: '乙站', line: 'L02', brand: '乙牌', subsystem: 'AFCAGM', history_workorder_count: 7, last_record_time: '2026-10-01' },
  history_summary: { returned_history_count: 2, recent_descriptions: ['合成工单：扇门卡滞；现场复位并记录模拟观察值'], top_fault_descriptions: [] },
  risk_prediction: { risk_30d: null, risk_90d: 0.7, warning_level: '关注', warning_reason: '复发频次较高', suggested_inspection_window: null, main_risk_factors: ['历史工单较多'] },
  maintenance_advice: { recognized_fault_phenomena: ['扇门异常'], inspection_suggestions: ['检查扇门'], spare_part_suggestions: [] },
  fault_prediction: { status: 'unavailable', message: '没有故障类型模型结果', prediction_window_days: 30, most_likely_fault: null },
  analysis_statement: '未来工单复发风险不等于物理故障日期。',
}

function mockApi({ detailStatus = 200, detail = diagnosis }: { detailStatus?: number; detail?: unknown } = {}) {
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/usecases/devices')) return new Response(JSON.stringify(devices), { status: 200 })
    if (path.includes('/usecases/high-risk')) return new Response(JSON.stringify({ status: 'success', devices: [
      { assetnum: 'DEMO-X', warning_level: '橙色预警' },
      { assetnum: 'DEMO-Z', warning_level: '黄色预警' },
    ] }), { status: 200 })
    if (path.includes('/diagnosis')) return new Response(JSON.stringify(detailStatus === 200 ? detail : { detail: 'not found' }), { status: detailStatus })
    return new Response(JSON.stringify({ status: 'success', tasks: [], count: 0 }), { status: 200 })
  })))
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>)
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('searches only real list fields and preserves API order', async () => {
  mockApi()
  const user = userEvent.setup()
  renderAt('/devices')
  const list = await screen.findByRole('list', { name: '设备列表' })
  expect(within(list).getAllByRole('link').map((link) => link.textContent?.match(/DEMO-[A-Z]/)?.[0])).toEqual(['DEMO-Z', 'DEMO-A', 'DEMO-X'])
  await user.click(screen.getByRole('button', { name: '筛选线路和品牌' }))
  await user.selectOptions(screen.getByLabelText('线路'), 'L02')
  expect(within(list).getAllByRole('link').map((link) => link.textContent?.match(/DEMO-[A-Z]/)?.[0])).toEqual(['DEMO-Z', 'DEMO-X'])
  await user.type(screen.getByRole('searchbox', { name: '搜索设备、车站、线路或品牌' }), '丙站')
  expect(within(list).getAllByRole('link')).toHaveLength(1)
  expect(within(list).getByText('DEMO-X')).toBeInTheDocument()
})

test('demo device label is consistent with raw identifier links and production keeps the identifier', async () => {
  const targetDevice = { assetnum: 'DEMO-AGM-018', station_name: '月港', line: 'L1', brand: null, workorder_count: 0, last_record_time: null }
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/health')) return new Response(JSON.stringify({ status: 'ok', data_profile: 'demo' }), { status: 200 })
    if (path.endsWith('/usecases/devices')) return new Response(JSON.stringify({ status: 'success', message: '', device_count: 1, devices: [targetDevice] }), { status: 200 })
    return new Response(JSON.stringify({ status: 'success', tasks: [], count: 0 }), { status: 200 })
  })))
  renderAt('/devices')
  const demoName = await screen.findByText('月港站闸机 03')
  expect(demoName).toBeInTheDocument()
  expect(screen.getByText('设备编号 DEMO-AGM-018')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /月港站闸机 03/ })).toHaveAttribute('href', '/devices/DEMO-AGM-018')
  cleanup()
  vi.stubGlobal('fetch', vi.fn(withLoggedInFetch(async (input: RequestInfo | URL) => {
    const path = String(input)
    if (path.endsWith('/health')) return new Response(JSON.stringify({ status: 'ok', data_profile: 'production' }), { status: 200 })
    if (path.endsWith('/usecases/devices')) return new Response(JSON.stringify({ status: 'success', message: '', device_count: 1, devices: [targetDevice] }), { status: 200 })
    return new Response(JSON.stringify({ status: 'success', tasks: [], count: 0 }), { status: 200 })
  })))
  renderAt('/devices')
  const list = await screen.findByRole('list', { name: '设备列表' })
  expect(within(list).getByText('设备编号 DEMO-AGM-018')).toBeInTheDocument()
  expect(within(list).queryByText('月港站闸机 03')).not.toBeInTheDocument()
  expect(list.querySelector('img')).toBeNull()
})

test('risk focus uses server order and keeps device detail links', async () => {
  mockApi()
  renderAt('/devices?view=attention')
  expect(await screen.findByRole('button', { name: '高风险设备' })).toHaveAttribute('aria-pressed', 'true')
  const list = await screen.findByRole('list', { name: '设备列表' })
  expect(within(list).getAllByRole('link').map((link) => link.textContent?.match(/DEMO-[A-Z]/)?.[0])).toEqual(['DEMO-X', 'DEMO-Z'])
  expect(within(list).getByText('橙色预警')).toHaveClass('warning-level--orange')
  expect(within(list).getByText('黄色预警')).toHaveClass('warning-level--yellow')
  expect(within(list).getByRole('link', { name: /DEMO-X/ })).toHaveAttribute('href', '/devices/DEMO-X')
})

test('shows diagnosis sections, unavailable fault prediction and device links', async () => {
  mockApi()
  renderAt('/devices/DEMO-Z')
  expect(await screen.findByRole('heading', { name: /DEMO-Z/ })).toBeInTheDocument()
  expect(screen.getByText(/乙站/)).toBeInTheDocument()
  expect(screen.getByText('检查扇门')).toBeInTheDocument()
  expect(screen.getByText('扇门卡滞')).toBeInTheDocument()
  expect(screen.getByText(/故障类型预测暂不可用/)).toBeInTheDocument()
  expect(screen.getByText(/暂无数据/)).toBeInTheDocument()
  expect(screen.getByText(/不等同于实际故障发生时间/)).toBeInTheDocument()
  expect(screen.queryByText(/合成工单|模拟观察值/)).not.toBeInTheDocument()
  const actions = screen.getByRole('navigation', { name: '设备后续操作' })
  expect(within(actions).getByRole('link', { name: '查看检修建议' })).toHaveAttribute('href', '/maintenance?view=suggestions&q=DEMO-Z')
  expect(within(actions).getByRole('link', { name: '相关任务' })).toHaveAttribute('href', '/maintenance?view=tasks&assetnum=DEMO-Z')
  expect(within(actions).getByRole('link', { name: 'AI 助手' })).toHaveAttribute('href', '/assistant?assetnum=DEMO-Z')
})

test('handles a missing device and missing diagnosis sections', async () => {
  mockApi({ detailStatus: 404 })
  renderAt('/devices/UNKNOWN')
  expect(await screen.findByText('设备详情读取失败')).toBeInTheDocument()
  cleanup()
  vi.unstubAllGlobals()
  mockApi({ detail: { status: 'success', assetnum: 'DEMO-Z', analysis_statement: '风险说明' } })
  renderAt('/devices/DEMO-Z')
  expect(await screen.findByRole('heading', { name: '风险评估' })).toBeInTheDocument()
  expect(screen.getByText('当前没有可用的设备风险结果。')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '历史故障' })).toBeInTheDocument()
})
