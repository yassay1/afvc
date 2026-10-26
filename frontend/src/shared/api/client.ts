export class ApiError extends Error {
  constructor(
    public readonly status: number | null,
    public readonly detail: unknown,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** Register a handler for HTTP 401 (cleared session → login). */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler
}

export async function requestJson<T>(path: `/${string}`, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers, credentials: 'include' })
  } catch (error) {
    if (error instanceof DOMException && (error.name === 'AbortError' || error.name === 'TimeoutError')) throw error
    throw new ApiError(null, null, '无法连接服务，请检查网络后重试。')
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) {
      onUnauthorized?.()
    }
    const detail = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : payload
    throw new ApiError(response.status, detail, `请求失败（${response.status}）`)
  }
  return payload as T
}
