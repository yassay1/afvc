import { useQuery } from '@tanstack/react-query'
import { getMaintenanceSuggestions, getMaintenanceTask, getMaintenanceTasks } from '../api/maintenance'
import { queryKeys } from './queryClient'

export function useMaintenanceSuggestions() {
  return useQuery({ queryKey: queryKeys.suggestions, queryFn: ({ signal }) => getMaintenanceSuggestions(signal) })
}

export function useMaintenanceTasks() {
  return useQuery({ queryKey: queryKeys.tasks, queryFn: ({ signal }) => getMaintenanceTasks(signal) })
}

export function useMaintenanceTask(taskId: string) {
  return useQuery({ queryKey: queryKeys.task(taskId), queryFn: ({ signal }) => getMaintenanceTask(taskId, signal), enabled: Boolean(taskId) })
}
