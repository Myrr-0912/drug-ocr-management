import request from './index'
import type { ApiResponse, PageResponse } from '@/types/common'
import type {
  InventoryRecord,
  StockInRequest,
  StockOutRequest,
  AdjustRequest,
  InventoryListQuery,
} from '@/types/inventory'

/** 获取库存流水记录 */
export function getInventoryRecords(params?: InventoryListQuery) {
  return request.get<ApiResponse<PageResponse<InventoryRecord>>>('/inventory', { params })
}

/** 入库操作 */
export function stockIn(data: StockInRequest) {
  return request.post<ApiResponse<InventoryRecord>>('/inventory/stock-in', data)
}

/** 出库操作 */
export function stockOut(data: StockOutRequest) {
  return request.post<ApiResponse<InventoryRecord>>('/inventory/stock-out', data)
}

/** 盘点调整 */
export function adjustInventory(data: AdjustRequest) {
  return request.post<ApiResponse<InventoryRecord>>('/inventory/adjust', data)
}

/** 删除库存流水记录（仅管理员） */
export function deleteInventoryRecord(id: number) {
  return request.delete<ApiResponse<null>>(`/inventory/${id}`)
}
