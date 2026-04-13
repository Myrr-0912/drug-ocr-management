import request from './index'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '@/types/user'
import type { ApiResponse } from '@/types/common'

export function login(data: LoginRequest) {
  return request.post<ApiResponse<TokenResponse>>('/auth/login', data)
}

export function register(data: RegisterRequest) {
  return request.post<ApiResponse<User>>('/auth/register', data)
}

export function getMe() {
  return request.get<ApiResponse<User>>('/auth/me')
}

export function updateMe(data: { real_name?: string; phone?: string; email?: string }) {
  return request.put<ApiResponse<User>>('/auth/me', data)
}

export function logout() {
  const refreshToken = localStorage.getItem('refresh_token')
  return request.post<ApiResponse<null>>(
    '/auth/logout',
    refreshToken ? { refresh_token: refreshToken } : undefined,
  )
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post<ApiResponse<null>>('/auth/change-password', data)
}

export function refreshToken(refreshTokenStr: string) {
  return request.post<ApiResponse<TokenResponse>>('/auth/refresh', {
    refresh_token: refreshTokenStr,
  })
}

export function forgotPassword(email: string) {
  return request.post<ApiResponse<null>>('/auth/forgot-password', { email })
}

export function resetPassword(token: string, new_password: string) {
  return request.post<ApiResponse<null>>('/auth/reset-password', { token, new_password })
}
