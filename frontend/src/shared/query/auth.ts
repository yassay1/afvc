import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import { fetchMe, login, logout, type AuthUser } from '../api/auth'

export const authMeQueryKey = ['auth', 'me'] as const

export function useAuthMe() {
  return useQuery({
    queryKey: authMeQueryKey,
    queryFn: async (): Promise<AuthUser | null> => {
      try {
        return await fetchMe()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    staleTime: 60_000,
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) => login(username, password),
    onSuccess: (data) => {
      queryClient.setQueryData(authMeQueryKey, { username: data.username } satisfies AuthUser)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => logout(),
    onSettled: () => {
      queryClient.setQueryData(authMeQueryKey, null)
      queryClient.clear()
    },
  })
}
