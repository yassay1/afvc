import { useEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router'
import { setUnauthorizedHandler } from '../../shared/api/client'
import { authMeQueryKey, useAuthMe } from '../../shared/query/auth'
import { queryClient } from '../../shared/query/queryClient'
import { StateMessage } from '../../shared/components/StateMessage'

export function RequireAuth() {
  const me = useAuthMe()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    setUnauthorizedHandler(() => {
      queryClient.setQueryData(authMeQueryKey, null)
      navigate('/login', { replace: true, state: { from: location.pathname + location.search } })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate, location.pathname, location.search])

  if (me.isLoading) {
    return <StateMessage title="正在确认登录状态" detail="请稍候…" />
  }

  if (me.isError) {
    return <StateMessage title="无法确认登录状态" detail="请检查网络后重试。" retry={() => me.refetch()} />
  }

  if (!me.data) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }

  return <Outlet />
}
