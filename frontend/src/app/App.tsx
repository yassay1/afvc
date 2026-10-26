import { Navigate, Route, Routes, useLocation } from 'react-router'
import { AppShell } from './AppShell'
import { Workbench } from '../features/workbench/Workbench'
import { MaintenancePage } from '../features/maintenance/MaintenancePage'
import { TaskDetail } from '../features/maintenance/TaskDetail'
import { DeviceList } from '../features/devices/DeviceList'
import { DeviceDetail } from '../features/devices/DeviceDetail'
import { AssistantPage } from '../features/assistant/AssistantPage'
import { DataManagementPage } from '../features/data-management/DataManagementPage'
import { LoginPage } from '../features/auth/LoginPage'
import { RequireAuth } from '../features/auth/RequireAuth'

function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <section className="placeholder" aria-label={title}>
      <p className="placeholder__label">AFVC / 前端重建</p>
      <h2>{title}</h2>
      <p>{note}</p>
    </section>
  )
}

function NotFoundRoute() {
  const location = useLocation()
  return <Placeholder title="未找到页面" note={`路径 ${location.pathname} 不存在，请使用底部导航。`} />
}

export function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/workbench" replace />} />
          <Route path="workbench" element={<Workbench />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="maintenance" element={<MaintenancePage />} />
          <Route path="maintenance/tasks/:taskId" element={<TaskDetail />} />
          <Route path="devices" element={<DeviceList />} />
          <Route path="devices/:assetnum" element={<DeviceDetail />} />
          <Route path="data" element={<DataManagementPage />} />
          <Route path="*" element={<NotFoundRoute />} />
        </Route>
      </Route>
    </Routes>
  )
}
