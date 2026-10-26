import { expect, test } from '@playwright/test'

test('suggestion to task adjustment and feedback remains on maintenance API', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const writes: string[] = []
  let task: Record<string, unknown> | null = null
  await page.route('**/usecases/maintenance/**', async (route) => {
    const request = route.request()
    const url = request.url()
    const method = request.method()
    if (url.includes('/suggestions')) return route.fulfill({ json: { status: 'success', message: 'ok', prediction_tier: 'statistical_baseline', model_note: '统计基线', suggestions: [{ assetnum: 'DEMO-AGM-001', station_name: '样例站', fault_focus: '暂停服务', warning_level: '高', reasons: ['工单频次较高'], data_note: '班组为模拟资源', score: 0.8, suggested_crew_id: 'CREW-A' }] } })
    if (url.endsWith('/maintenance/tasks') && method === 'GET') return route.fulfill({ json: { status: 'success', message: 'ok', tasks: task ? [task] : [], count: task ? 1 : 0 } })
    if (url.endsWith('/maintenance/tasks') && method === 'POST') {
      writes.push(url)
      task = { ...request.postDataJSON(), id: 'task-browser', status: 'planned', feedback_result: null, feedback_note: null }
      return route.fulfill({ json: { status: 'success', task } })
    }
    if (url.includes('/task-browser') && method === 'GET') return route.fulfill({ json: { status: 'success', task } })
    if (url.endsWith('/feedback') && method === 'POST') {
      writes.push(url)
      task = { ...task, ...request.postDataJSON(), status: 'done', feedback_result: request.postDataJSON().result }
      return route.fulfill({ json: { status: 'success', task } })
    }
    if (url.includes('/task-browser') && method === 'PATCH') {
      writes.push(url)
      task = { ...task, ...request.postDataJSON() }
      return route.fulfill({ json: { status: 'success', task } })
    }
    return route.fulfill({ status: 404, json: { detail: 'not found' } })
  })
  await page.goto('/maintenance?view=suggestions')
  await page.getByRole('button', { name: '安排检修' }).click()
  const form = page.getByRole('form', { name: '核对检修安排' })
  await form.getByLabel('计划日期').fill('2027-10-26')
  await form.getByLabel(/优先级/).fill('3')
  await form.getByRole('button', { name: '确认安排检修' }).click()
  await expect(page).toHaveURL(/\/maintenance\/tasks\/task-browser/)
  await page.screenshot({ path: 'test-results/visual-task-detail.png', fullPage: true })
  const editor = page.getByRole('form', { name: '调整计划' })
  await editor.getByLabel('任务状态').selectOption('in_progress')
  await editor.getByRole('button', { name: '保存任务调整' }).click()
  await expect(page.getByText('状态', { exact: true }).locator('..').getByText('执行中')).toBeVisible()
  const feedback = page.getByRole('form', { name: '执行反馈' })
  await feedback.getByLabel(/现场结果/).fill('现场已处理')
  await feedback.getByRole('button', { name: '提交执行反馈' }).click()
  await expect(page.getByText('已提交的执行反馈')).toBeVisible()
  await expect(page.getByText('现场已处理')).toBeVisible()
  expect(writes).toHaveLength(3)
  expect(writes.every((url) => url.includes('/usecases/maintenance/'))).toBe(true)
})
