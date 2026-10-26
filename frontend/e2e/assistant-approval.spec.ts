import { expect, test } from '@playwright/test'

test('pending workorder action requires explicit approval in the browser', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('afvc.assistant.currentTab.v1', JSON.stringify({ sessionId: 'browser-session', exchanges: [] }))
  })
  let pending = true
  let approved: unknown = null
  await page.route('**/interaction/sessions/*/pending', async (route) => {
    await route.fulfill({ json: { session_id: 'browser-session', pending_actions: pending ? [{ action_id: 'action-1', thread_id: 'browser-session', tool_name: 'update_workorder', status: 'pending', summary: '更新工单 42', payload: { workorder_id: 42, description: '已检修' }, executed: false }] : [] } })
  })
  await page.route('**/interaction/approve', async (route) => {
    approved = route.request().postDataJSON()
    pending = false
    await route.fulfill({ json: { status: 'success', use_case: null, assetnum: null, final_answer: '已批准并执行：更新工单 42', session_id: 'browser-session', last_assetnum: null, result: { source: 'approval' }, pending_actions: [] } })
  })
  await page.goto('/assistant')
  await expect(page.getByText('更新工单 42')).toBeVisible()
  await expect(page.getByRole('button', { name: '新会话' })).toBeDisabled()
  await page.getByRole('button', { name: '批准并执行：更新工单 42' }).click()
  await expect(page.getByText('已批准并执行：更新工单 42')).toBeVisible()
  expect(approved).toEqual({ session_id: 'browser-session', action_id: 'action-1' })
  await expect(page.getByRole('button', { name: '新会话' })).toBeEnabled()
})
