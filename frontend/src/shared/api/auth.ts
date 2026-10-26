import { requestJson } from './client'

export type AuthUser = { username: string }

export function fetchMe(): Promise<AuthUser> {
  return requestJson<AuthUser>('/auth/me')
}

export function login(username: string, password: string): Promise<{ status: string; username: string }> {
  return requestJson('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<{ status: string }> {
  return requestJson('/auth/logout', { method: 'POST' })
}
