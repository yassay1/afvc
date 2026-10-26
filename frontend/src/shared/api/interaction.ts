import { requestJson } from './client'
import type { InteractionResponse, PendingActionsResponse } from './types'

export function sendTurn(query: string, sessionId: string) {
  return requestJson<InteractionResponse>('/interaction/turn', {
    method: 'POST',
    body: JSON.stringify({ query, session_id: sessionId }),
    signal: AbortSignal.timeout(45000),
  })
}

export function getPendingActions(sessionId: string) {
  return requestJson<PendingActionsResponse>(`/interaction/sessions/${encodeURIComponent(sessionId)}/pending`)
}

export function resolvePendingAction(kind: 'approve' | 'reject', sessionId: string, actionId: string) {
  return requestJson<InteractionResponse>(`/interaction/${kind}`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, action_id: actionId }),
  })
}
