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

// refresh 锁：防止多个并发 401 同时触发多次 refresh
let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

// 请求拦截器：自动注入最新 Access Token（读 sessionStorage，与 auth store 保持一致）
request.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token')
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
      // 若已有 refresh 进行中，将本请求排队，等 refresh 完成后统一重试
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            config.headers.Authorization = `Bearer ${token}`
            resolve(request(config))
          })
        })
      }

      config._retry = true
      isRefreshing = true

      // 动态 import 避免循环依赖
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      const newToken = await authStore.refreshAccessToken()
      isRefreshing = false

      if (newToken) {
        // 唤醒所有排队请求
        onRefreshed(newToken)
        // 重试当前请求
        config.headers.Authorization = `Bearer ${newToken}`
        return request(config)
      }

      // refresh 也失败，清空队列并跳转登录
      refreshSubscribers = []
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
