<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resetPassword } from '@/api/auth'

const route = useRoute()
const router = useRouter()

const token = ref('')
const loading = ref(false)
const success = ref(false)
const formRef = ref()

const form = reactive({ new_password: '', confirm_password: '' })

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) {
    ElMessage.error('重置链接无效，请重新申请')
    router.replace('/forgot-password')
  }
})

const rules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码不能少于 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string, callback: (err?: Error) => void) => {
        if (value !== form.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function handleReset() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await resetPassword(token.value, form.new_password)
    success.value = true
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
          <el-icon size="28" color="#3b82f6"><Key /></el-icon>
        </div>
        <h1 class="brand-title">设置新密码</h1>
        <p class="brand-subtitle">请输入您的新密码，完成后即可登录</p>
      </div>

      <!-- 重置成功 -->
      <template v-if="success">
        <el-result
          icon="success"
          title="密码重置成功"
          sub-title="您的密码已更新，请使用新密码登录。"
          style="padding: 8px 0 24px;"
        />
        <router-link to="/login" class="back-btn-wrap">
          <el-button type="primary" size="large" class="submit-btn">去登录</el-button>
        </router-link>
      </template>

      <!-- 设置密码表单 -->
      <template v-else>
        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleReset">
          <el-form-item prop="new_password">
            <el-input
              v-model="form.new_password"
              type="password"
              placeholder="新密码（至少 6 位）"
              size="large"
              :prefix-icon="'Lock'"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item prop="confirm_password">
            <el-input
              v-model="form.confirm_password"
              type="password"
              placeholder="再次输入新密码"
              size="large"
              :prefix-icon="'Lock'"
              show-password
              autocomplete="new-password"
              @keyup.enter="handleReset"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="submit-btn"
            @click="handleReset"
          >
            {{ loading ? '提交中...' : '确认重置密码' }}
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
