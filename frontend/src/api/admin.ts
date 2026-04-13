import request from './index'
import type { ApiResponse, PageResponse } from '@/types/common'
import type { User, UserRole } from '@/types/user'

export interface AdminCreateUserRequest {
  username: string
  password: string
  real_name?: string
  phone?: string
  email?: string
  role: UserRole
}

export interface AdminUpdateUserRequest {
  real_name?: string
  phone?: string
  email?: string
  role?: UserRole
  is_active?: boolean
}

export function listUsers(params: { page?: number; page_size?: number; keyword?: string }) {
  return request.get<ApiResponse<PageResponse<User>>>('/admin/users', { params })
}

export function createUser(data: AdminCreateUserRequest) {
  return request.post<ApiResponse<{ id: number; username: string }>>('/admin/users', data)
}

export function updateUser(userId: number, data: AdminUpdateUserRequest) {
  return request.put<ApiResponse<unknown>>(`/admin/users/${userId}`, data)
}

export function deleteUser(userId: number) {
  return request.delete<ApiResponse<null>>(`/admin/users/${userId}`)
}

export function resetPassword(userId: number, newPassword: string) {
  return request.post<ApiResponse<null>>(`/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  })
}

export interface LoginLog {
  id: number
  username: string
  user_id: number | null
  ip: string | null
  user_agent: string | null
  success: boolean
  failure_reason: string | null
  created_at: string
}

export interface LoginLogQuery {
  page?: number
  page_size?: number
  username?: string
  success?: boolean
}

export function listLoginLogs(params: LoginLogQuery) {
  return request.get<ApiResponse<PageResponse<LoginLog>>>('/admin/login-logs', { params })
}
