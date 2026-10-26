import { Bot, ClipboardList, LayoutDashboard, ScanSearch } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useDataProfile } from '../shared/query/dataProfile'
import { useAuthMe, useLogout } from '../shared/query/auth'

const navigation = [
  { to: '/workbench', label: '工作台', icon: LayoutDashboard, match: (path: string) => path === '/workbench' },
  { to: '/assistant', label: 'AI 助手', icon: Bot, match: (path: string) => path === '/assistant' },
  { to: '/maintenance?view=suggestions', label: '检修', icon: ClipboardList, match: (path: string) => path.startsWith('/maintenance') },
  { to: '/devices', label: '设备', icon: ScanSearch, match: (path: string) => path.startsWith('/devices') },
]

export function AppShell() {
  const { pathname } = useLocation()
  const isWorkbench = pathname === '/workbench'
  const isMaintenanceHome = pathname === '/maintenance'
  const isDevicePage = pathname.startsWith('/devices')
  const isAssistant = pathname.startsWith('/assistant')
  const current = navigation.find((item) => item.match(pathname))
  const health = useDataProfile()
  const me = useAuthMe()
  const logout = useLogout()

  const showDarkHeader = !isWorkbench && !isMaintenanceHome && !isDevicePage && !isAssistant

  return (
    <div className={`app-shell${isWorkbench ? ' app-shell--workbench' : ''}${isMaintenanceHome ? ' app-shell--maintenance' : ''}${isDevicePage ? ' app-shell--devices' : ''}${isAssistant ? ' app-shell--assistant' : ''}`}>
      {showDarkHeader && <header className="app-header">
        <div className="app-header__inner">
          <div className="app-brand" aria-label="AFVC 检修系统">AFVC<span className="app-brand__mark" aria-hidden="true" /></div>
          <div className="app-header__meta">
            <span className="app-header__section">{current?.label ?? (pathname.startsWith('/data') ? '数据与风险' : '页面')}</span>
            {me.data?.username && (
              <button
                type="button"
                className="app-header__logout"
                onClick={() => logout.mutate()}
                disabled={logout.isPending}
                aria-label={`退出登录（${me.data.username}）`}
              >
                退出
              </button>
            )}
          </div>
        </div>
      </header>}
      {(isWorkbench || isMaintenanceHome || isDevicePage) && me.data?.username && (
        <div className="app-account-bar">
          <span>{me.data.username}</span>
          <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>退出</button>
        </div>
      )}
      {health.data?.data_profile === 'demo' && (
        <div className="data-profile-banner" role="status" aria-label="体验环境说明">体验环境：设备、检修任务与风险数据为演示内容；设备配图为生成素材，并非现场实拍。</div>
      )}
      {(health.isError || (health.isSuccess && !['demo', 'production'].includes(health.data.data_profile))) && (
        <div className="data-profile-banner data-profile-banner--unknown" role="alert">数据模式未确认，请检查后端连接</div>
      )}
      <main id="main-content" className="app-main">
        <Outlet />
      </main>
      <nav className="bottom-nav" aria-label="主导航">
        <div className="bottom-nav__inner">
          {navigation.map(({ to, label, icon: Icon, match }) => (
            <NavLink
              key={label}
              to={to}
              className={`bottom-nav__item${match(pathname) ? ' bottom-nav__item--active' : ''}`}
              aria-current={match(pathname) ? 'page' : undefined}
            >
              <Icon size={22} strokeWidth={1.9} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
