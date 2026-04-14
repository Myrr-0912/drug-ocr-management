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
          :class="{ 'drop-zone--active': isDragging, 'drop-zone--has-image': previewUrl }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
          @click="triggerFilePicker"
        >
          <template v-if="!previewUrl">
            <el-icon class="drop-icon"><UploadFilled /></el-icon>
            <p class="drop-text">拖拽图片至此，或<span class="drop-link">点击选择</span></p>
            <p class="drop-hint">支持 JPG / PNG / BMP / WebP，最大 10 MB</p>
          </template>

          <template v-else>
            <img :src="previewUrl" alt="预览图" class="preview-img" />
            <div class="preview-overlay">
              <el-icon class="overlay-icon"><RefreshRight /></el-icon>
              <span>重新选择</span>
            </div>
          </template>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/bmp,image/webp"
          style="display: none"
          @change="handleFileChange"
        />

        <!-- 识别按钮 -->
        <el-button
          type="primary"
          :loading="ocrStore.uploading"
          :disabled="!selectedFile"
          class="recognize-btn"
          @click="startRecognize"
        >
          {{ ocrStore.uploading ? '识别中...' : '开始识别' }}
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

          <!-- 识别失败提示 -->
          <el-alert
            v-if="ocrStore.currentRecord.status === 'failed'"
            :title="ocrStore.currentRecord.error_message || '识别失败，请重试'"
            type="error"
            :closable="false"
            class="mb-16"
          />

          <!-- 置信度 -->
          <div v-if="ocrStore.currentRecord.confidence != null" class="confidence-row">
            <span class="confidence-label">识别置信度</span>
            <el-progress
              :percentage="Math.round((ocrStore.currentRecord.confidence || 0) * 100)"
              :color="confidenceColor(ocrStore.currentRecord.confidence || 0)"
              :stroke-width="8"
              class="confidence-bar"
            />
            <span class="confidence-source-tag" :class="ocrStore.currentRecord.extracted_data?.confidence_estimated ? 'is-estimated' : 'is-real'">
              {{ ocrStore.currentRecord.extracted_data?.confidence_estimated ? '估算值' : 'API 真实数据' }}
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
                确认入库
              </el-button>
            </div>
          </el-form>
        </template>
      </div>
    </div>

    <!-- OCR 历史记录 -->
    <div class="card history-section">
      <div class="history-header">
        <p class="panel-label" style="margin: 0">历史识别记录</p>
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

      <el-table
        :data="ocrStore.records"
        v-loading="ocrStore.loading"
        row-key="id"
        size="small"
        class="history-table"
      >
        <el-table-column label="ID" prop="id" width="64" />
        <el-table-column label="预览" width="72">
          <template #default="{ row }">
            <el-image
              :src="`/uploads/${row.image_path}`"
              :preview-src-list="[`/uploads/${row.image_path}`]"
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
        <el-table-column label="置信度" width="140">
          <template #default="{ row }">
            <span v-if="row.confidence != null">
              {{ Math.round(row.confidence * 100) }}%
              <span class="confidence-source-tag" :class="row.extracted_data?.confidence_estimated ? 'is-estimated' : 'is-real'">
                {{ row.extracted_data?.confidence_estimated ? '估算值' : 'API 真实数据' }}
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
          </template>
        </el-table-column>
        <el-table-column label="识别时间" min-width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              text
              size="small"
              :disabled="row.status === 'confirmed'"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, RefreshRight, DocumentChecked } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

import { useOcrStore } from '@/stores/ocr'
import type { OcrStatus, OcrConfirmRequest } from '@/types/ocr'
import { OCR_STATUS_MAP } from '@/types/ocr'

const ocrStore = useOcrStore()
const statusMap = OCR_STATUS_MAP

// --- 上传区状态 ---
const isDragging = ref(false)
const selectedFile = ref<File | null>(null)
const previewUrl = ref<string>('')
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

// -------- 方法 --------

function triggerFilePicker() {
  fileInput.value?.click()
}

function handleFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    setFile(file)
    // 清空 input 原生值，使同一文件下次仍可触发 @change
    ;(e.target as HTMLInputElement).value = ''
  }
}

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) setFile(file)
}

function setFile(file: File) {
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  // 清除上次识别结果
  ocrStore.currentRecord = null
}

async function startRecognize() {
  if (!selectedFile.value) return
  const record = await ocrStore.uploadAndRecognize(selectedFile.value)
  if (record) {
    // 将识别结果预填入表单
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

    // 新记录已写入 DB，立即刷新历史列表使其可见（用户取消时不需再刷新页面）
    loadHistory()

    if (record.status === 'failed') {
      ElMessage.error('识别失败：' + (record.error_message || '请重试'))
    } else {
      ElMessage.success('识别完成，请核对并确认入库')
    }
  }
}

async function handleConfirm() {
  if (!ocrStore.currentRecord) return
  await confirmFormRef.value?.validate(async (valid) => {
    if (!valid) return
    confirming.value = true
    const ok = await ocrStore.confirmRecord(ocrStore.currentRecord!.id, { ...confirmForm })
    confirming.value = false
    if (ok) {
      resetResult()
      loadHistory()
    }
  })
}

function resetResult() {
  ocrStore.currentRecord = null
  selectedFile.value = null
  previewUrl.value = ''
  // 清空 input 的原生值，确保选同一文件时仍能触发 @change
  if (fileInput.value) fileInput.value.value = ''
}

async function handleDelete(row: { id: number; status: string }) {
  try {
    await ElMessageBox.confirm('确认删除该识别记录？', '提示', { type: 'warning' })
    await ocrStore.deleteRecord(row.id)
  } catch {
    // 用户点击弹框"取消"，忽略
  }
}

function loadHistory() {
  ocrStore.loadRecords({
    status: filterStatus.value || undefined,
    page: currentPage.value,
    page_size: 20,
  })
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

onMounted(loadHistory)
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

.preview-img {
  width: 100%;
  height: 220px;
  object-fit: contain;
  display: block;
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

/* 历史记录 */
.history-section {
  padding: 20px 24px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.history-table {
  border-radius: 6px;
  overflow: hidden;
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
