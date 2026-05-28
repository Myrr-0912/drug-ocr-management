export type OcrStatus = 'pending' | 'paused' | 'success' | 'failed' | 'confirmed'
export type OcrMultiImageConsistencyStatus = 'passed' | 'review_required' | 'failed'

export interface OcrMultiImageConsistency {
  status: OcrMultiImageConsistencyStatus
  method: string
  review_required: boolean
  batch_confirm_allowed: boolean
  message: string
  conflicts: Array<Record<string, unknown>>
  llm_judgement?: Record<string, unknown> | null
  llm_error?: string | null
}

export interface OcrMultiImageMeta {
  image_count: number
  merged_from_image_indexes: Record<string, number>
  consistency: OcrMultiImageConsistency
}

/** OCR 提取的结构化药品信息 */
export interface ExtractedDrugData {
  name?: string
  approval_number?: string
  manufacturer?: string
  specification?: string
  batch_number?: string
  production_date?: string  // YYYY-MM-DD 字符串
  expiry_date?: string      // YYYY-MM-DD 字符串
  quantity?: number
  confidence_estimated?: boolean  // true = confidence 是字段完整度代理值
  multi_image?: OcrMultiImageMeta
}

/** OCR 主记录下的单张图片证据 */
export interface OcrRecordImage {
  id: number
  ocr_record_id: number
  image_path: string
  image_index: number
  raw_text?: string
  extracted_data?: ExtractedDrugData
  confidence?: number
  status: OcrStatus
  error_message?: string
  created_at?: string
}

/** OCR 识别记录 */
export interface OcrRecord {
  id: number
  image_path: string
  image_paths?: string[]
  image_count?: number
  images?: OcrRecordImage[]
  raw_text?: string
  extracted_data?: ExtractedDrugData
  confidence?: number
  status: OcrStatus
  drug_id?: number
  batch_id?: number
  error_message?: string
  created_at: string
}

/** 确认入库请求体 */
export interface OcrConfirmRequest {
  drug_id?: number
  drug_name: string
  approval_number?: string
  manufacturer?: string
  specification?: string
  batch_number: string
  production_date?: string  // YYYY-MM-DD
  expiry_date: string       // YYYY-MM-DD（必填）
  quantity: number
  unit: string
}

/** 确认入库响应 */
export interface OcrConfirmResponse {
  ocr_id: number
  drug_id: number
  batch_id: number
  message: string
}

/** 状态对应的中文标签和类型 */
export const OCR_STATUS_MAP: Record<OcrStatus, { label: string; type: string }> = {
  pending:   { label: '识别中',   type: 'info' },
  paused:    { label: '已暂停',   type: 'info' },
  success:   { label: '待确认',   type: 'warning' },
  failed:    { label: '识别失败', type: 'danger' },
  confirmed: { label: '已入库',   type: 'success' },
}

export function isManualReviewRequired(record: OcrRecord): boolean {
  const consistency = record.extracted_data?.multi_image?.consistency
  return consistency?.review_required === true || consistency?.batch_confirm_allowed === false
}

export function isBatchConfirmAllowed(record: OcrRecord): boolean {
  const consistency = record.extracted_data?.multi_image?.consistency
  if (record.status !== 'success') return false
  if (!consistency) return true
  return consistency.batch_confirm_allowed !== false && consistency.review_required !== true
}
