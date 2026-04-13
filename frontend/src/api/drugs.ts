import request from './index'
import type { ApiResponse, PageResponse } from '@/types/common'
import type { Drug, DrugCreate, DrugUpdate, DrugListQuery } from '@/types/drug'

/** 获取药品列表（分页 + 筛选） */
export function getDrugList(params?: DrugListQuery) {
  return request.get<ApiResponse<PageResponse<Drug>>>('/drugs', { params })
}

/** 获取单个药品详情 */
export function getDrug(id: number) {
  return request.get<ApiResponse<Drug>>(`/drugs/${id}`)
}

/** 新建药品 */
export function createDrug(data: DrugCreate) {
  return request.post<ApiResponse<Drug>>('/drugs', data)
}

/** 更新药品 */
export function updateDrug(id: number, data: DrugUpdate) {
  return request.put<ApiResponse<Drug>>(`/drugs/${id}`, data)
}

/** 删除药品 */
export function deleteDrug(id: number) {
  return request.delete<ApiResponse<null>>(`/drugs/${id}`)
}
