import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElIcons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import '@/styles/global.scss'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 注册所有 Element Plus 图标
Object.entries(ElIcons).forEach(([name, component]) => {
  app.component(name, component)
})

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn, size: 'default' })

// 初始化时校验本地 token 是否仍有效；无效则清除，避免用过期 token 进入 dashboard
router.isReady().then(async () => {
  const { useAuthStore } = await import('@/stores/auth')
  const { getMe } = await import('@/api/auth')
  const auth = useAuthStore()
  if (auth.token) {
    try {
      await getMe()
    } catch {
      // access token 已失效且 refresh 也失败（axios 拦截器会尝试 refresh，失败后会 redirect /login）
      // 此处静默处理，拦截器已负责跳转
    }
  }
})

app.mount('#app')
