<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">批次管理</h2>
        <p class="page-subtitle">管理药品批次信息，追踪批号与有效期</p>
      </div>
      <el-button
        v-if="authStore.isPharmacist"
        type="primary"
        :icon="Plus"
        @click="openDialog()"
      >
        新建批次
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索批号..."
        clearable
        :prefix-icon="Search"
        class="search-input"
        @input="onSearch"
        @clear="onSearch"
      />
      <el-select
        v-model="query.status"
        placeholder="全部状态"
        clearable
        class="filter-select"
        @change="onSearch"
      >
        <el-option
          v-for="(label, val) in BATCH_STATUS_LABEL"
          :key="val"
          :label="label"
          :value="val"
        />
      </el-select>
    </div>

    <!-- 表格 -->
    <div class="card table-card">
      <el-table
        v-loading="batchesStore.loading"
        :data="batchesStore.list"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="drug_name" label="药品名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="batch_number" label="批号" min-width="140" />
        <el-table-column prop="production_date" label="生产日期" width="120">
          <template #default="{ row }">
            {{ row.production_date ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="expiry_date" label="有效期至" width="120" />
        <el-table-column prop="quantity" label="库存量" width="100">
          <template #default="{ row }">
            <span :class="row.quantity === 0 ? 'qty-zero' : 'qty-normal'">
              {{ row.quantity }} {{ row.unit }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="(BATCH_STATUS_TAG[row.status as BatchStatus] as any)" size="small">
              {{ BATCH_STATUS_LABEL[row.status as BatchStatus] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="authStore.isPharmacist"
              text
              type="primary"
              size="small"
              @click="openDialog(row)"
            >
              编辑
            </el-button>
            <el-popconfirm
              v-if="authStore.isPharmacist"
              title="仅可删除库存量为 0 的批次，确认删除？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              confirm-button-type="danger"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="batchesStore.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @change="loadList"
        />
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingBatch ? '编辑批次' : '新建批次'"
      width="480px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
        class="batch-form"
      >
        <!-- 新建时选择药品，编辑时只读显示 -->
        <el-form-item v-if="!editingBatch" label="所属药品" prop="drug_id">
          <el-select
            v-model="form.drug_id"
            placeholder="请选择药品"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="d in drugOptions"
              :key="d.id"
              :label="d.name"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="所属药品">
          <span class="form-readonly">{{ editingBatch.drug_name }}</span>
        </el-form-item>

        <el-form-item label="批号" prop="batch_number">
          <el-input v-model="form.batch_number" placeholder="如：20240101" />
        </el-form-item>
        <el-form-item label="生产日期">
          <el-date-picker
            v-model="form.production_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择生产日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="有效期至" prop="expiry_date">
          <el-date-picker
            v-model="form.expiry_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择有效期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="!editingBatch" label="初始库存" prop="quantity">
          <el-input-number v-model="form.quantity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="单位" prop="unit">
          <el-select v-model="form.unit" style="width: 100%">
            <el-option v-for="u in UNITS" :key="u" :label="u" :value="u" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ editingBatch ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onActivated } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useBatchesStore } from '@/stores/batches'
import { getDrugList } from '@/api/drugs'
import type { Batch, BatchStatus } from '@/types/batch'
import { BATCH_STATUS_LABEL, BATCH_STATUS_TAG } from '@/types/batch'

const UNITS = ['盒', '瓶', '袋', '支', '片', '粒', '克', '毫升']

const authStore = useAuthStore()
const batchesStore = useBatchesStore()

const query = reactive({
  keyword: '',
  status: '' as any,
  page: 1,
  page_size: 20,
})

const dialogVisible = ref(false)
const submitting = ref(false)
const editingBatch = ref<Batch | null>(null)
const formRef = ref<FormInstance>()

/** 药品下拉选项 */
const drugOptions = ref<{ id: number; name: string }[]>([])

const form = reactive({
  drug_id: 0,
  batch_number: '',
  production_date: '' as string | undefined,
  expiry_date: '',
  quantity: 0,
  unit: '盒',
})

const rules: FormRules = {
  drug_id: [{ required: true, message: '请选择药品', trigger: 'change' }],
  batch_number: [{ required: true, message: '请输入批号', trigger: 'blur' }],
  expiry_date: [{ required: true, message: '请选择有效期', trigger: 'change' }],
  quantity: [{ required: true, type: 'number', min: 0, message: '库存量不能为负', trigger: 'blur' }],
}

let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    query.page = 1
    loadList()
  }, 300)
}

async function loadList() {
  await batchesStore.fetchList({
    keyword: query.keyword || undefined,
    status: query.status || undefined,
    page: query.page,
    page_size: query.page_size,
  })
}

async function loadDrugOptions() {
  const resp = await getDrugList({ page: 1, page_size: 200 })
  drugOptions.value = resp.data.data!.items.map((d) => ({ id: d.id, name: d.name }))
}

function openDialog(batch: Batch | null = null) {
  editingBatch.value = batch
  if (batch) {
    form.batch_number = batch.batch_number
    form.production_date = batch.production_date ?? undefined
    form.expiry_date = batch.expiry_date
    form.unit = batch.unit
  }
  dialogVisible.value = true
}

function resetForm() {
  editingBatch.value = null
  form.drug_id = 0
  form.batch_number = ''
  form.production_date = undefined
  form.expiry_date = ''
  form.quantity = 0
  form.unit = '盒'
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingBatch.value) {
      await batchesStore.update(editingBatch.value.id, {
        batch_number: form.batch_number,
        production_date: form.production_date || undefined,
        expiry_date: form.expiry_date,
        unit: form.unit,
      })
      ElMessage.success('批次信息已更新')
    } else {
      await batchesStore.create({
        drug_id: form.drug_id,
        batch_number: form.batch_number,
        production_date: form.production_date || undefined,
        expiry_date: form.expiry_date,
        quantity: form.quantity,
        unit: form.unit,
      })
      ElMessage.success('批次已创建')
    }
    dialogVisible.value = false
    loadList()
  } catch {
    // 错误由 axios 拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await batchesStore.remove(id)
    ElMessage.success('删除成功')
  } catch {
    // 错误由 axios 拦截器统一处理
  }
}

onMounted(() => {
  loadList()
  loadDrugOptions()
})

// keep-alive 激活时重新拉取列表（从其他页面切换回来时更新数据）
onActivated(() => {
  loadList()
})
</script>

<style scoped>
.page-container {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 4px;
}

.page-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-input {
  width: 280px;
}

.filter-select {
  width: 140px;
}

.table-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.qty-normal {
  font-weight: 500;
  color: #111827;
}

.qty-zero {
  color: #9ca3af;
}

.pagination-wrap {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f3f4f6;
}

.batch-form {
  padding: 8px 0;
}

.form-readonly {
  font-size: 14px;
  color: #374151;
}
</style>
