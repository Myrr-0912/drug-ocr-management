export type BatchStatus = 'normal' | 'near_expiry' | 'expired'

export interface Batch {
  id: number
  drug_id: number
  drug_name: string
  batch_number: string
  production_date: string | null
  expiry_date: string
  quantity: number
  unit: string
  status: BatchStatus
  source_ocr_id: number | null
  created_at: string
  updated_at: string
}

export interface BatchCreate {
  drug_id: number
  batch_number: string
  production_date?: string
  expiry_date: string
  quantity: number
  unit?: string
}

export interface BatchUpdate {
  batch_number?: string
  production_date?: string
  expiry_date?: string
  unit?: string
}

export interface BatchListQuery {
  drug_id?: number
  status?: BatchStatus
  keyword?: string
  page?: number
  page_size?: number
}

/** 状态显示映射 */
export const BATCH_STATUS_LABEL: Record<BatchStatus, string> = {
  normal: '正常',
  near_expiry: '临近过期',
  expired: '已过期',
}

export const BATCH_STATUS_TAG: Record<BatchStatus, string> = {
  normal: 'success',
  near_expiry: 'warning',
  expired: 'danger',
}
