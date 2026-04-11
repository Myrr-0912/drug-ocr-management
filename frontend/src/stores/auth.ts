import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginRequest } from '@/types/user'
import { login as apiLogin, getMe } from '@/api/auth'

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

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  return { token, user, isLoggedIn, isAdmin, isPharmacist, login, fetchMe, logout }
})
