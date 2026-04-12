import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Alert, AlertListQuery, AlertStats } from '@/types/alert'
import { fetchAlerts, fetchAlertStats, triggerScan, markRead, markAllRead, resolveAlert } from '@/api/alerts'
import { ElMessage } from 'element-plus'

export const useAlertsStore = defineStore('alerts', () => {
  const list = ref<Alert[]>([])
  const total = ref(0)
  const unreadCount = ref(0)
  const stats = ref<AlertStats | null>(null)
  const loading = ref(false)

  /** 加载预警列表 */
  async function loadAlerts(query: AlertListQuery = {}) {
    loading.value = true
    try {
      const res = await fetchAlerts({ page: 1, page_size: 20, ...query })
      const payload = res.data.data
      list.value = payload.items
      total.value = payload.total
      unreadCount.value = payload.unread_count
    } finally {
      loading.value = false
    }
  }

  /** 加载统计数据（顶部徽标用） */
  async function loadStats() {
    try {
      const res = await fetchAlertStats()
      stats.value = res.data.data
      unreadCount.value = res.data.data.unread
    } catch {
      // 静默失败，不影响主流程
    }
  }

  /** 手动触发扫描 */
  async function runScan() {
    await triggerScan()
    ElMessage.success('扫描完成，预警已更新')
    await loadAlerts()
    await loadStats()
  }

  /** 批量标记已读 */
  async function readAlerts(ids: number[]) {
    await markRead(ids)
    ids.forEach(id => {
      const item = list.value.find(a => a.id === id)
      if (item) item.is_read = true
    })
    unreadCount.value = Math.max(0, unreadCount.value - ids.length)
  }

  /** 全部已读 */
  async function readAll() {
    await markAllRead()
    list.value.forEach(a => { a.is_read = true })
    unreadCount.value = 0
    ElMessage.success('全部已标记为已读')
  }

  /** 解决预警 */
  async function resolve(id: number) {
    await resolveAlert(id)
    const item = list.value.find(a => a.id === id)
    if (item) {
      item.is_resolved = true
      item.is_read = true
    }
    ElMessage.success('预警已标记解决')
  }

  return {
    list, total, unreadCount, stats, loading,
    loadAlerts, loadStats, runScan, readAlerts, readAll, resolve,
  }
})
