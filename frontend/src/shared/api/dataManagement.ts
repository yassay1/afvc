import { requestJson } from './client'
import type { DataOverviewResponse, HighRiskResponse } from './types'

export function getDataOverview(signal?: AbortSignal) {
  return requestJson<DataOverviewResponse>('/usecases/overview?top_n=10', { signal })
}

export function getHighRiskDevices(signal?: AbortSignal) {
  return requestJson<HighRiskResponse>('/usecases/high-risk?top_n=10', { signal })
}
