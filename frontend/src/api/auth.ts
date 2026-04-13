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
  return request.post<ApiResponse<null>>('/auth/logout')
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post<ApiResponse<null>>('/auth/change-password', data)
}
