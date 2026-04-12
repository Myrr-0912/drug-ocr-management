<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import { useAuthStore } from '@/stores/auth'
import type { AlertType, AlertSeverity, AlertListQuery } from '@/types/alert'
import { ElMessageBox } from 'element-plus'

const alertsStore = useAlertsStore()
const authStore = useAuthStore()

const canScan = computed(() => authStore.isAdmin || authStore.isPharmacist)

/* ── 筛选状态 ── */
const query = ref<AlertListQuery>({
  alert_type: undefined,
  severity: undefined,
  is_read: undefined,
  is_resolved: false,   // 默认只看未解决
  page: 1,
  page_size: 20,
})

const scanning = ref(false)

/* ── 类型 / 级别映射 ── */
const typeLabels: Record<AlertType, string> = {
  expiry_warning: '临期预警',
  expired: '已过期',
  low_stock: '库存不足',
}

const severityConfig: Record<AlertSeverity, { label: string; type: 'danger' | 'warning' | 'info' }> = {
  critical: { label: '严重', type: 'danger' },
  warning:  { label: '警告', type: 'warning' },
  info:     { label: '提示', type: 'info' },
}

/* ── 生命周期 ── */
onMounted(async () => {
  await Promise.all([alertsStore.loadAlerts(query.value), alertsStore.loadStats()])
})

/* ── 操作 ── */
async function handleScan() {
  scanning.value = true
  try {
    await alertsStore.runScan()
  } finally {
    scanning.value = false
  }
}

async function handleReadAll() {
  await alertsStore.readAll()
}

