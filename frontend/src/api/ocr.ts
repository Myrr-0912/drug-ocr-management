import request from './index'
import type { ApiResponse, PageResponse } from '@/types/common'
import type { OcrRecord, OcrConfirmRequest, OcrConfirmResponse } from '@/types/ocr'

/** 上传图片并触发 OCR 识别 */
export function uploadOcrImage(formData: FormData) {
  return request.post<ApiResponse<OcrRecord>>('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,  // OCR 最多等待 60s
  })
}

/** 确认识别结果并入库 */
export function confirmOcrRecord(recordId: number, data: OcrConfirmRequest) {
  return request.post<ApiResponse<OcrConfirmResponse>>(`/ocr/${recordId}/confirm`, data)
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
