import request from './index'
import type { AxiosRequestConfig } from 'axios'
import type { ApiResponse, PageResponse } from '@/types/common'
import type { OcrRecord, OcrConfirmRequest, OcrConfirmResponse } from '@/types/ocr'

const OCR_UPLOAD_TIMEOUT_MS = 260000

/** 上传图片并触发 OCR 识别 */
export function uploadOcrImage(formData: FormData) {
  return request.post<ApiResponse<OcrRecord>>('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: OCR_UPLOAD_TIMEOUT_MS,
  })
}

/** 确认识别结果并入库 */
export function confirmOcrRecord(
  recordId: number,
  data: OcrConfirmRequest,
  config?: AxiosRequestConfig & { suppressErrorMessage?: boolean },
) {
  return request.post<ApiResponse<OcrConfirmResponse>>(`/ocr/${recordId}/confirm`, data, config)
}

/** 暂停 OCR 识别任务 */
export function pauseOcrRecord(recordId: number) {
  return request.post<ApiResponse<OcrRecord>>(`/ocr/${recordId}/pause`)
}

/** 继续 OCR 识别任务 */
export function resumeOcrRecord(recordId: number) {
  return request.post<ApiResponse<OcrRecord>>(`/ocr/${recordId}/resume`)
}

/** 获取 OCR 记录列表 */
export function getOcrList(params?: { status?: string; page?: number; page_size?: number }) {
  return request.get<ApiResponse<PageResponse<OcrRecord>>>('/ocr', { params })
}

/** 获取单条 OCR 记录 */
export function getOcrRecord(id: number) {
  return request.get<ApiResponse<OcrRecord>>(`/ocr/${id}`)
}

/** 删除 OCR 记录 */
export function deleteOcrRecord(id: number) {
  return request.delete<ApiResponse<null>>(`/ocr/${id}`)
}