async function handleResolve(id: number) {
  await ElMessageBox.confirm('确认将此预警标记为已解决？', '操作确认', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await alertsStore.resolve(id)
}

async function applyFilter() {
  query.value.page = 1
  await alertsStore.loadAlerts(query.value)
}

async function handlePageChange(page: number) {
  query.value.page = page
  await alertsStore.loadAlerts(query.value)
}

function resetFilter() {
  query.value = { is_resolved: false, page: 1, page_size: 20 }
  alertsStore.loadAlerts(query.value)
}
</script>

<template>
  <div class="alert-page">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">预警中心</h2>
        <el-badge
          v-if="alertsStore.unreadCount > 0"
          :value="alertsStore.unreadCount"
          class="unread-badge"
        />
      </div>
      <div class="header-actions">
        <el-button
          v-if="canScan"
          :loading="scanning"
          @click="handleScan"
        >
          立即扫描
        </el-button>
        <el-button @click="handleReadAll">全部已读</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="alertsStore.stats" class="stats-row">
      <div class="stat-card critical">
        <div class="stat-value">{{ alertsStore.stats.critical }}</div>
        <div class="stat-label">严重</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-value">{{ alertsStore.stats.warning }}</div>
        <div class="stat-label">警告</div>
      </div>
      <div class="stat-card info">
        <div class="stat-value">{{ alertsStore.stats.info }}</div>
        <div class="stat-label">提示</div>
      </div>
      <div class="stat-card unread">
        <div class="stat-value">{{ alertsStore.stats.unread }}</div>
        <div class="stat-label">未读</div>
      </div>
      <div class="stat-card total">
        <div class="stat-value">{{ alertsStore.stats.total }}</div>
        <div class="stat-label">全部</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select
        v-model="query.alert_type"
        placeholder="全部类型"
        clearable
        class="filter-item"
      >
        <el-option label="临期预警" value="expiry_warning" />
        <el-option label="已过期" value="expired" />
        <el-option label="库存不足" value="low_stock" />
      </el-select>

      <el-select
        v-model="query.severity"
        placeholder="全部级别"
        clearable
        class="filter-item"
      >
        <el-option label="严重" value="critical" />
        <el-option label="警告" value="warning" />
        <el-option label="提示" value="info" />
      </el-select>

      <el-select
        v-model="query.is_read"
        placeholder="全部状态"
        clearable
        class="filter-item"
      >
        <el-option label="未读" :value="false" />
        <el-option label="已读" :value="true" />
      </el-select>

      <el-select
        v-model="query.is_resolved"
        placeholder="处理状态"
        clearable
        class="filter-item"
      >
        <el-option label="未解决" :value="false" />
        <el-option label="已解决" :value="true" />
      </el-select>

      <el-button type="primary" @click="applyFilter">查询</el-button>
      <el-button @click="resetFilter">重置</el-button>
    </div>

    <!-- 预警列表 -->
    <div class="alert-list" v-loading="alertsStore.loading">
      <div
        v-for="item in alertsStore.list"
        :key="item.id"
        class="alert-item"
        :class="[`severity-${item.severity}`, { unread: !item.is_read, resolved: item.is_resolved }]"
      >
        <div class="alert-indicator" />

        <div class="alert-body">
          <div class="alert-top">
            <el-tag
              size="small"
              :type="severityConfig[item.severity].type"
              effect="plain"
            >
              {{ severityConfig[item.severity].label }}
            </el-tag>
            <el-tag size="small" effect="plain" type="info" class="type-tag">
              {{ typeLabels[item.alert_type] }}
            </el-tag>
            <span v-if="!item.is_read" class="unread-dot" />
          </div>

          <p class="alert-message">{{ item.message }}</p>

          <div class="alert-meta">
            <span class="meta-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
            <el-tag v-if="item.is_resolved" size="small" type="success" effect="plain">
              已解决
            </el-tag>
          </div>
        </div>

        <div class="alert-actions">
          <el-button
            v-if="!item.is_resolved"
            size="small"
            type="primary"
            plain
            @click="handleResolve(item.id)"
          >
            标记解决
          </el-button>
        </div>
      </div>

      <el-empty
        v-if="!alertsStore.loading && alertsStore.list.length === 0"
        description="暂无预警记录"
        :image-size="80"
      />
    </div>

    <!-- 分页 -->
    <div v-if="alertsStore.total > (query.page_size ?? 20)" class="pagination">
      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :total="alertsStore.total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.alert-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .page-title {
    font-size: 20px;
    font-weight: 600;
    color: #111827;
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

/* ── 统计卡片 ── */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 100px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  text-align: center;

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 6px;
  }

  .stat-label {
    font-size: 12px;
    color: #6b7280;
  }

  &.critical  { .stat-value { color: #ef4444; } }
  &.warning   { .stat-value { color: #f59e0b; } }
  &.info      { .stat-value { color: #3b82f6; } }
  &.unread    { .stat-value { color: #8b5cf6; } }
  &.total     { .stat-value { color: #374151; } }
}

/* ── 筛选栏 ── */
.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;

  .filter-item {
    width: 140px;
  }
}

/* ── 预警列表 ── */
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 200px;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  transition: all 0.2s ease-in-out;

  &:hover {
    border-color: #d1d5db;
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  }

  &.unread {
    background: #fafbff;
    border-left: 3px solid #3b82f6;
  }

  &.resolved {
    opacity: 0.6;
  }

  /* 左侧色条 */
  .alert-indicator {
    width: 4px;
    border-radius: 2px;
    align-self: stretch;
    min-height: 40px;
    flex-shrink: 0;
  }

  &.severity-critical .alert-indicator { background: #ef4444; }
  &.severity-warning  .alert-indicator { background: #f59e0b; }
  &.severity-info     .alert-indicator { background: #3b82f6; }
}

.alert-body {
  flex: 1;
  min-width: 0;
}

.alert-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;

  .type-tag { margin-left: 2px; }

  .unread-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #3b82f6;
    margin-left: 4px;
  }
}

.alert-message {
  font-size: 14px;
  color: #374151;
  margin: 0 0 6px;
  line-height: 1.5;
}

.alert-meta {
  display: flex;
  align-items: center;
  gap: 10px;

  .meta-time {
    font-size: 12px;
    color: #9ca3af;
  }
}

.alert-actions {
  flex-shrink: 0;
}

/* ── 分页 ── */
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
