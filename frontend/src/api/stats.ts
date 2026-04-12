import request from './index'
import type { ApiResponse } from '@/types/common'

export interface StatsOverview {
  total_drugs: number
  total_batches: number
  active_alerts: number
  today_stock_in: number
}

export interface TrendPoint {
  date: string
  stock_in: number
  stock_out: number
}

export interface ExpiryDistribution {
  expired: number
  near_30: number
  near_90: number
  normal: number
}

export function getOverview() {
  return request.get<ApiResponse<StatsOverview>>('/stats/overview')
}

export function getInventoryTrend(days = 30) {
  return request.get<ApiResponse<TrendPoint[]>>('/stats/inventory-trend', { params: { days } })
}

export function getExpiryDistribution() {
  return request.get<ApiResponse<ExpiryDistribution>>('/stats/expiry-distribution')
}
