/** Prepend a successful /auth/me response so App + RequireAuth can render in tests. */
export function withLoggedInFetch(
  handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
): (input: RequestInfo | URL, init?: RequestInit) => Promise<Response> {
  return async (input, init) => {
    if (String(input).includes('/auth/me')) {
      return new Response(JSON.stringify({ username: 'pytest' }), { status: 200 })
    }
    return handler(input, init)
  }
}
