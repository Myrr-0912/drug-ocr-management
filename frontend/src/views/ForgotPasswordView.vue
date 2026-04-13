<script setup lang="ts">
import { ref } from 'vue'
import { forgotPassword } from '@/api/auth'

const email = ref('')
const loading = ref(false)
const sent = ref(false)
const formRef = ref()

const rules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱格式', trigger: 'blur' },
  ],
}

async function handleSubmit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await forgotPassword(email.value)
    sent.value = true
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <!-- 品牌标识 -->
      <div class="brand">
        <div class="brand-icon">
          <el-icon size="28" color="#3b82f6"><Lock /></el-icon>
        </div>
        <h1 class="brand-title">重置密码</h1>
        <p class="brand-subtitle">输入注册邮箱，我们将发送重置链接</p>
      </div>

      <!-- 发送成功提示 -->
      <template v-if="sent">
        <el-result
          icon="success"
          title="邮件已发送"
          sub-title="请查收邮件并点击重置链接（15 分钟内有效）。若未收到，请检查垃圾邮件文件夹。"
          style="padding: 8px 0 24px;"
        />
        <router-link to="/login" class="back-btn-wrap">
          <el-button type="primary" size="large" class="submit-btn">返回登录</el-button>
        </router-link>
      </template>

      <!-- 输入邮箱表单 -->
      <template v-else>
        <el-form ref="formRef" :model="{ email }" :rules="rules" @submit.prevent="handleSubmit">
          <el-form-item prop="email">
            <el-input
              v-model="email"
              placeholder="注册时使用的邮箱"
              size="large"
              :prefix-icon="'Message'"
              autocomplete="email"
              @keyup.enter="handleSubmit"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="submit-btn"
            @click="handleSubmit"
          >
            {{ loading ? '发送中...' : '发送重置链接' }}
          </el-button>
        </el-form>

        <p class="back-hint">
          <router-link to="/login" class="back-link">← 返回登录</router-link>
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f5f3ff 100%);
}

.card {
  width: 400px;
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
    width: 56px;
    height: 56px;
    background: #eff6ff;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
  }

  .brand-title {
    font-size: 20px;
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

.submit-btn {
  width: 100%;
  margin-top: 4px;
  border-radius: 8px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.back-btn-wrap {
  display: block;
  text-decoration: none;
}

.back-hint {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;

  .back-link {
    color: #6b7280;
    text-decoration: none;
    transition: color 0.2s ease-in-out;

    &:hover {
      color: #3b82f6;
    }
  }
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
}
</style>
