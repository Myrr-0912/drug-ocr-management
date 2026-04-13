<template>
  <div class="page-container">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">药品管理</h2>
        <p class="page-subtitle">管理所有药品的基础档案信息</p>
      </div>
      <el-button
        v-if="authStore.isPharmacist"
        type="primary"
        :icon="Plus"
        @click="openDialog()"
      >
        新建药品
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索药品名称、通用名、批准文号..."
        clearable
        :prefix-icon="Search"
        class="search-input"
        @input="onSearch"
        @clear="onSearch"
      />
      <el-select
        v-model="query.category"
        placeholder="分类"
        clearable
        class="filter-select"
        @change="onSearch"
      >
        <el-option
          v-for="cat in CATEGORIES"
          :key="cat"
          :label="cat"
          :value="cat"
        />
      </el-select>
      <el-input
        v-model="query.manufacturer"
        placeholder="厂家"
        clearable
        class="filter-input"
        @input="onSearch"
        @clear="onSearch"
      />
    </div>

    <!-- 表格 -->
    <div class="card table-card">
      <el-table
        v-loading="drugsStore.loading"
        :data="drugsStore.list"
        stripe
        style="width: 100%"
        row-class-name="table-row"
      >
        <el-table-column prop="name" label="药品名称" min-width="160">
          <template #default="{ row }">
            <span class="drug-name">{{ row.name }}</span>
            <span v-if="row.common_name" class="drug-common">{{ row.common_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="approval_number" label="批准文号" width="160" />
        <el-table-column prop="specification" label="规格" width="120" />
        <el-table-column prop="dosage_form" label="剂型" width="100" />
        <el-table-column prop="manufacturer" label="生产企业" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small" :type="row.category === '处方药' ? 'danger' : 'success'">
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewDetail(row)">查看</el-button>
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
              title="确认删除此药品？"
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
          :total="drugsStore.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @change="loadList"
        />
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <DrugFormDialog
      v-model:visible="dialogVisible"
      :drug="editingDrug"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useDrugsStore } from '@/stores/drugs'
import type { Drug } from '@/types/drug'
import DrugFormDialog from './DrugFormDialog.vue'

const CATEGORIES = ['处方药', 'OTC', '中药', '中成药', '生物制品']

const router = useRouter()
const authStore = useAuthStore()
const drugsStore = useDrugsStore()

const query = reactive({
  keyword: '',
  category: '',
  manufacturer: '',
  page: 1,
  page_size: 20,
})

const dialogVisible = ref(false)
const editingDrug = ref<Drug | null>(null)

/** 防抖定时器 */
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    query.page = 1
    loadList()
  }, 300)
}

async function loadList() {
  await drugsStore.fetchList({
    keyword: query.keyword || undefined,
    category: query.category || undefined,
    manufacturer: query.manufacturer || undefined,
    page: query.page,
    page_size: query.page_size,
  })
}

function viewDetail(row: Drug) {
  router.push({ name: 'DrugDetail', params: { id: row.id } })
}

function openDialog(drug: Drug | null = null) {
  editingDrug.value = drug
  dialogVisible.value = true
}

async function handleDelete(id: number) {
  try {
    await drugsStore.remove(id)
    ElMessage.success('删除成功')
  } catch {
    // 错误已由 axios 拦截器处理
  }
}

function onSaved() {
  dialogVisible.value = false
  loadList()
}

onMounted(loadList)
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
  width: 320px;
}

.filter-select {
  width: 140px;
}

.filter-input {
  width: 160px;
}

.table-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

:deep(.table-row) {
  transition: background-color 0.15s ease;
}

.drug-name {
  display: block;
  font-weight: 500;
  color: #111827;
  line-height: 1.5;
}

.drug-common {
  display: block;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

.pagination-wrap {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f3f4f6;
}
</style>
