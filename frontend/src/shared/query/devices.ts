import { useQuery } from '@tanstack/react-query'
import { getDeviceDiagnosis, getDevices } from '../api/devices'
import { queryKeys } from './queryClient'

export function useDevices() {
  return useQuery({ queryKey: queryKeys.devices, queryFn: ({ signal }) => getDevices(signal) })
}

export function useDeviceDiagnosis(assetnum: string) {
  return useQuery({ queryKey: queryKeys.deviceDiagnosis(assetnum), queryFn: ({ signal }) => getDeviceDiagnosis(assetnum, signal), enabled: Boolean(assetnum) })
}
