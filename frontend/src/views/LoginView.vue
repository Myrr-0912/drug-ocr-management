<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const form = reactive({ username: '', password: '' })
const formRef = ref()

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码不能少于 6 位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await authStore.login(form)
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 品牌标识区 -->
      <div class="brand">
        <div class="brand-icon">
          <el-icon size="32" color="#3b82f6"><FirstAidKit /></el-icon>
        </div>
        <h1 class="brand-title">药品智能管理系统</h1>
        <p class="brand-subtitle">基于 AI OCR 的药品信息识别与管理平台</p>
      </div>

      <!-- 登录表单 -->
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="'User'"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="'Lock'"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登录' }}
        </el-button>
      </el-form>

      <!-- 辅助链接区 -->
      <div class="aux-links">
        <router-link to="/forgot-password" class="aux-link">忘记密码？</router-link>
        <span class="divider">·</span>
        <router-link to="/register" class="aux-link">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f5f3ff 100%);
}

.login-card {
  width: 400px;
  background: #fff;
  border-radius: 12px;
  padding: 48px 40px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.brand {
  text-align: center;
  margin-bottom: 40px;

  .brand-icon {
    width: 64px;
    height: 64px;
    background: #eff6ff;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
  }

  .brand-title {
    font-size: 22px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 8px;
  }

  .brand-subtitle {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.5;
  }
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  border-radius: 8px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.aux-links {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #6b7280;

  .divider {
    margin: 0 8px;
    color: #d1d5db;
  }

  .aux-link {
    color: #3b82f6;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s ease-in-out;

    &:hover {
      color: #2563eb;
    }
  }
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
}
</style>
