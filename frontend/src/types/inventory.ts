export type OperationType = 'in' | 'out' | 'adjust'

export interface InventoryRecord {
  id: number
  drug_id: number
  drug_name: string
  batch_id: number
  batch_number: string
  operation_type: OperationType
  quantity: number
  operator_id: number | null
  operator_name: string | null
  remark: string | null
  created_at: string
}

export interface StockInRequest {
  drug_id: number
  batch_id: number
  quantity: number
  remark?: string
}

export interface StockOutRequest {
  drug_id: number
  batch_id: number
  quantity: number
  remark?: string
}

export interface AdjustRequest {
  drug_id: number
  batch_id: number
  new_quantity: number
  remark?: string
}

export interface InventoryListQuery {
  drug_id?: number
  batch_id?: number
  operation_type?: OperationType
  page?: number
  page_size?: number
}

/** 操作类型显示映射 */
export const OPERATION_TYPE_LABEL: Record<OperationType, string> = {
  in: '入库',
  out: '出库',
  adjust: '盘点调整',
}

export const OPERATION_TYPE_TAG: Record<OperationType, string> = {
  in: 'success',
  out: 'danger',
  adjust: 'info',
}
