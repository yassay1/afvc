import { requestJson } from './client'
import type { DeviceDiagnosisResponse, DeviceListResponse } from './types'

export function getDevices(signal?: AbortSignal) {
  return requestJson<DeviceListResponse>('/usecases/devices', { signal })
}

export function getDeviceDiagnosis(assetnum: string, signal?: AbortSignal) {
  return requestJson<DeviceDiagnosisResponse>(`/usecases/devices/${encodeURIComponent(assetnum)}/diagnosis`, { signal })
}
