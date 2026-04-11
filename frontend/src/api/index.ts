import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types/common'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器：自动注入 JWT
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理错误
request.interceptors.response.use(
  (response) => {
    const data: ApiResponse = response.data
    if (data.code !== 200) {
      ElMessage.error(data.message || '操作失败')
      return Promise.reject(new Error(data.message))
    }
    return response
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || error.message

    if (status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    if (status === 403) {
      ElMessage.error('权限不足，无法执行该操作')
    } else if (status === 404) {
      ElMessage.error('请求的资源不存在')
    } else if (status === 409) {
      ElMessage.error(message || '数据冲突')
    } else {
      ElMessage.error(message || '网络错误，请稍后重试')
    }

    return Promise.reject(error)
  },
)

export default request
