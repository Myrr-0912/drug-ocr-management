import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import type { OcrRecord, OcrConfirmRequest, OcrStatus } from '@/types/ocr'
import { uploadOcrImage, confirmOcrRecord, getOcrList, getOcrRecord, deleteOcrRecord } from '@/api/ocr'

const OCR_POLL_INTERVAL_MS = 2000
const OCR_POLL_TIMEOUT_MS = 260000

export const useOcrStore = defineStore('ocr', () => {
  // 当前识别结果（上传后写入，确认入库后清空）
  const currentRecord = ref<OcrRecord | null>(null)
  // 历史记录列表
  const records = ref<OcrRecord[]>([])
  const taskQueueRecords = ref<OcrRecord[]>([])
  const unreadTaskIds = ref<number[]>([])
  const total = ref(0)
  const loading = ref(false)
  const uploading = ref(false)
  const pollingRecordIds = ref<number[]>([])
  const recognizing = computed(() => pollingRecordIds.value.length > 0)
  let pollVersion = 0

  function upsertRecord(record: OcrRecord) {
    const idx = records.value.findIndex((r) => r.id === record.id)
    if (idx >= 0) {
      records.value[idx] = record
    }
  }

  function upsertTaskQueueRecord(record: OcrRecord) {
    if (record.status === 'confirmed') {
      taskQueueRecords.value = taskQueueRecords.value.filter((r) => r.id !== record.id)
      markTaskRead(record.id)
      return
    }

    const idx = taskQueueRecords.value.findIndex((r) => r.id === record.id)
    if (idx >= 0) {
      taskQueueRecords.value[idx] = record
    } else {
      taskQueueRecords.value = [record, ...taskQueueRecords.value]
    }
    taskQueueRecords.value = [...taskQueueRecords.value].sort((a, b) => b.id - a.id)
  }

  function markTaskUnread(recordId: number) {
    if (!unreadTaskIds.value.includes(recordId)) {
      unreadTaskIds.value = [...unreadTaskIds.value, recordId]
    }
  }

  function markTaskRead(recordId: number) {
    unreadTaskIds.value = unreadTaskIds.value.filter((id) => id !== recordId)
  }

  function cancelPolling() {
    pollVersion++
    pollingRecordIds.value = []
  }

  function startPolling(recordId: number) {
    if (!pollingRecordIds.value.includes(recordId)) {
      pollingRecordIds.value = [...pollingRecordIds.value, recordId]
    }
  }

  function stopPolling(recordId: number) {
    pollingRecordIds.value = pollingRecordIds.value.filter((id) => id !== recordId)
  }

  /** 上传图片并识别 */
  async function uploadAndRecognize(file: File): Promise<OcrRecord | null> {
    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await uploadOcrImage(formData)
      const record = res.data.data!
      upsertRecord(record)
      upsertTaskQueueRecord(record)
      return record
    } catch {
      return null
    } finally {
      uploading.value = false
    }
  }

  async function refreshRecord(recordId: number, activate = false): Promise<OcrRecord | null> {
    try {
      const res = await getOcrRecord(recordId)
      const record = res.data.data!
      if (activate && currentRecord.value?.id === record.id) {
        currentRecord.value = record
      }
      upsertRecord(record)
      upsertTaskQueueRecord(record)
      return record
    } catch {
      return null
    }
  }

  async function pollRecordUntilDone(recordId: number): Promise<OcrRecord | null> {
    const version = pollVersion
    const deadline = Date.now() + OCR_POLL_TIMEOUT_MS
    startPolling(recordId)
    try {
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, OCR_POLL_INTERVAL_MS))
        if (version !== pollVersion) return null

        const record = await refreshRecord(recordId)
        if (!record) {
          continue
        }
        if (record.status !== 'pending') {
          if (currentRecord.value?.id !== record.id) {
            markTaskUnread(record.id)
          }
          return record
        }
      }
      ElMessage.warning('识别仍在进行中，可稍后在历史记录中查看结果')
      return taskQueueRecords.value.find((record) => record.id === recordId) || null
    } finally {
      if (version === pollVersion) {
        stopPolling(recordId)
      }
    }
  }

  /** 确认识别结果入库 */
  async function confirmRecord(
    recordId: number,
    data: OcrConfirmRequest,
    notify = true,
  ): Promise<boolean> {
    try {
      const res = await confirmOcrRecord(recordId, data)
      if (notify) {
        ElMessage.success(res.data.data?.message || '识别结果已确认入库')
      }
      taskQueueRecords.value = taskQueueRecords.value.filter((r) => r.id !== recordId)
      markTaskRead(recordId)
      if (currentRecord.value?.id === recordId) {
        currentRecord.value = null
      }
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

  async function loadTaskQueue() {
    const statuses: OcrStatus[] = ['pending', 'success', 'failed']
    const responses = await Promise.all(
      statuses.map((status) => getOcrList({ status, page: 1, page_size: 100 })),
    )
    taskQueueRecords.value = responses
      .flatMap((res) => res.data.data?.items || [])
      .sort((a, b) => b.id - a.id)
  }

  /** 删除 OCR 记录 */
  async function deleteRecord(id: number, notify = true): Promise<boolean> {
    try {
      await deleteOcrRecord(id)
      if (notify) {
        ElMessage.success('删除成功')
      }
      records.value = records.value.filter((r) => r.id !== id)
      taskQueueRecords.value = taskQueueRecords.value.filter((r) => r.id !== id)
      markTaskRead(id)
      total.value--
      // 若删除的是当前正在查看的记录，同步清空右侧面板，防止后续入库失败
      if (currentRecord.value?.id === id) {
        currentRecord.value = null
      }
      return true
    } catch {
      return false
    }
  }

  return {
    currentRecord,
    records,
    taskQueueRecords,
    unreadTaskIds,
    total,
    loading,
    uploading,
    recognizing,
    pollingRecordIds,
    uploadAndRecognize,
    refreshRecord,
    pollRecordUntilDone,
    cancelPolling,
    markTaskRead,
    confirmRecord,
    loadRecords,
    loadTaskQueue,
    deleteRecord,
  }
})
