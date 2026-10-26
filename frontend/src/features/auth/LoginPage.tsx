import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../../shared/api/client'
import { useAuthMe, useLogin } from '../../shared/query/auth'

export function LoginPage() {
  const me = useAuthMe()
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const from = (location.state as { from?: string } | null)?.from
  const redirectTo = typeof from === 'string' && from.startsWith('/') && !from.startsWith('/login') ? from : '/workbench'

  if (me.isSuccess && me.data) {
    return <Navigate to={redirectTo} replace />
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await login.mutateAsync({ username: username.trim(), password })
      navigate(redirectTo, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('用户名或密码错误')
      } else {
        setError('登录失败，请稍后重试')
      }
    }
  }

  return (
    <div className="login-page">
      <section className="login-card" aria-label="登录">
        <p className="login-card__eyebrow">AFVC</p>
        <h1 className="login-card__title">检修系统登录</h1>
        <p className="login-card__hint">由管理员发放账号，无自助注册。</p>
        <form className="login-form" onSubmit={onSubmit}>
          <label className="login-form__field">
            <span>用户名</span>
            <input
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label className="login-form__field">
            <span>密码</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="login-form__error" role="alert">{error}</p>}
          <button type="submit" className="login-form__submit" disabled={login.isPending}>
            {login.isPending ? '登录中…' : '登录'}
          </button>
        </form>
      </section>
    </div>
  )
}
