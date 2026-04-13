<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { updateMe, changePassword } from '@/api/auth'

const authStore = useAuthStore()
const activeTab = ref('profile')

// ── 基本信息表单 ──────────────────────────────────────────────
const profileLoading = ref(false)
const profileForm = reactive({
  real_name: authStore.user?.real_name ?? '',
  email: authStore.user?.email ?? '',
  phone: authStore.user?.phone ?? '',
})

const profileRules = {
  email: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }],
}

async function handleUpdateProfile() {
  profileLoading.value = true
  try {
    await updateMe({
      real_name: profileForm.real_name || undefined,
      email: profileForm.email || undefined,
      phone: profileForm.phone || undefined,
    })
    await authStore.fetchMe()
    ElMessage.success('资料更新成功')
  } finally {
    profileLoading.value = false
  }
}

// ── 修改密码表单 ──────────────────────────────────────────────
const pwdLoading = ref(false)
const pwdFormRef = ref()
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

const pwdRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码不能少于 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string, callback: (e?: Error) => void) => {
        if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function handleChangePassword() {
  await pwdFormRef.value?.validate()
  pwdLoading.value = true
  try {
    await changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    await authStore.logout()
    // 登出后跳转由路由守卫处理
  } finally {
    pwdLoading.value = false
  }
}

const roleLabel: Record<string, string> = {
  admin: '管理员',
  pharmacist: '药师',
  user: '普通用户',
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">个人中心</h2>
      <p class="page-sub">管理您的账号信息与安全设置</p>
    </div>

    <div class="profile-layout">
      <!-- 用户卡片 -->
      <div class="user-card">
        <el-avatar :size="64" class="avatar">
          {{ authStore.user?.real_name?.[0] || authStore.user?.username?.[0] || 'U' }}
        </el-avatar>
        <div class="user-card-info">
          <p class="user-card-name">
            {{ authStore.user?.real_name || authStore.user?.username }}
          </p>
          <el-tag
            size="small"
            :type="authStore.isAdmin ? 'danger' : authStore.isPharmacist ? 'primary' : 'info'"
          >
            {{ roleLabel[authStore.user?.role || 'user'] }}
          </el-tag>
        </div>
        <p class="user-card-id">ID：{{ authStore.user?.id }}</p>
      </div>

      <!-- 操作面板 -->
      <div class="content-panel">
        <el-tabs v-model="activeTab" class="profile-tabs">
          <!-- 基本信息 Tab -->
          <el-tab-pane label="基本信息" name="profile">
            <el-form
              :model="profileForm"
              :rules="profileRules"
              label-position="top"
              class="panel-form"
            >
              <div class="form-row">
                <el-form-item label="用户名">
                  <el-input
                    :value="authStore.user?.username"
                    disabled
                    size="large"
                  />
                </el-form-item>
                <el-form-item label="真实姓名">
                  <el-input
                    v-model="profileForm.real_name"
                    placeholder="请输入真实姓名"
                    size="large"
                  />
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="邮箱" prop="email">
                  <el-input
                    v-model="profileForm.email"
                    placeholder="请输入邮箱"
                    size="large"
                    autocomplete="email"
                  />
                </el-form-item>
                <el-form-item label="手机号">
                  <el-input
                    v-model="profileForm.phone"
                    placeholder="请输入手机号"
                    size="large"
                    autocomplete="tel"
                  />
                </el-form-item>
              </div>
              <el-button
                type="primary"
                size="large"
                :loading="profileLoading"
                class="save-btn"
                @click="handleUpdateProfile"
              >
                保存修改
              </el-button>
            </el-form>
          </el-tab-pane>

          <!-- 修改密码 Tab -->
          <el-tab-pane label="修改密码" name="password">
            <el-form
              ref="pwdFormRef"
              :model="pwdForm"
              :rules="pwdRules"
              label-position="top"
              class="panel-form pwd-form"
            >
              <el-form-item label="当前密码" prop="old_password" required>
                <el-input
                  v-model="pwdForm.old_password"
                  type="password"
                  placeholder="请输入当前密码"
                  size="large"
                  show-password
                  autocomplete="current-password"
                />
              </el-form-item>
              <el-form-item label="新密码" prop="new_password" required>
                <el-input
                  v-model="pwdForm.new_password"
                  type="password"
                  placeholder="不少于 6 位"
                  size="large"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
              <el-form-item label="确认新密码" prop="confirm" required>
                <el-input
                  v-model="pwdForm.confirm"
                  type="password"
                  placeholder="再次输入新密码"
                  size="large"
                  show-password
                  autocomplete="new-password"
                />
              </el-form-item>
              <el-button
                type="danger"
                size="large"
                :loading="pwdLoading"
                class="save-btn"
                @click="handleChangePassword"
              >
                修改密码
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  margin-bottom: 28px;

  .page-title {
    font-size: 20px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 4px;
  }

  .page-sub {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.5;
  }
}

.profile-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 24px;
  align-items: start;
}

.user-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);

  .avatar {
    background: #eff6ff;
    color: #3b82f6;
    font-size: 24px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .user-card-info {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }

  .user-card-name {
    font-size: 15px;
    font-weight: 600;
    color: #111827;
    line-height: 1.3;
  }

  .user-card-id {
    font-size: 12px;
    color: #9ca3af;
  }
}

.content-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 24px 28px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 20px;
}

.panel-form {
  margin-top: 16px;
}

.pwd-form {
  max-width: 400px;
}

.save-btn {
  margin-top: 8px;
}

:deep(.el-form-item__label) {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
  padding-bottom: 4px;
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
}

:deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
}
</style>
