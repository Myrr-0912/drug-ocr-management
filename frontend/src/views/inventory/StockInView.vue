<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">库存操作</h2>
        <p class="page-subtitle">入库、出库或盘点调整</p>
      </div>
      <el-button :icon="ArrowLeft" @click="$router.push({ name: 'InventoryList' })">
        返回流水
      </el-button>
    </div>

    <!-- 操作类型选项卡 -->
    <div class="card op-card">
      <el-tabs v-model="activeTab" class="op-tabs">
        <el-tab-pane label="入库" name="in">
          <div class="tab-desc">增加指定批次的库存数量</div>
        </el-tab-pane>
        <el-tab-pane label="出库" name="out">
          <div class="tab-desc">减少指定批次的库存数量，库存不足时将阻止操作</div>
        </el-tab-pane>
        <el-tab-pane label="盘点调整" name="adjust">
          <div class="tab-desc">将指定批次的库存直接设置为盘点后的实际数量</div>
        </el-tab-pane>
      </el-tabs>

      <!-- 操作表单 -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="currentRules"
        label-width="90px"
        class="op-form"
      >
        <!-- 药品选择 -->
        <el-form-item label="药品" prop="drug_id">
          <el-select
            v-model="form.drug_id"
            placeholder="请选择药品"
            filterable
            style="width: 100%"
            @change="onDrugChange"
          >
            <el-option
              v-for="d in drugOptions"
              :key="d.id"
              :label="d.name"
              :value="d.id"
            />
          </el-select>
        </el-form-item>

        <!-- 批次选择 -->
        <el-form-item label="批次" prop="batch_id">
          <el-select
            v-model="form.batch_id"
            placeholder="请先选择药品"
            :disabled="!form.drug_id"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="b in batchOptions"
              :key="b.id"
              :label="batchLabel(b)"
              :value="b.id"
            />
          </el-select>
        </el-form-item>

        <!-- 数量 -->
        <el-form-item v-if="activeTab !== 'adjust'" label="数量" prop="quantity">
          <el-input-number
            v-model="form.quantity"
            :min="1"
            style="width: 100%"
            placeholder="请输入数量"
          />
        </el-form-item>
        <el-form-item v-else label="调整后数量" prop="new_quantity">
          <el-input-number
            v-model="form.new_quantity"
            :min="0"
            style="width: 100%"
            placeholder="请输入盘点后实际库存"
          />
          <div v-if="selectedBatch" class="qty-hint">
            当前库存：{{ selectedBatch.quantity }} {{ selectedBatch.unit }}
          </div>
        </el-form-item>

        <!-- 备注 -->
        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="2"
            placeholder="可选备注说明"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <!-- 提交 -->
        <el-form-item>
          <el-button
            type="primary"
            :loading="submitting"
            style="width: 120px"
            @click="handleSubmit"
          >
            {{ OP_LABEL[activeTab as OperationType] }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 最近操作记录（仅当前药品） -->
    <div v-if="recentRecords.length > 0" class="card recent-card">
      <h3 class="recent-title">最近操作记录</h3>
      <el-table :data="recentRecords" stripe size="small">
        <el-table-column prop="drug_name" label="药品" min-width="120" show-overflow-tooltip />
        <el-table-column prop="batch_number" label="批号" width="130" />
        <el-table-column prop="operation_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="(OPERATION_TYPE_TAG[row.operation_type as OperationType] as any)" size="small">
              {{ OPERATION_TYPE_LABEL[row.operation_type as OperationType] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="变动" width="90">
          <template #default="{ row }">
            <span :class="row.quantity >= 0 ? 'qty-positive' : 'qty-negative'">
              {{ row.quantity >= 0 ? '+' : '' }}{{ row.quantity }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useInventoryStore } from '@/stores/inventory'
import { getBatchList } from '@/api/batches'
import { getDrugList } from '@/api/drugs'
import { getInventoryRecords } from '@/api/inventory'
import type { Batch } from '@/types/batch'
import type { InventoryRecord, OperationType } from '@/types/inventory'
import { OPERATION_TYPE_LABEL, OPERATION_TYPE_TAG } from '@/types/inventory'

const OP_LABEL: Record<OperationType, string> = { in: '确认入库', out: '确认出库', adjust: '确认调整' }

const inventoryStore = useInventoryStore()
const formRef = ref<FormInstance>()
const activeTab = ref<OperationType>('in')
const submitting = ref(false)

const drugOptions = ref<{ id: number; name: string }[]>([])
const batchOptions = ref<Batch[]>([])
const recentRecords = ref<InventoryRecord[]>([])

const form = reactive({
  drug_id: 0,
  batch_id: 0,
  quantity: 1,
  new_quantity: 0,
  remark: '',
})

const selectedBatch = computed(() =>
  batchOptions.value.find((b) => b.id === form.batch_id) ?? null
)

function batchLabel(b: Batch) {
  return `${b.batch_number} · 库存:${b.quantity}${b.unit} · 有效期:${b.expiry_date}`
}

/** 动态校验规则（根据操作类型切换数量字段） */
const currentRules = computed<FormRules>(() => ({
  drug_id: [{ required: true, type: 'number', min: 1, message: '请选择药品', trigger: 'change' }],
  batch_id: [{ required: true, type: 'number', min: 1, message: '请选择批次', trigger: 'change' }],
  quantity: activeTab.value !== 'adjust'
    ? [{ required: true, type: 'number', min: 1, message: '数量必须大于 0', trigger: 'blur' }]
    : [],
  new_quantity: activeTab.value === 'adjust'
    ? [{ required: true, type: 'number', min: 0, message: '调整量不能为负', trigger: 'blur' }]
    : [],
}))

async function onDrugChange(drugId: number) {
  form.batch_id = 0
  batchOptions.value = []
  if (!drugId) return
  const resp = await getBatchList({ drug_id: drugId, page: 1, page_size: 100 })
  batchOptions.value = resp.data.data!.items
  // 加载该药品最近流水（最近 10 条）
  const recResp = await getInventoryRecords({ drug_id: drugId, page: 1, page_size: 10 })
  recentRecords.value = recResp.data.data!.items
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (activeTab.value === 'in') {
      await inventoryStore.doStockIn({
        drug_id: form.drug_id,
        batch_id: form.batch_id,
        quantity: form.quantity,
        remark: form.remark || undefined,
      })
      ElMessage.success('入库成功')
    } else if (activeTab.value === 'out') {
      await inventoryStore.doStockOut({
        drug_id: form.drug_id,
        batch_id: form.batch_id,
        quantity: form.quantity,
        remark: form.remark || undefined,
      })
      ElMessage.success('出库成功')
    } else {
      await inventoryStore.doAdjust({
        drug_id: form.drug_id,
        batch_id: form.batch_id,
        new_quantity: form.new_quantity,
        remark: form.remark || undefined,
      })
      ElMessage.success('盘点调整成功')
    }
    // 重新加载该药品的批次（库存量已变）
    await onDrugChange(form.drug_id)
    // 重置数量与备注
    form.quantity = 1
    form.new_quantity = 0
    form.remark = ''
    formRef.value?.clearValidate()
  } catch {
    // 错误由 axios 拦截器统一处理
  } finally {
    submitting.value = false
  }
}

function formatTime(iso: string) {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '—'
}

onMounted(async () => {
  const resp = await getDrugList({ page: 1, page_size: 200 })
  drugOptions.value = resp.data.data!.items.map((d) => ({ id: d.id, name: d.name }))
})
</script>

<style scoped>
.page-container {
  padding: 32px;
  max-width: 800px;
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

.op-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  padding: 24px;
  margin-bottom: 24px;
}

.op-tabs {
  margin-bottom: 24px;
}

.tab-desc {
  font-size: 13px;
  color: #6b7280;
  padding: 8px 0 16px;
  line-height: 1.5;
}

.op-form {
  max-width: 480px;
}

.qty-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.recent-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  padding: 20px 24px;
}

.recent-title {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 16px;
}

.qty-positive {
  font-weight: 500;
  color: #16a34a;
}

.qty-negative {
  font-weight: 500;
  color: #dc2626;
}
</style>
