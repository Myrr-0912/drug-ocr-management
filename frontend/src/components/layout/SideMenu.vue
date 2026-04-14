<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => '/' + route.path.split('/')[1])

interface MenuItem {
  path: string
  title: string
  icon: string
  show: boolean
}

const menuItems = computed<MenuItem[]>(() => [
  { path: '/dashboard', title: '仪表盘', icon: 'DataLine', show: true },
  {
    path: '/ocr/upload',
    title: 'OCR 识别',
    icon: 'Camera',
    show: authStore.isPharmacist,
  },
  { path: '/drugs', title: '药品管理', icon: 'FirstAidKit', show: true },
  { path: '/inventory', title: '库存管理', icon: 'Box', show: true },
  { path: '/batches', title: '批次管理', icon: 'Grid', show: true },
  { path: '/alerts', title: '预警中心', icon: 'Bell', show: true },
  { path: '/admin/users', title: '用户管理', icon: 'User', show: authStore.isAdmin },
  { path: '/admin/login-logs', title: '登录日志', icon: 'Document', show: authStore.isAdmin },
])
</script>

<template>
  <el-menu
    :default-active="activeMenu"
    router
    class="side-menu"
    :collapse="false"
  >
    <div class="menu-logo">
      <el-icon size="20" color="#3b82f6"><FirstAidKit /></el-icon>
      <span class="logo-text">药品管理</span>
    </div>

    <template v-for="item in menuItems" :key="item.path">
      <el-menu-item v-if="item.show" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<style scoped lang="scss">
.side-menu {
  width: 220px;
  height: 100%;
  border-right: 1px solid #e5e7eb;
  background: #fff;
  overflow-y: auto;

  :deep(.el-menu-item) {
    border-radius: 6px;
    margin: 2px 8px;
    width: calc(100% - 16px);
    transition: all 0.2s ease-in-out;

    &.is-active {
      background: #eff6ff;
      color: #3b82f6;
      font-weight: 500;
    }

    &:hover {
      background: #f9fafb;
    }
  }
}

.menu-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid #f3f4f6;
  margin-bottom: 8px;

  .logo-text {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
  }
}
</style>
