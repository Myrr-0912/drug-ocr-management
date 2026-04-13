<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAlertsStore } from '@/stores/alerts'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const alertsStore = useAlertsStore()

// 应用启动时静默加载未读数
onMounted(() => alertsStore.loadStats())

const roleLabel: Record<string, string> = {
  admin: '管理员',
  pharmacist: '药师',
  user: '普通用户',
}

async function handleCommand(command: string) {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await authStore.logout()
    router.push('/login')
  }
}
</script>

<template>
  <header class="header-bar">
    <div class="header-left">
      <!-- 预留面包屑位置 -->
    </div>
    <div class="header-right">
      <!-- 预警徽标 -->
      <el-badge
        :value="alertsStore.unreadCount"
        :hidden="alertsStore.unreadCount === 0"
        class="alert-badge"
      >
        <el-button
          circle
          size="small"
          :icon="'Bell'"
          class="bell-btn"
          @click="router.push('/alerts')"
        />
      </el-badge>
      <el-dropdown @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" class="user-avatar">
            {{ authStore.user?.real_name?.[0] || authStore.user?.username?.[0] || 'U' }}
          </el-avatar>
          <div class="user-meta">
            <span class="user-name">
              {{ authStore.user?.real_name || authStore.user?.username }}
            </span>
            <el-tag
              size="small"
              :type="authStore.isAdmin ? 'danger' : authStore.isPharmacist ? 'primary' : 'info'"
            >
              {{ roleLabel[authStore.user?.role || 'user'] }}
            </el-tag>
          </div>
          <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile" :icon="'User'">
              个人中心
            </el-dropdown-item>
            <el-dropdown-item divided command="logout" :icon="'SwitchButton'">
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped lang="scss">
.header-bar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 8px;
  transition: background 0.2s ease-in-out;

  &:hover {
    background: #f9fafb;
  }
}

.user-avatar {
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .user-name {
    font-size: 13px;
    font-weight: 500;
    color: #111827;
    line-height: 1;
  }
}

.dropdown-icon {
  color: #9ca3af;
  font-size: 12px;
}

.alert-badge {
  margin-right: 8px;
}

.bell-btn {
  border: none;
  background: transparent;
  color: #6b7280;

  &:hover {
    background: #f3f4f6;
    color: #374151;
  }
}
</style>
