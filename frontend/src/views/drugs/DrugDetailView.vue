<template>
  <div class="page-container">
    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else-if="drug">
      <!-- 返回 + 操作区 -->
      <div class="page-header">
        <div class="back-row">
          <el-button text :icon="ArrowLeft" @click="router.back()">返回列表</el-button>
        </div>
        <div v-if="authStore.isPharmacist" class="action-row">
          <el-button type="primary" plain @click="dialogVisible = true">编辑</el-button>
          <el-popconfirm
            title="确认删除此药品？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            confirm-button-type="danger"
            @confirm="handleDelete"
          >
            <template #reference>
              <el-button type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>

      <!-- 药品信息卡片 -->
      <div class="detail-card">
        <div class="card-header">
          <div>
            <h2 class="drug-title">{{ drug.name }}</h2>
            <p v-if="drug.common_name" class="drug-common">通用名：{{ drug.common_name }}</p>
          </div>
          <el-tag v-if="drug.category" :type="drug.category === '处方药' ? 'danger' : 'success'" size="large">
            {{ drug.category }}
          </el-tag>
        </div>

        <el-divider />

        <el-descriptions :column="2" border class="drug-desc">
          <el-descriptions-item label="批准文号">
            {{ drug.approval_number || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="规格">
            {{ drug.specification || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="剂型">
            {{ drug.dosage_form || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="储存条件">
            {{ drug.storage_condition || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="生产企业" :span="2">
            {{ drug.manufacturer || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="drug.description" label="备注" :span="2">
            {{ drug.description }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDate(drug.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最后更新">
            {{ formatDate(drug.updated_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>

    <div v-else class="empty-wrap">
      <el-empty description="药品不存在或已被删除" />
      <el-button @click="router.push({ name: 'DrugList' })">返回列表</el-button>
    </div>

    <!-- 编辑弹窗 -->
    <DrugFormDialog
      v-if="drug"
      v-model:visible="dialogVisible"
      :drug="drug"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useDrugsStore } from '@/stores/drugs'
import type { Drug } from '@/types/drug'
import DrugFormDialog from './DrugFormDialog.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const drugsStore = useDrugsStore()

const drug = ref<Drug | null>(null)
const loading = ref(true)
const dialogVisible = ref(false)

function formatDate(str: string) {
  return new Date(str).toLocaleString('zh-CN', { hour12: false })
}

async function loadDrug() {
  loading.value = true
  try {
    drug.value = await drugsStore.fetchOne(Number(route.params.id))
  } catch {
    drug.value = null
  } finally {
    loading.value = false
  }
}

async function handleDelete() {
  try {
    await drugsStore.remove(drug.value!.id)
    ElMessage.success('删除成功')
    router.push({ name: 'DrugList' })
  } catch {
    // 错误已由 axios 拦截器处理
  }
}

async function onSaved() {
  dialogVisible.value = false
  await loadDrug()
}

onMounted(loadDrug)
</script>

<style scoped>
.page-container {
  padding: 32px;
  max-width: 900px;
  margin: 0 auto;
}

.loading-wrap {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.back-row,
.action-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.detail-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 28px 32px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.drug-title {
  font-size: 22px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 4px;
}

.drug-common {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.drug-desc {
  margin-top: 4px;
}

.empty-wrap {
  text-align: center;
  padding: 80px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
</style>
