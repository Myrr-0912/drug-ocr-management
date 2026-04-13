import request from './index'
import type { AlertListQuery, AlertListResponse, AlertStats } from '@/types/alert'

/** 获取预警统计 */
export function fetchAlertStats() {
  return request.get<any, { data: { data: AlertStats } }>('/alerts/stats')
}

/** 分页查询预警列表 */
export function fetchAlerts(params: AlertListQuery) {
  return request.get<any, { data: { data: AlertListResponse } }>('/alerts', { params })
}

/** 手动触发扫描 */
export function triggerScan() {
  return request.post('/alerts/scan')
}

/** 批量标记已读 */
export function markRead(alertIds: number[]) {
  return request.patch('/alerts/read', alertIds)
}

/** 全部标记已读 */
export function markAllRead() {
  return request.patch('/alerts/read-all')
}

/** 标记某条预警已解决 */
export function resolveAlert(alertId: number) {
  return request.patch(`/alerts/${alertId}/resolve`)
}
