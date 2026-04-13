<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listLoginLogs, type LoginLog } from '@/api/admin'

const loading = ref(false)
const logs = ref<LoginLog[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  username: '',
  success: undefined as boolean | undefined,
})

async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: query.page,
      page_size: query.page_size,
    }
    if (query.username) params.username = query.username
    if (query.success !== undefined) params.success = query.success

    const resp = await listLoginLogs(params as Parameters<typeof listLoginLogs>[0])
    logs.value = resp.data.data?.items ?? []
    total.value = resp.data.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  fetchLogs()
}

function handleReset() {
  query.username = ''
  query.success = undefined
  query.page = 1
  fetchLogs()
}

function handlePageChange(page: number) {
  query.page = page
  fetchLogs()
}

// UA 简化展示（取浏览器名称）
function shortUA(ua: string | null): string {
  if (!ua) return '-'
  if (ua.includes('Chrome')) return 'Chrome'
  if (ua.includes('Firefox')) return 'Firefox'
  if (ua.includes('Safari') && !ua.includes('Chrome')) return 'Safari'
  if (ua.includes('Edge')) return 'Edge'
  return ua.slice(0, 30) + (ua.length > 30 ? '…' : '')
}

onMounted(fetchLogs)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">登录日志</h2>
      <p class="page-sub">记录所有登录尝试，包括成功与失败</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="query.username"
        placeholder="按用户名搜索"
        clearable
        style="width: 200px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-select
        v-model="query.success"
        placeholder="全部状态"
        clearable
        style="width: 140px"
        @change="handleSearch"
      >
        <el-option label="登录成功" :value="true" />
        <el-option label="登录失败" :value="false" />
      </el-select>
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <!-- 日志表格 -->
    <el-table
      v-loading="loading"
      :data="logs"
      row-class-name="log-row"
      class="log-table"
      stripe
    >
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag
            :type="row.success ? 'success' : 'danger'"
            size="small"
            disable-transitions
          >
            {{ row.success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="username" label="用户名" min-width="120" />

      <el-table-column prop="ip" label="IP 地址" min-width="130">
        <template #default="{ row }">{{ row.ip || '-' }}</template>
      </el-table-column>

      <el-table-column label="浏览器" min-width="100">
        <template #default="{ row }">{{ shortUA(row.user_agent) }}</template>
      </el-table-column>

      <el-table-column prop="failure_reason" label="失败原因" min-width="160">
        <template #default="{ row }">
          <span :class="{ 'text-danger': !row.success }">
            {{ row.failure_reason || '-' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="时间" min-width="170">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  margin-bottom: 24px;

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

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.log-table {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

.text-danger {
  color: #ef4444;
  font-size: 13px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
