import { useQuery } from '@tanstack/react-query'
import { requestJson } from '../api/client'
import type { HealthResponse } from '../api/types'

export const dataProfileQueryKey = ['health', 'data-profile'] as const

export function useDataProfile() {
  return useQuery({
    queryKey: dataProfileQueryKey,
    queryFn: () => requestJson<HealthResponse>('/health'),
    staleTime: 60_000,
  })
}
