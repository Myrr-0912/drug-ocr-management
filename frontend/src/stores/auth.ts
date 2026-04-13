import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginRequest } from '@/types/user'
import { login as apiLogin, getMe, logout as apiLogout, refreshToken as apiRefreshToken } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshTokenVal = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<User | null>(JSON.parse(localStorage.getItem('user_info') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isPharmacist = computed(
    () => user.value?.role === 'admin' || user.value?.role === 'pharmacist',
  )

  async function login(data: LoginRequest) {
    const resp = await apiLogin(data)
    const { access_token, refresh_token, user: userInfo } = resp.data.data!
    token.value = access_token
    refreshTokenVal.value = refresh_token
    user.value = userInfo
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user_info', JSON.stringify(userInfo))
  }

  async function fetchMe() {
    const resp = await getMe()
    user.value = resp.data.data!
    localStorage.setItem('user_info', JSON.stringify(user.value))
  }

  /** 用 Refresh Token 换取新 Access Token（axios 拦截器调用）*/
  async function refreshAccessToken(): Promise<string | null> {
    const rt = refreshTokenVal.value
    if (!rt) return null
    try {
      const resp = await apiRefreshToken(rt)
      const { access_token, refresh_token } = resp.data.data!
      token.value = access_token
      refreshTokenVal.value = refresh_token
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      return access_token
    } catch {
      // refresh token 也失效，清理登录状态
      _clearSession()
      return null
    }
  }

  async function logout() {
    // 带上 refresh_token 一起注销（写入黑名单）
    try {
      await apiLogout()
    } catch {
      // token 已过期或网络故障，忽略并继续本地清除
    }
    _clearSession()
  }

  function _clearSession() {
    token.value = null
    refreshTokenVal.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
  }

  return {
    token,
    refreshTokenVal,
    user,
    isLoggedIn,
    isAdmin,
    isPharmacist,
    login,
    fetchMe,
    logout,
    refreshAccessToken,
  }
})
