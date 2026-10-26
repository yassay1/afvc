import { useQuery } from '@tanstack/react-query'
import { getDataOverview, getHighRiskDevices } from '../api/dataManagement'
import { queryKeys } from './queryClient'

export function useDataOverview() {
  return useQuery({ queryKey: queryKeys.overview, queryFn: ({ signal }) => getDataOverview(signal) })
}

export function useHighRiskDevices(enabled = true) {
  return useQuery({ queryKey: queryKeys.highRisk, queryFn: ({ signal }) => getHighRiskDevices(signal), enabled })
}
