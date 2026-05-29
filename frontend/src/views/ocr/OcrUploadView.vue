<template>
  <div class="page-wrap">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">OCR 药品识别</h2>
        <p class="page-subtitle">上传药品包装图片，自动提取药品信息并入库</p>
      </div>
    </div>

    <!-- 主工作区 -->
    <div class="work-area">
      <!-- 左侧：上传区 -->
      <div class="upload-panel card">
        <p class="panel-label">上传图片</p>

        <!-- 拖拽上传区 -->
        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': isDragging, 'drop-zone--has-image': previewUrls.length > 0 }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
          @click="triggerFilePicker"
        >
          <template v-if="previewUrls.length === 0">
            <el-icon class="drop-icon"><UploadFilled /></el-icon>
            <p class="drop-text">拖拽图片至此，或<span class="drop-link">点击选择</span></p>
            <p class="drop-hint">同一药盒不同面可多选，最多 6 张，单张最大 10 MB</p>
          </template>

          <template v-else>
            <div class="preview-grid" :class="{ 'preview-grid--single': previewUrls.length === 1 }">
              <img
                v-for="(url, index) in previewUrls"
                :key="url"
                :src="url"
                :alt="`预览图 ${index + 1}`"
                class="preview-img"
              />
            </div>
            <div class="preview-overlay">
              <el-icon class="overlay-icon"><RefreshRight /></el-icon>
              <span>{{ selectedFiles.length }} 张，重新选择</span>
            </div>
          </template>
        </div>

        <input
          ref="fileInput"
          type="file"
          multiple
          accept="image/jpeg,image/png,image/bmp,image/webp"
          style="display: none"
          @change="handleFileChange"
        />

        <!-- 识别按钮 -->
        <el-button
          type="primary"
          :loading="ocrStore.uploading"
          :disabled="selectedFiles.length === 0 || ocrStore.uploading"
          class="recognize-btn"
          @click="startRecognize"
        >
          {{ ocrStore.uploading ? '上传中...' : '开始识别' }}
        </el-button>
      </div>

      <!-- 右侧：识别结果 -->
      <div class="result-panel card" :class="{ 'result-panel--empty': !ocrStore.currentRecord }">
        <template v-if="!ocrStore.currentRecord">
          <div class="result-empty">
            <el-icon class="empty-icon"><DocumentChecked /></el-icon>
            <p>上传并识别图片后，在此处核对并编辑结果</p>
          </div>
        </template>

        <template v-else>
          <div class="result-header">
            <p class="panel-label">核对识别结果</p>
            <el-tag
              :type="statusMap[ocrStore.currentRecord.status].type as any"
              size="small"
              round
            >
              {{ statusMap[ocrStore.currentRecord.status].label }}
            </el-tag>
          </div>

          <!-- 识别中提示 -->
          <el-alert
            v-if="ocrStore.currentRecord.status === 'pending'"
            title="识别任务已提交，正在后台处理，完成后会自动刷新结果"
            type="info"
            show-icon
            :closable="false"
            class="mb-16"
          />

          <el-alert
            v-if="ocrStore.currentRecord.status === 'paused'"
            title="识别任务已暂停，可在任务队列中点击继续恢复识别"
            type="warning"
            show-icon
            :closable="false"
            class="mb-16"
          />

          <div
            v-if="ocrStore.currentRecord.status === 'pending' || ocrStore.currentRecord.status === 'paused'"
            class="pending-actions"
          >
            <el-button type="primary" plain @click="resetResult">
              返回上传图片
            </el-button>
          </div>

          <!-- 识别失败提示 -->
          <el-alert
            v-if="ocrStore.currentRecord.status === 'failed'"
            :title="ocrStore.currentRecord.error_message || '识别失败，请重试'"
            type="error"
            :closable="false"
            class="mb-16"
          />

          <el-alert
            v-if="requiresManualReview(ocrStore.currentRecord)"
            :title="manualReviewMessage(ocrStore.currentRecord)"
            type="warning"
            show-icon
            :closable="false"
            class="mb-16"
          />

          <div v-if="recordImagePaths(ocrStore.currentRecord).length > 1" class="review-image-strip mb-16">
            <el-image
              v-for="(path, index) in recordImagePaths(ocrStore.currentRecord)"
              :key="`${ocrStore.currentRecord.id}-${path}`"
              :src="`/uploads/${path}`"
              :preview-src-list="recordPreviewSrcList(ocrStore.currentRecord)"
              :initial-index="index"
              fit="cover"
              class="review-thumb"
              preview-teleported
            />
          </div>

          <!-- 字段完整度 -->
          <div v-if="ocrStore.currentRecord.confidence != null" class="confidence-row">
            <span class="confidence-label">字段完整度</span>
            <el-progress
              :percentage="Math.round((ocrStore.currentRecord.confidence || 0) * 100)"
              :color="confidenceColor(ocrStore.currentRecord.confidence || 0)"
              :stroke-width="8"
              class="confidence-bar"
            />
            <span class="confidence-source-tag is-estimated">
              按字段计算
            </span>
          </div>

          <!-- 原始 OCR 文本（调试用，可折叠） -->
          <el-collapse v-if="ocrStore.currentRecord.raw_text" class="raw-text-collapse mb-16">
            <el-collapse-item title="原始识别文本（调试）" name="raw">
              <pre class="raw-text-pre">{{ ocrStore.currentRecord.raw_text }}</pre>
            </el-collapse-item>
          </el-collapse>

          <!-- 可编辑确认表单 -->
          <el-form
            v-if="ocrStore.currentRecord.status !== 'pending' && ocrStore.currentRecord.status !== 'paused'"
            ref="confirmFormRef"
            :model="confirmForm"
            :rules="confirmRules"
            label-position="top"
            class="confirm-form"
          >
            <div class="form-section-title">药品信息</div>

            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="药品名称" prop="drug_name">
                  <el-input v-model="confirmForm.drug_name" placeholder="请输入药品名称" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="批准文号">
                  <el-input v-model="confirmForm.approval_number" placeholder="国药准字…" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="规格">
                  <el-input v-model="confirmForm.specification" placeholder="如 0.25g×24粒" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="生产企业">
                  <el-input v-model="confirmForm.manufacturer" placeholder="生产企业名称" />
                </el-form-item>
              </el-col>
            </el-row>

            <div class="form-section-title">批次信息</div>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="批号" prop="batch_number">
                  <el-input v-model="confirmForm.batch_number" placeholder="生产批号" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="数量">
                  <el-input-number
                    v-model="confirmForm.quantity"
                    :min="0"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="生产日期">
                  <el-date-picker
                    v-model="confirmForm.production_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="生产日期"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="有效期至" prop="expiry_date">
                  <el-date-picker
                    v-model="confirmForm.expiry_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="有效期至"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="单位">
                  <el-select v-model="confirmForm.unit" style="width: 100%">
                    <el-option label="盒" value="盒" />
                    <el-option label="瓶" value="瓶" />
                    <el-option label="袋" value="袋" />
                    <el-option label="支" value="支" />
                    <el-option label="粒" value="粒" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <div class="form-actions">
              <el-button @click="resetResult">取消</el-button>
              <el-button
                type="primary"
                :loading="confirming"
                :disabled="ocrStore.currentRecord.status === 'failed'"
                @click="handleConfirm"
              >
                {{ requiresManualReview(ocrStore.currentRecord) ? '人工核对后确认入库' : '确认入库' }}
              </el-button>
            </div>
          </el-form>
        </template>
      </div>
    </div>

    <!-- 入库任务队列 -->
    <div class="card task-queue-section">
      <div class="history-header">
        <p class="panel-label" style="margin: 0">入库任务队列</p>
        <div class="table-toolbar">
          <span class="queue-count">{{ ocrStore.taskQueueRecords.length }} 个待处理</span>
          <el-button
            type="primary"
            size="small"
            :disabled="batchConfirmableTaskSelection.length === 0"
            @click="handleBatchConfirm(taskSelection)"
          >
            批量确认
          </el-button>
          <el-button
            type="danger"
            size="small"
            plain
            :disabled="taskSelection.length === 0"
            @click="handleBatchDelete(taskSelection)"
          >
            批量删除
          </el-button>
        </div>
      </div>

      <el-table
        :data="ocrStore.taskQueueRecords"
        row-key="id"
        size="small"
        class="history-table"
        empty-text="暂无待处理 OCR 任务"
        @selection-change="handleTaskSelectionChange"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column width="36">
          <template #default="{ row }">
            <span
              v-if="row.status === 'pending'"
              class="queue-status-icon is-loading"
              aria-label="识别中"
            />
            <span
              v-else-if="ocrStore.unreadTaskIds.includes(row.id)"
              class="queue-status-icon is-unread"
              aria-label="未查看"
            />
          </template>
        </el-table-column>
        <el-table-column label="预览" width="72">
          <template #default="{ row }">
            <el-image
              :src="recordFirstImageUrl(row)"
              :preview-src-list="recordPreviewSrcList(row)"
              fit="cover"
              style="width: 48px; height: 48px; border-radius: 6px; cursor: zoom-in"
              preview-teleported
            />
          </template>
        </el-table-column>
        <el-table-column label="识别药品" min-width="140">
          <template #default="{ row }">
            <span v-if="row.extracted_data?.name" class="drug-name">
              {{ row.extracted_data.name }}
            </span>
            <span v-else class="no-data">—</span>
          </template>
        </el-table-column>
        <el-table-column label="批号" min-width="120">
          <template #default="{ row }">
            {{ row.extracted_data?.batch_number || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="有效期至" min-width="110">
          <template #default="{ row }">
            {{ row.extracted_data?.expiry_date || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status as OcrStatus].type as any" size="small" round>
              {{ statusMap[row.status as OcrStatus].label }}
            </el-tag>
            <el-tag
              v-if="requiresManualReview(row)"
              type="warning"
              size="small"
              round
              class="manual-review-tag"
            >
              需人工审核
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <div class="history-actions">
              <el-button
                type="primary"
                text
                size="small"
                @click="handleOpenQueueRecord(row)"
              >
                {{ historyActionLabel(row.status as OcrStatus) }}
              </el-button>
              <el-button
                v-if="row.status === 'pending'"
                type="warning"
                text
                size="small"
                @click="handlePause(row)"
              >
                暂停
              </el-button>
              <el-button
                v-if="row.status === 'paused'"
                type="success"
                text
                size="small"
                @click="handleResume(row)"
              >
                继续
              </el-button>
              <el-button
                type="danger"
                text
                size="small"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- OCR 历史记录 -->
    <div class="card history-section">
      <div class="history-header">
        <p class="panel-label" style="margin: 0">历史识别记录</p>
        <div class="table-toolbar">
          <el-button
            type="primary"
            size="small"
            :disabled="batchConfirmableHistorySelection.length === 0"
            @click="handleBatchConfirm(historySelection)"
          >
            批量确认
          </el-button>
          <el-button
            type="danger"
            size="small"
            plain
            :disabled="historySelection.length === 0"
            @click="handleBatchDelete(historySelection)"
          >
            批量删除
          </el-button>
          <el-select
            v-model="filterStatus"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            size="small"
            @change="loadHistory"
          >
            <el-option
              v-for="(v, k) in statusMap"
              :key="k"
              :label="v.label"
              :value="k"
            />
          </el-select>
        </div>
      </div>

      <el-table
        :data="ocrStore.records"
        v-loading="ocrStore.loading"
        row-key="id"
        size="small"
        class="history-table"
        @selection-change="handleHistorySelectionChange"
      >
        <el-table-column type="selection" width="42" :selectable="isHistoryRowSelectable" />
        <el-table-column label="ID" prop="id" width="64" />
        <el-table-column label="预览" width="72">
          <template #default="{ row }">
            <el-image
              :src="recordFirstImageUrl(row)"
              :preview-src-list="recordPreviewSrcList(row)"
              fit="cover"
              style="width: 48px; height: 48px; border-radius: 6px; cursor: zoom-in"
              preview-teleported
            />
          </template>
        </el-table-column>
        <el-table-column label="识别药品" min-width="140">
          <template #default="{ row }">
            <span v-if="row.extracted_data?.name" class="drug-name">
              {{ row.extracted_data.name }}
            </span>
            <span v-else class="no-data">—</span>
          </template>
        </el-table-column>
        <el-table-column label="批号" min-width="120">
          <template #default="{ row }">
            {{ row.extracted_data?.batch_number || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="有效期至" min-width="110">
          <template #default="{ row }">
            {{ row.extracted_data?.expiry_date || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="完整度" width="140">
          <template #default="{ row }">
            <span v-if="row.confidence != null">
              {{ Math.round(row.confidence * 100) }}%
              <span class="confidence-source-tag is-estimated">
                按字段计算
              </span>
            </span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status as OcrStatus].type as any" size="small" round>
              {{ statusMap[row.status as OcrStatus].label }}
            </el-tag>
            <el-tag
              v-if="requiresManualReview(row)"
              type="warning"
              size="small"
              round
              class="manual-review-tag"
            >
              需人工审核
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="识别时间" min-width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <div class="history-actions">
              <el-button
                v-if="row.status !== 'confirmed'"
                type="primary"
                text
                size="small"
                @click="handleOpenHistoryRecord(row)"
              >
                {{ historyActionLabel(row.status as OcrStatus) }}
              </el-button>
              <el-button
                type="danger"
                text
                size="small"
                :disabled="row.status === 'confirmed' && !authStore.isAdmin"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="20"
          :total="ocrStore.total"
          layout="total, prev, pager, next"
          small
          @current-change="loadHistory"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, RefreshRight, DocumentChecked } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

import { useOcrStore } from '@/stores/ocr'
import { useAuthStore } from '@/stores/auth'
import type { OcrStatus, OcrConfirmRequest, OcrRecord } from '@/types/ocr'
import { OCR_STATUS_MAP, isBatchConfirmAllowed, isManualReviewRequired } from '@/types/ocr'

const ocrStore = useOcrStore()
const authStore = useAuthStore()
const statusMap = OCR_STATUS_MAP

// --- 上传区状态 ---
const isDragging = ref(false)
const selectedFiles = ref<File[]>([])
const previewUrls = ref<string[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

// --- 确认表单 ---
const confirmFormRef = ref<FormInstance | null>(null)
const confirming = ref(false)
const confirmForm = reactive<OcrConfirmRequest>({
  drug_name: '',
  approval_number: '',
  manufacturer: '',
  specification: '',
  batch_number: '',
  production_date: undefined,
  expiry_date: '',
  quantity: 0,
  unit: '盒',
})

const confirmRules: FormRules = {
  drug_name:    [{ required: true, message: '请输入药品名称', trigger: 'blur' }],
  batch_number: [{ required: true, message: '请输入批号', trigger: 'blur' }],
  expiry_date:  [{ required: true, message: '请选择有效期', trigger: 'change' }],
}

// --- 历史记录 ---
const filterStatus = ref<string | undefined>(undefined)
const currentPage = ref(1)
const taskSelection = ref<OcrRecord[]>([])
const historySelection = ref<OcrRecord[]>([])
const batchConfirmableTaskSelection = computed(() => taskSelection.value.filter(isBatchConfirmAllowed))
const batchConfirmableHistorySelection = computed(() => historySelection.value.filter(isBatchConfirmAllowed))

// -------- 方法 --------

function triggerFilePicker() {
  fileInput.value?.click()
}

function handleFileChange(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  if (files.length > 0) {
    setFiles(files)
    // 清空 input 原生值，使同一文件下次仍可触发 @change
    ;(e.target as HTMLInputElement).value = ''
  }
}

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length > 0) setFiles(files)
}

function setFiles(files: File[]) {
  clearSelectedFile()
  selectedFiles.value = files
  previewUrls.value = files.map((file) => URL.createObjectURL(file))
}

async function startRecognize() {
  if (selectedFiles.value.length === 0) return
  const record = await ocrStore.uploadAndRecognize([...selectedFiles.value])
  if (record) {
    // 新记录已写入 DB，立即刷新历史列表使其可见（用户取消时不需再刷新页面）
    loadHistory()
    clearSelectedFile()

    if (record.status === 'pending') {
      ElMessage.success('识别任务已提交，完成后会自动刷新结果')
      watchQueueRecord(record.id)
      return
    }

    if (record.status === 'failed') {
      ElMessage.error('识别失败：' + (record.error_message || '请重试'))
    } else {
      ocrStore.markTaskRead(record.id)
      openRecordForReview(record)
    }
  }
}

function watchQueueRecord(recordId: number) {
  void ocrStore.pollRecordUntilDone(recordId).then((finalRecord) => {
    loadHistory()
    void ocrStore.loadTaskQueue()
    if (!finalRecord || finalRecord.status === 'pending') return
    if (finalRecord.status === 'success') {
      ElMessage.success('识别完成，已加入入库任务队列')
    } else if (finalRecord.status === 'failed') {
      ElMessage.error('识别失败，请在入库任务队列中查看')
    }
  })
}

function clearSelectedFile() {
  previewUrls.value
    .filter((url) => url.startsWith('blob:'))
    .forEach((url) => URL.revokeObjectURL(url))
  selectedFiles.value = []
  previewUrls.value = []
  if (fileInput.value) fileInput.value.value = ''
}

function fillConfirmForm(record: OcrRecord) {
  const d = record.extracted_data || {}
  confirmForm.drug_name = d.name || ''
  confirmForm.approval_number = d.approval_number || ''
  confirmForm.manufacturer = d.manufacturer || ''
  confirmForm.specification = d.specification || ''
  confirmForm.batch_number = d.batch_number || ''
  confirmForm.production_date = d.production_date || undefined
  confirmForm.expiry_date = d.expiry_date || ''
  confirmForm.quantity = d.quantity ?? 0
  confirmForm.unit = '盒'
}

function textValue(value: unknown): string {
  if (value == null) return ''
  return String(value).trim()
}

function buildConfirmPayload(record: OcrRecord): OcrConfirmRequest | null {
  const data = record.extracted_data || {}
  const drugName = textValue(data.name)
  const batchNumber = textValue(data.batch_number)
  const expiryDate = textValue(data.expiry_date)

  if (!drugName || !batchNumber || !expiryDate) {
    return null
  }

  return {
    drug_name: drugName,
    approval_number: textValue(data.approval_number) || undefined,
    manufacturer: textValue(data.manufacturer) || undefined,
    specification: textValue(data.specification) || undefined,
    batch_number: batchNumber,
    production_date: textValue(data.production_date) || undefined,
    expiry_date: expiryDate,
    quantity: data.quantity ?? 0,
    unit: '盒',
  }
}

function historyActionLabel(status: OcrStatus): string {
  if (status === 'success') return '确认'
  return '查看'
}

function handleTaskSelectionChange(rows: OcrRecord[]) {
  taskSelection.value = rows
}

function handleHistorySelectionChange(rows: OcrRecord[]) {
  historySelection.value = rows
}

function isHistoryRowSelectable(row: OcrRecord): boolean {
  return authStore.isAdmin || row.status !== 'confirmed'
}

function recordImagePaths(record?: OcrRecord | null): string[] {
  if (!record) return []
  if (record.image_paths?.length) return record.image_paths
  if (record.images?.length) {
    return [...record.images]
      .sort((a, b) => a.image_index - b.image_index)
      .map((image) => image.image_path)
  }
  return record.image_path ? [record.image_path] : []
}

function recordPreviewSrcList(record?: OcrRecord | null): string[] {
  return recordImagePaths(record).map((path) => `/uploads/${path}`)
}

function recordFirstImageUrl(record: OcrRecord): string {
  return recordPreviewSrcList(record)[0] || ''
}

function requiresManualReview(record?: OcrRecord | null): boolean {
  return !!record && record.status === 'success' && isManualReviewRequired(record)
}

function manualReviewMessage(record: OcrRecord): string {
  return record.extracted_data?.multi_image?.consistency?.message
    || '多张图片缺少可交叉验证字段，AI 仅提供辅助意见，请人工核对所有照片后再确认入库。'
}

function openRecordForReview(record: OcrRecord) {
  ocrStore.currentRecord = record
  fillConfirmForm(record)
}

async function handleOpenQueueRecord(row: OcrRecord) {
  ocrStore.markTaskRead(row.id)
  clearSelectedFile()
  previewUrls.value = recordPreviewSrcList(row)

  const refreshed = await ocrStore.refreshRecord(row.id)
  const record = refreshed || row
  ocrStore.currentRecord = record
  previewUrls.value = recordPreviewSrcList(record)

  if (record.status === 'pending') {
    ElMessage.info('正在查看该识别任务，完成后会自动刷新当前面板')
    const finalRecord = await ocrStore.pollRecordUntilDone(record.id)
    loadHistory()
    void ocrStore.loadTaskQueue()
    if (!finalRecord || finalRecord.status === 'pending') return
    if (ocrStore.currentRecord?.id !== finalRecord.id) return
    ocrStore.currentRecord = finalRecord
    if (finalRecord.status === 'success') {
      fillConfirmForm(finalRecord)
      ElMessage.success('识别完成，请核对并确认入库')
    } else if (finalRecord.status === 'failed') {
      fillConfirmForm(finalRecord)
      ElMessage.error('识别失败：' + (finalRecord.error_message || '请重试'))
    }
    return
  }

  if (record.status === 'paused') {
    openRecordForReview(record)
    ElMessage.info('该识别任务已暂停，可在任务队列中点击继续')
    return
  }

  if (record.status === 'success') {
    openRecordForReview(record)
    ElMessage.success('已载入待确认记录')
    return
  }

  if (record.status === 'failed') {
    openRecordForReview(record)
    ElMessage.error('识别失败：' + (record.error_message || '请重试'))
  }
}

async function handleOpenHistoryRecord(row: OcrRecord) {
  await handleOpenQueueRecord(row)
}

async function handlePause(row: OcrRecord) {
  const record = await ocrStore.pauseRecord(row.id)
  if (!record) return
  await refreshTables()
}

async function handleResume(row: OcrRecord) {
  const record = await ocrStore.resumeRecord(row.id)
  if (!record) return
  await refreshTables()
  watchQueueRecord(record.id)
}

async function handleConfirm() {
  if (!ocrStore.currentRecord) return
  await confirmFormRef.value?.validate(async (valid) => {
    if (!valid) return
    if (requiresManualReview(ocrStore.currentRecord)) {
      try {
        await ElMessageBox.confirm(
          'AI 仅提供辅助意见。请确认已人工核对所有照片与识别字段后再入库。',
          '人工审核确认',
          { type: 'warning' },
        )
      } catch {
        return
      }
    }
    confirming.value = true
    const ok = await ocrStore.confirmRecord(ocrStore.currentRecord!.id, { ...confirmForm })
    confirming.value = false
    if (ok) {
      resetResult()
      loadHistory()
      ocrStore.loadTaskQueue()
    }
  })
}

async function handleBatchConfirm(rows: OcrRecord[]) {
  const candidates = rows.filter(isBatchConfirmAllowed)
  const ready = candidates
    .map((row) => ({ row, payload: buildConfirmPayload(row) }))
    .filter((item): item is { row: OcrRecord; payload: OcrConfirmRequest } => item.payload != null)

  const missing = candidates.length - ready.length
  const skipped = rows.length - candidates.length + missing
  const reviewRequired = rows.filter(requiresManualReview).length

  if (ready.length === 0) {
    ElMessage.warning(
      reviewRequired > 0
        ? '需人工审核的多图记录不能批量确认，请单独核对后入库'
        : '没有可批量确认的待确认记录；缺少必填字段的记录请先单独核对',
    )
    return
  }

  try {
    await ElMessageBox.confirm(
      reviewRequired > 0
        ? `将确认 ${ready.length} 条记录，跳过 ${reviewRequired} 条需人工审核的多图记录。继续？`
        : skipped > 0
        ? `将确认 ${ready.length} 条记录，跳过 ${skipped} 条不可确认或缺少必填字段的记录。继续？`
        : `确认将选中的 ${ready.length} 条记录批量入库？`,
      '批量确认',
      { type: 'warning' },
    )
  } catch {
    return
  }

  let success = 0
  const failedMessages: string[] = []
  for (const item of ready) {
    if (await ocrStore.confirmRecord(item.row.id, item.payload, false, {
      suppressErrorMessage: true,
      onError: (message) => failedMessages.push(message),
    })) {
      success++
    }
  }

  taskSelection.value = []
  historySelection.value = []
  await refreshTables()

  if (success === ready.length) {
    ElMessage.success(`已批量确认 ${success} 条记录`)
  } else {
    const firstReason = failedMessages[0] ? `。首条失败原因：${failedMessages[0]}` : ''
    ElMessage.warning(`已确认 ${success} 条，${ready.length - success} 条失败${firstReason}`)
  }
}

async function handleBatchDelete(rows: OcrRecord[]) {
  const deletable = rows.filter((row) => authStore.isAdmin || row.status !== 'confirmed')
  const skipped = rows.length - deletable.length

  if (deletable.length === 0) {
    ElMessage.warning('没有可删除的记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      skipped > 0
        ? `将删除 ${deletable.length} 条记录，跳过 ${skipped} 条无权限删除的已入库记录。继续？`
        : `确认删除选中的 ${deletable.length} 条记录？`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }

  let success = 0
  for (const row of deletable) {
    if (await ocrStore.deleteRecord(row.id, false)) {
      success++
    }
  }

  taskSelection.value = []
  historySelection.value = []
  await refreshTables()

  if (success === deletable.length) {
    ElMessage.success(`已批量删除 ${success} 条记录`)
  } else {
    ElMessage.warning(`已删除 ${success} 条，${deletable.length - success} 条失败`)
  }
}

function resetResult() {
  ocrStore.currentRecord = null
  clearSelectedFile()
}

async function handleDelete(row: { id: number; status: string }) {
  try {
    await ElMessageBox.confirm('确认删除该识别记录？', '提示', { type: 'warning' })
    await ocrStore.deleteRecord(row.id)
    ocrStore.loadTaskQueue()
  } catch {
    // 用户点击弹框"取消"，忽略
  }
}

function loadHistory() {
  return ocrStore.loadRecords({
    status: filterStatus.value || undefined,
    page: currentPage.value,
    page_size: 20,
  })
}

function loadQueue() {
  return ocrStore.loadTaskQueue()
}

async function refreshTables() {
  await Promise.all([loadHistory(), loadQueue()])
}

function confidenceColor(val: number): string {
  if (val >= 0.8) return '#22c55e'
  if (val >= 0.5) return '#f59e0b'
  return '#ef4444'
}

function formatDate(iso: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  loadHistory()
  loadQueue()
})
onBeforeUnmount(() => {
  ocrStore.cancelPolling()
})
</script>

<style scoped>
.page-wrap {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 页头 */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 4px;
}
.page-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* 卡片 */
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 24px;
}

/* 主工作区：左右分栏 */
.work-area {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 24px;
}

/* 上传面板 */
.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.panel-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 4px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.drop-zone {
  position: relative;
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
  min-height: 220px;
  overflow: hidden;
}
.drop-zone:hover,
.drop-zone--active {
  border-color: #3b82f6;
  background: #eff6ff;
}
.drop-zone--has-image {
  border-style: solid;
  border-color: #e5e7eb;
  padding: 0;
}
.drop-icon {
  font-size: 40px;
  color: #9ca3af;
}
.drop-text {
  font-size: 14px;
  color: #374151;
  margin: 0;
}
.drop-link {
  color: #3b82f6;
  margin-left: 2px;
}
.drop-hint {
  font-size: 12px;
  color: #9ca3af;
  margin: 0;
}

.preview-grid {
  width: 100%;
  height: 220px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(0, 1fr);
  gap: 6px;
  padding: 6px;
}
.preview-grid--single {
  grid-template-columns: 1fr;
}
.preview-img {
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: contain;
  display: block;
  background: #f9fafb;
  border-radius: 6px;
}
.preview-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.drop-zone:hover .preview-overlay {
  opacity: 1;
}
.overlay-icon {
  font-size: 28px;
}
.recognize-btn {
  width: 100%;
}

/* 识别结果面板 */
.result-panel {
  display: flex;
  flex-direction: column;
}
.result-panel--empty {
  align-items: center;
  justify-content: center;
}
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #9ca3af;
  padding: 48px 0;
}
.empty-icon {
  font-size: 48px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.confidence-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.confidence-label {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}
.confidence-bar {
  flex: 1;
}
.confidence-source-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
  &.is-real {
    color: #15803d;
    background: #dcfce7;
  }
  &.is-estimated {
    color: #92400e;
    background: #fef3c7;
  }
}

.form-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f3f4f6;
}
.form-section-title + .form-section-title {
  margin-top: 8px;
}
.confirm-form {
  flex: 1;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.pending-actions {
  display: flex;
  justify-content: flex-end;
}
.mb-16 {
  margin-bottom: 16px;
}

/* 原始文本折叠 */
.raw-text-collapse {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.raw-text-pre {
  font-size: 12px;
  color: #374151;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  padding: 8px 4px;
  background: #f9fafb;
  border-radius: 4px;
}

.review-image-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 8px;
}
.review-thumb {
  width: 100%;
  height: 72px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: zoom-in;
  background: #f9fafb;
}

/* 历史记录 */
.task-queue-section {
  padding: 20px 24px;
}
.history-section {
  padding: 20px 24px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.queue-count {
  font-size: 12px;
  color: #6b7280;
}
.queue-status-icon {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  vertical-align: middle;
}
.queue-status-icon.is-unread {
  background: #3b82f6;
}
.queue-status-icon.is-loading {
  width: 14px;
  height: 14px;
  border: 2px solid #bfdbfe;
  border-top-color: #3b82f6;
  animation: queue-spin 0.8s linear infinite;
}
.manual-review-tag {
  margin-left: 4px;
}
@keyframes queue-spin {
  to {
    transform: rotate(360deg);
  }
}
.history-table {
  border-radius: 6px;
  overflow: hidden;
}
.history-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.drug-name {
  font-weight: 500;
  color: #111827;
}
.no-data {
  color: #d1d5db;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
