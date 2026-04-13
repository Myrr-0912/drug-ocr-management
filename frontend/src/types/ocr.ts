export type OcrStatus = 'pending' | 'success' | 'failed' | 'confirmed'

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
}

/** OCR 识别记录 */
export interface OcrRecord {
  id: number
  image_path: string
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
  success:   { label: '待确认',   type: 'warning' },
  failed:    { label: '识别失败', type: 'danger' },
  confirmed: { label: '已入库',   type: 'success' },
}
