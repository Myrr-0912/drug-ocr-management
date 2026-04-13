import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types/common'
import type { InternalAxiosRequestConfig } from 'axios'

// 扩展请求配置类型，支持重试标记
interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器：自动注入最新 Access Token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理错误 + Access Token 自动续期
request.interceptors.response.use(
  (response) => {
    const data: ApiResponse = response.data
    if (data.code !== 200) {
      ElMessage.error(data.message || '操作失败')
      return Promise.reject(new Error(data.message))
    }
    return response
  },
  async (error) => {
    const config = error.config as RetryConfig
    const status = error.response?.status
    const message = error.response?.data?.detail || error.message

    // 401 处理：先尝试用 refresh_token 续期，失败再跳登录
    if (status === 401 && !config._retry) {
      config._retry = true
      // 动态 import 避免循环依赖
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      const newToken = await authStore.refreshAccessToken()
      if (newToken) {
        // 续期成功：用新 token 重试原请求
        config.headers.Authorization = `Bearer ${newToken}`
        return request(config)
      }
      // refresh 也失败，跳转登录
      window.location.href = '/login'
      return Promise.reject(error)
    }

    if (status === 403) {
      ElMessage.error('权限不足，无法执行该操作')
    } else if (status === 404) {
      ElMessage.error('请求的资源不存在')
    } else if (status === 409) {
      ElMessage.error(message || '数据冲突')
    } else if (status !== 401) {
      ElMessage.error(message || '网络错误，请稍后重试')
    }

    return Promise.reject(error)
  },
)

export default request
