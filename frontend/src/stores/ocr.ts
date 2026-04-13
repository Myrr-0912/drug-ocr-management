import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import type { OcrRecord, OcrConfirmRequest } from '@/types/ocr'
import { uploadOcrImage, confirmOcrRecord, getOcrList, deleteOcrRecord } from '@/api/ocr'

export const useOcrStore = defineStore('ocr', () => {
  // 当前识别结果（上传后写入，确认入库后清空）
  const currentRecord = ref<OcrRecord | null>(null)
  // 历史记录列表
  const records = ref<OcrRecord[]>([])
  const total = ref(0)
  const loading = ref(false)
  const uploading = ref(false)

  /** 上传图片并识别 */
  async function uploadAndRecognize(file: File): Promise<OcrRecord | null> {
    uploading.value = true
    currentRecord.value = null
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await uploadOcrImage(formData)
      currentRecord.value = res.data.data!
      return currentRecord.value
    } catch {
      return null
    } finally {
      uploading.value = false
    }
  }

  /** 确认识别结果入库 */
  async function confirmRecord(recordId: number, data: OcrConfirmRequest): Promise<boolean> {
    try {
      const res = await confirmOcrRecord(recordId, data)
      ElMessage.success(res.data.data?.message || '识别结果已确认入库')
      currentRecord.value = null
      return true
    } catch {
      return false
    }
  }

  /** 加载历史记录列表 */
  async function loadRecords(params?: { status?: string; page?: number; page_size?: number }) {
    loading.value = true
    try {
      const res = await getOcrList(params)
      const page = res.data.data!
      records.value = page.items
      total.value = page.total
    } finally {
      loading.value = false
    }
  }

  /** 删除 OCR 记录 */
  async function deleteRecord(id: number): Promise<boolean> {
    try {
      await deleteOcrRecord(id)
      ElMessage.success('删除成功')
      records.value = records.value.filter((r) => r.id !== id)
      total.value--
      return true
    } catch {
      return false
    }
  }

  return {
    currentRecord,
    records,
    total,
    loading,
    uploading,
    uploadAndRecognize,
    confirmRecord,
    loadRecords,
    deleteRecord,
  }
})
