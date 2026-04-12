import request from './index'
import type { ApiResponse, PageResponse } from '@/types/common'
import type { Batch, BatchCreate, BatchUpdate, BatchListQuery } from '@/types/batch'

/** 获取批次列表（分页 + 筛选） */
export function getBatchList(params?: BatchListQuery) {
  return request.get<ApiResponse<PageResponse<Batch>>>('/batches', { params })
}

/** 获取单个批次详情 */
export function getBatch(id: number) {
  return request.get<ApiResponse<Batch>>(`/batches/${id}`)
}

/** 新建批次 */
export function createBatch(data: BatchCreate) {
  return request.post<ApiResponse<Batch>>('/batches', data)
}

/** 更新批次 */
export function updateBatch(id: number, data: BatchUpdate) {
  return request.put<ApiResponse<Batch>>(`/batches/${id}`, data)
}

/** 删除批次 */
export function deleteBatch(id: number) {
  return request.delete<ApiResponse<null>>(`/batches/${id}`)
}
