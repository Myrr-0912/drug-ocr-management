import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginRequest } from '@/types/user'
import { login as apiLogin, getMe, logout as apiLogout } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<User | null>(JSON.parse(localStorage.getItem('user_info') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isPharmacist = computed(
    () => user.value?.role === 'admin' || user.value?.role === 'pharmacist',
  )

  async function login(data: LoginRequest) {
    const resp = await apiLogin(data)
    const { access_token, user: userInfo } = resp.data.data!
    token.value = access_token
    user.value = userInfo
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('user_info', JSON.stringify(userInfo))
  }

  async function fetchMe() {
    const resp = await getMe()
    user.value = resp.data.data!
    localStorage.setItem('user_info', JSON.stringify(user.value))
  }

  async function logout() {
    // 先调后端注销 token（写入 Redis 黑名单），失败也继续清除本地状态
    try {
      await apiLogout()
    } catch {
      // token 已过期或网络故障，忽略并继续本地清除
    }
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  return { token, user, isLoggedIn, isAdmin, isPharmacist, login, fetchMe, logout }
})
