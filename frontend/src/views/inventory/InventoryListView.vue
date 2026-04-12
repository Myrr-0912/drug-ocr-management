<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">库存流水</h2>
        <p class="page-subtitle">查看所有出入库及盘点记录</p>
      </div>
      <el-button
        v-if="authStore.isPharmacist"
        type="primary"
        :icon="Edit"
        @click="$router.push({ name: 'StockIn' })"
      >
        库存操作
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="search-bar">
      <el-select
        v-model="query.operation_type"
        placeholder="全部类型"
        clearable
        class="filter-select"
        @change="onFilter"
      >
        <el-option
          v-for="(label, val) in OPERATION_TYPE_LABEL"
          :key="val"
          :label="label"
          :value="val"
        />
      </el-select>
    </div>

    <!-- 表格 -->
    <div class="card table-card">
      <el-table
        v-loading="inventoryStore.loading"
        :data="inventoryStore.records"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="drug_name" label="药品名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="batch_number" label="批号" min-width="130" />
        <el-table-column prop="operation_type" label="操作类型" width="110">
          <template #default="{ row }">
            <el-tag :type="(OPERATION_TYPE_TAG[row.operation_type] as any)" size="small">
              {{ OPERATION_TYPE_LABEL[row.operation_type] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="变动数量" width="100">
          <template #default="{ row }">
            <span :class="row.quantity >= 0 ? 'qty-positive' : 'qty-negative'">
              {{ row.quantity >= 0 ? '+' : '' }}{{ row.quantity }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="100">
          <template #default="{ row }">
            {{ row.operator_name ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.remark ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="inventoryStore.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @change="loadRecords"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { Edit } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useInventoryStore } from '@/stores/inventory'
import { OPERATION_TYPE_LABEL, OPERATION_TYPE_TAG } from '@/types/inventory'

const authStore = useAuthStore()
const inventoryStore = useInventoryStore()

const query = reactive({
  operation_type: '' as any,
  page: 1,
  page_size: 20,
})

function onFilter() {
  query.page = 1
  loadRecords()
}

async function loadRecords() {
  await inventoryStore.fetchRecords({
    operation_type: query.operation_type || undefined,
    page: query.page,
    page_size: query.page_size,
  })
}

function formatTime(iso: string) {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '—'
}

onMounted(loadRecords)
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

.qty-positive {
  font-weight: 500;
  color: #16a34a;
}

.qty-negative {
  font-weight: 500;
  color: #dc2626;
}

.pagination-wrap {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f3f4f6;
}
</style>
