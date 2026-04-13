export type UserRole = 'admin' | 'pharmacist' | 'user'

export interface User {
  id: number
  username: string
  real_name: string | null
  phone: string | null
  email: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RegisterRequest {
  username: string
  password: string
  real_name?: string
  phone?: string
  email?: string
}
