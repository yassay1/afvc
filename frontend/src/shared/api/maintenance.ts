import { requestJson } from './client'
import type {
  MaintenanceFeedbackBody, MaintenanceSuggestionsResponse, MaintenanceTaskCreateBody,
  MaintenanceTaskPatchBody, MaintenanceTaskResponse, MaintenanceTasksResponse,
} from './types'

export function getMaintenanceSuggestions(signal?: AbortSignal) {
  return requestJson<MaintenanceSuggestionsResponse>('/usecases/maintenance/suggestions?top_n=10', { signal })
}

export function getMaintenanceTasks(signal?: AbortSignal) {
  return requestJson<MaintenanceTasksResponse>('/usecases/maintenance/tasks', { signal })
}

export function getMaintenanceTask(taskId: string, signal?: AbortSignal) {
  return requestJson<MaintenanceTaskResponse>(`/usecases/maintenance/tasks/${encodeURIComponent(taskId)}`, { signal })
}

export function createMaintenanceTask(body: MaintenanceTaskCreateBody) {
  return requestJson<MaintenanceTaskResponse>('/usecases/maintenance/tasks', { method: 'POST', body: JSON.stringify(body) })
}

export function patchMaintenanceTask(taskId: string, body: MaintenanceTaskPatchBody) {
  return requestJson<MaintenanceTaskResponse>(`/usecases/maintenance/tasks/${encodeURIComponent(taskId)}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export function submitMaintenanceFeedback(taskId: string, body: MaintenanceFeedbackBody) {
  return requestJson<MaintenanceTaskResponse>(`/usecases/maintenance/tasks/${encodeURIComponent(taskId)}/feedback`, { method: 'POST', body: JSON.stringify(body) })
}
