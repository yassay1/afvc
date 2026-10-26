import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const suggestions = { status: 'success', message: 'ok', prediction_tier: 'statistical_baseline', model_note: '统计基线', suggestions: [{ assetnum: 'DEMO-AGM-001', station_name: '样例站', fault_focus: '暂停服务', warning_level: '高', reasons: ['工单频次较高'], data_note: '资源为模拟数据', score: 1, suggested_crew_id: 'CREW-A' }] }
const tasks = { status: 'success', message: 'ok', tasks: [], count: 0 }
const devices = { status: 'success', message: 'ok', device_count: 1, devices: [{ assetnum: 'DEMO-AGM-001', station_name: '样例站', line: '1号线', brand: '样例品牌', workorder_count: 2, last_record_time: '2026-01-01' }] }
const diagnosis = { status: 'success', message: 'ok', assetnum: 'DEMO-AGM-001', analysis_statement: '工单复发风险不是物理故障日期。', device_profile: { assetnum: 'DEMO-AGM-001', station_name: '样例站', line: '1号线', brand: '样例品牌', subsystem: '闸门', history_workorder_count: 2, last_record_time: '2026-01-01' }, history_summary: { returned_history_count: 1, recent_descriptions: ['闸门卡阻'], top_fault_descriptions: [] }, risk_prediction: { risk_30d: 0.2, risk_90d: 0.4, warning_level: '中', warning_reason: '工单频次', suggested_inspection_window: null, main_risk_factors: [] }, maintenance_advice: { inspection_suggestions: ['检查闸门'], spare_part_suggestions: [], recognized_fault_phenomena: [] }, fault_prediction: { status: 'unavailable', message: '样本不足', prediction_window_days: 90, most_likely_fault: null } }

test.beforeEach(async ({ page }) => {
  await page.route('**/usecases/**', async (route) => {
    const url = route.request().url()
    const payload = url.includes('/maintenance/suggestions') ? suggestions
      : url.includes('/maintenance/tasks') ? tasks
        : url.includes('/devices/') && url.includes('/diagnosis') ? diagnosis
          : url.includes('/devices') ? devices
            : url.includes('/overview') ? { status: 'success', message: 'ok', data_backend: 'file', basic_metrics: { workorder_count: 2, column_count: 8, device_count: 1, station_count: 1, line_count: 1, brand_count: 1 }, time_range: { start_time: '2026-01-01', end_time: '2026-01-02', note: '工单记录时间' }, brand_distribution: [], line_distribution: [], fault_description_top: [], field_note: { description: '故障现象', current_faildate: '记录时间' } }
              : { status: 'success', message: 'ok', devices: [{ assetnum: 'DEMO-AGM-001', station_name: '样例站', line: '1号线', brand: '样例品牌', risk_30d: 0.2, risk_90d: 0.4, warning_level: '中', main_risk_factors: [] }], model_note: '统计基线', prediction_tier: 'statistical_baseline' }
    await route.fulfill({ json: payload })
  })
  await page.route('**/interaction/sessions/*/pending', async (route) => route.fulfill({ json: { session_id: 'smoke', pending_actions: [] } }))
})

for (const [width, height] of [[375, 812], [390, 844], [768, 1024], [1024, 768], [844, 390]] as const) {
  test(`main routes and bottom navigation fit ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/workbench')
    await expect(page.getByRole('heading', { name: '设备检修助手' })).toBeVisible()
    if (width === 390) { await page.waitForLoadState('networkidle'); await page.screenshot({ path: 'test-results/visual-workbench.png', fullPage: true }) }
    const nav = page.getByRole('navigation', { name: '主导航' })
    await expect(nav.getByRole('link')).toHaveText(['工作台', 'AI 助手', '检修', '设备'])
    for (const route of ['/assistant', '/maintenance?view=suggestions', '/devices', '/devices/DEMO-AGM-001', '/data?view=overview', '/data?view=risk']) {
      await page.goto(route)
      await expect(nav).toBeVisible()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      expect(overflow, `horizontal overflow at ${route} on ${width}x${height}`).toBeLessThanOrEqual(1)
      if (width === 390) {
        await page.waitForLoadState('networkidle')
        const name = route.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')
        await page.screenshot({ path: `test-results/visual-${name}.png`, fullPage: true })
      }
    }
  })
}

test('device to assistant and maintenance links retain assetnum across navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/devices/DEMO-AGM-001')
  await page.locator('a[href="/assistant?assetnum=DEMO-AGM-001"]').click()
  await expect(page).toHaveURL(/\/assistant\?assetnum=DEMO-AGM-001/)
  await expect(page.getByText('当前设备：')).toBeVisible()
  await page.getByRole('link', { name: '查看相关建议' }).click()
  await expect(page).toHaveURL(/\/maintenance\?view=suggestions&q=DEMO-AGM-001/)
  await expect(page.getByText('工单频次较高')).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/\/assistant\?assetnum=DEMO-AGM-001/)
})

test('main pages meet automated WCAG A and AA checks', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const route of ['/workbench', '/assistant', '/maintenance?view=suggestions', '/devices', '/devices/DEMO-AGM-001', '/data?view=risk']) {
    await page.goto(route)
    await page.waitForLoadState('networkidle')
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
    expect(results.violations, `${route}: ${results.violations.map((issue) => `${issue.id} ${issue.nodes.map((node) => node.target.join(' ')).join(', ')}`).join('; ')}`).toEqual([])
  }
})

test('keyboard focus and bottom navigation targets are usable on a phone viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/workbench')
  await page.keyboard.press('Tab')
  const focused = await page.evaluate(() => ({ href: (document.activeElement as HTMLAnchorElement)?.getAttribute('href'), outline: getComputedStyle(document.activeElement as Element).outlineStyle }))
  expect(focused.href).toBe('/assistant')
  expect(focused.outline).toBe('solid')
  const targets = await page.getByRole('navigation', { name: '主导航' }).getByRole('link').evaluateAll((links) => links.map((link) => ({ width: link.getBoundingClientRect().width, height: link.getBoundingClientRect().height })))
  expect(targets.every((size) => size.width >= 44 && size.height >= 44)).toBe(true)
})
