<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { User, UserRole } from '@/types/user'
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser,
  resetPassword,
  type AdminCreateUserRequest,
  type AdminUpdateUserRequest,
} from '@/api/admin'

// ── 列表状态 ───────────────────────────────────────────────
const loading = ref(false)
const users = ref<User[]>([])
const total = ref(0)
const keyword = ref('')
const pagination = reactive({ page: 1, page_size: 15 })

async function fetchUsers() {
  loading.value = true
  try {
    const res = await listUsers({ ...pagination, keyword: keyword.value || undefined })
    users.value = res.data.data?.items ?? []
    total.value = res.data.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

function onSearch() {
  pagination.page = 1
  fetchUsers()
}

// ── 创建对话框 ─────────────────────────────────────────────
const createVisible = ref(false)
const createForm = reactive<AdminCreateUserRequest>({
  username: '',
  password: '',
  real_name: undefined,
  phone: undefined,
  email: undefined,
  role: 'user',
})
const createRef = ref()

function openCreate() {
  Object.assign(createForm, {
    username: '',
    password: '',
    real_name: undefined,
    phone: undefined,
    email: undefined,
    role: 'user',
  })
  createVisible.value = true
}

async function submitCreate() {
  await createRef.value.validate()
  try {
    await createUser(createForm)
    ElMessage.success('用户创建成功')
    createVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '创建失败')
  }
}

// ── 编辑对话框 ─────────────────────────────────────────────
const editVisible = ref(false)
const editTarget = ref<User | null>(null)
const editForm = reactive<AdminUpdateUserRequest & { username: string }>({
  username: '',
  real_name: undefined,
  phone: undefined,
  email: undefined,
  role: 'user',
  is_active: true,
})

function openEdit(user: User) {
  editTarget.value = user
  Object.assign(editForm, {
    username: user.username,
    real_name: user.real_name ?? undefined,
    phone: user.phone ?? undefined,
    email: user.email ?? undefined,
    role: user.role,
    is_active: user.is_active,
  })
  editVisible.value = true
}

async function submitEdit() {
  if (!editTarget.value) return
  const payload: AdminUpdateUserRequest = {
    real_name: editForm.real_name,
    phone: editForm.phone,
    email: editForm.email,
    role: editForm.role,
    is_active: editForm.is_active,
  }
  try {
    await updateUser(editTarget.value.id, payload)
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '更新失败')
  }
}

// ── 删除 ───────────────────────────────────────────────────
async function handleDelete(user: User) {
  await ElMessageBox.confirm(`确定删除用户「${user.username}」？此操作不可撤销。`, '确认删除', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await deleteUser(user.id)
    ElMessage.success('已删除')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '删除失败')
  }
}

// ── 重置密码 ───────────────────────────────────────────────
const resetVisible = ref(false)
const resetTarget = ref<User | null>(null)
const newPassword = ref('')

function openReset(user: User) {
  resetTarget.value = user
  newPassword.value = ''
  resetVisible.value = true
}

async function submitReset() {
  if (!resetTarget.value || newPassword.value.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  try {
    await resetPassword(resetTarget.value.id, newPassword.value)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '重置失败')
  }
}

// ── 角色展示辅助 ───────────────────────────────────────────
const roleMap: Record<UserRole, { label: string; type: 'danger' | 'warning' | 'info' }> = {
  admin: { label: '管理员', type: 'danger' },
  pharmacist: { label: '药师', type: 'warning' },
  user: { label: '普通用户', type: 'info' },
}

const roleOptions: { label: string; value: UserRole }[] = [
  { label: '管理员', value: 'admin' },
  { label: '药师', value: 'pharmacist' },
  { label: '普通用户', value: 'user' },
]

onMounted(fetchUsers)
</script>

<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">用户管理</h2>
        <span class="page-count">共 {{ total }} 位用户</span>
      </div>
      <el-button type="primary" @click="openCreate">新建用户</el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索用户名或姓名…"
        clearable
        style="width: 280px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-button @click="onSearch">搜索</el-button>
    </div>

    <!-- 用户列表 -->
    <div class="table-card">
      <el-table :data="users" v-loading="loading" style="width: 100%" row-key="id">
        <el-table-column prop="id" label="ID" width="64" align="center" />
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column prop="real_name" label="真实姓名" min-width="110">
          <template #default="{ row }">
            <span :class="{ 'text-muted': !row.real_name }">{{ row.real_name ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="roleMap[row.role as UserRole].type" size="small">
              {{ roleMap[row.role as UserRole].label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160">
          <template #default="{ row }">
            <span :class="{ 'text-muted': !row.email }">{{ row.email ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? row.created_at.slice(0, 16).replace('T', ' ') : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="warning" @click="openReset(row)">重置密码</el-button>
            <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="total"
          layout="total, prev, pager, next"
          background
          @current-change="fetchUsers"
          @size-change="fetchUsers"
        />
      </div>
    </div>

    <!-- 创建用户对话框 -->
    <el-dialog v-model="createVisible" title="新建用户" width="440px" :close-on-click-modal="false">
      <el-form ref="createRef" :model="createForm" label-width="80px" class="dialog-form"
        :rules="{
          username: [{ required: true, message: '请填写用户名', trigger: 'blur' }, { min: 3, message: '至少 3 位', trigger: 'blur' }],
          password: [{ required: true, message: '请填写密码', trigger: 'blur' }, { min: 6, message: '至少 6 位', trigger: 'blur' }],
        }">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3-50 位字符" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="createForm.real_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option v-for="o in roleOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="createForm.phone" placeholder="可选" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createForm.email" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户对话框 -->
    <el-dialog v-model="editVisible" title="编辑用户" width="440px" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="80px" class="dialog-form">
        <el-form-item label="用户名">
          <el-input :value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="editForm.real_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option v-for="o in roleOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="editForm.phone" placeholder="可选" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="360px" :close-on-click-modal="false">
      <p class="reset-tip">为用户 <strong>{{ resetTarget?.username }}</strong> 设置新密码：</p>
      <el-input
        v-model="newPassword"
        type="password"
        show-password
        placeholder="至少 6 位新密码"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="warning" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.page-container {
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin: 0;
}

.page-count {
  font-size: 13px;
  color: #9ca3af;
}

.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.table-card {
  background: #fff;
  border: 1px solid #f3f4f6;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
  border-top: 1px solid #f3f4f6;
}

.text-muted {
  color: #d1d5db;
}

.dialog-form {
  padding: 0 8px;
}

.reset-tip {
  font-size: 14px;
  color: #374151;
  line-height: 1.5;
  margin: 0;
}
</style>
