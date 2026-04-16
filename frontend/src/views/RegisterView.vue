<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { register } from '@/api/auth'

const router = useRouter()
const loading = ref(false)
const formRef = ref()

const form = reactive({
  username: '',
  password: '',
  confirm: '',
  real_name: '',
  email: '',
  phone: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度为 3 ~ 50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码不能少于 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string, callback: (e?: Error) => void) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

async function handleRegister() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await register({
      username: form.username,
      password: form.password,
      email: form.email,
      real_name: form.real_name || undefined,
      phone: form.phone || undefined,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <div class="register-card">
      <!-- 品牌标识区 -->
      <div class="brand">
        <div class="brand-icon">
          <el-icon size="32" color="#3b82f6"><FirstAidKit /></el-icon>
        </div>
        <h1 class="brand-title">创建账号</h1>
        <p class="brand-subtitle">加入药品智能管理系统</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <div class="form-row">
          <el-form-item label="用户名" prop="username" required>
            <el-input
              v-model="form.username"
              placeholder="3 ~ 50 个字符"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item label="真实姓名" prop="real_name">
            <el-input
              v-model="form.real_name"
              placeholder="选填"
              size="large"
            />
          </el-form-item>
        </div>

        <el-form-item label="密码" prop="password" required>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="不少于 6 位"
            size="large"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirm" required>
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="再次输入密码"
            size="large"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>

        <div class="form-row">
          <el-form-item label="邮箱" prop="email" required>
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱，用于找回密码"
              size="large"
              autocomplete="email"
            />
          </el-form-item>
          <el-form-item label="手机号" prop="phone">
            <el-input
              v-model="form.phone"
              placeholder="选填"
              size="large"
              autocomplete="tel"
            />
          </el-form-item>
        </div>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="submit-btn"
          @click="handleRegister"
        >
          {{ loading ? '注册中...' : '创建账号' }}
        </el-button>
      </el-form>

      <p class="login-hint">
        已有账号？
        <router-link to="/login" class="login-link">立即登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f5f3ff 100%);
  padding: 40px 16px;
}

.register-card {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 12px;
  padding: 48px 40px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.brand {
  text-align: center;
  margin-bottom: 36px;

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

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
  border-radius: 8px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.login-hint {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #6b7280;

  .login-link {
    color: #3b82f6;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s ease-in-out;

    &:hover {
      color: #2563eb;
    }
  }
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
</style>
