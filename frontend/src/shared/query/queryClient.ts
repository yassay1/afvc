import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'

export const queryKeys = {
  overview: ['data', 'overview'] as const,
  highRisk: ['data', 'high-risk'] as const,
  devices: ['devices'] as const,
  deviceDiagnosis: (assetnum: string) => ['devices', 'diagnosis', assetnum] as const,
  suggestions: ['maintenance', 'suggestions'] as const,
  tasks: ['maintenance', 'tasks'] as const,
  task: (taskId: string) => ['maintenance', 'task', taskId] as const,
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        if (failureCount >= 1) return false
        return error instanceof ApiError && (error.status === null || error.status >= 500)
      },
    },
    mutations: { retry: false },
  },
})
