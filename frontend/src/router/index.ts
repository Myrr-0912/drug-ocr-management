import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/forgot-password',
      name: 'ForgotPassword',
      component: () => import('@/views/ForgotPasswordView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/reset-password',
      name: 'ResetPassword',
      component: () => import('@/views/ResetPasswordView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '仪表盘' },
        },
        {
          path: 'ocr/upload',
          name: 'OcrUpload',
          component: () => import('@/views/ocr/OcrUploadView.vue'),
          meta: { title: 'OCR识别', pharmacistOnly: true },
        },
        {
          path: 'drugs',
          name: 'DrugList',
          component: () => import('@/views/drugs/DrugListView.vue'),
          meta: { title: '药品管理' },
        },
        {
          path: 'drugs/:id',
          name: 'DrugDetail',
          component: () => import('@/views/drugs/DrugDetailView.vue'),
          meta: { title: '药品详情' },
        },
        {
          path: 'inventory',
          name: 'InventoryList',
          component: () => import('@/views/inventory/InventoryListView.vue'),
          meta: { title: '库存管理' },
        },
        {
          path: 'inventory/stock-in',
          name: 'StockIn',
          component: () => import('@/views/inventory/StockInView.vue'),
          meta: { title: '入库操作', pharmacistOnly: true },
        },
        {
          path: 'batches',
          name: 'BatchList',
          component: () => import('@/views/batches/BatchListView.vue'),
          meta: { title: '批次管理' },
        },
        {
          path: 'alerts',
          name: 'AlertList',
          component: () => import('@/views/alerts/AlertListView.vue'),
          meta: { title: '预警中心' },
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/ProfileView.vue'),
          meta: { title: '个人中心' },
        },
        {
          path: 'admin/users',
          name: 'UserManage',
          component: () => import('@/views/admin/UserManageView.vue'),
          meta: { title: '用户管理', adminOnly: true },
        },
        {
          path: 'admin/login-logs',
          name: 'LoginLogs',
          component: () => import('@/views/admin/LoginLogView.vue'),
          meta: { title: '登录日志', adminOnly: true },
        },
      ],
    },
    // 404 重定向
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：未登录跳转 /login，权限不足提示
router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth !== false && !auth.isLoggedIn) {
    return { name: 'Login' }
  }

  if (to.meta.adminOnly && !auth.isAdmin) {
    return { name: 'Dashboard' }
  }

  if (to.meta.pharmacistOnly && !auth.isPharmacist) {
    return { name: 'Dashboard' }
  }
})

export default router
