import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { LoginPage } from './LoginPage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function renderLogin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="login" element={<LoginPage />} />
          <Route path="workbench" element={<div>工作台内容</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path.includes('/auth/me')) {
      return new Response(JSON.stringify({ detail: '未登录' }), { status: 401 })
    }
    if (path.includes('/auth/login') && init?.method === 'POST') {
      return new Response(JSON.stringify({ status: 'success', username: 'alice' }), { status: 200 })
    }
    return new Response(JSON.stringify({ detail: 'unexpected' }), { status: 500 })
  }))
})

test('login form submits and navigates to workbench', async () => {
  const user = userEvent.setup()
  renderLogin()
  expect(await screen.findByRole('heading', { name: '检修系统登录' })).toBeInTheDocument()
  await user.type(screen.getByLabelText('用户名'), 'alice')
  await user.type(screen.getByLabelText('密码'), 'password123')
  await user.click(screen.getByRole('button', { name: '登录' }))
  expect(await screen.findByText('工作台内容')).toBeInTheDocument()
})
