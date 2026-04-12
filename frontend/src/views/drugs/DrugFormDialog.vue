<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑药品' : '新建药品'"
    width="560px"
    :close-on-click-modal="false"
    destroy-on-close
    @close="resetForm"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      label-position="right"
    >
      <el-form-item label="药品名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入药品名称" />
      </el-form-item>
      <el-form-item label="通用名" prop="common_name">
        <el-input v-model="form.common_name" placeholder="通用名（可选）" />
      </el-form-item>
      <el-form-item label="批准文号" prop="approval_number">
        <el-input v-model="form.approval_number" placeholder="如：国药准字 Z20050001" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="规格" prop="specification">
            <el-input v-model="form.specification" placeholder="如：0.5g×24片" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="剂型" prop="dosage_form">
            <el-select v-model="form.dosage_form" placeholder="选择剂型" clearable style="width:100%">
              <el-option v-for="f in DOSAGE_FORMS" :key="f" :label="f" :value="f" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="分类" prop="category">
        <el-select v-model="form.category" placeholder="选择分类" clearable style="width:100%">
          <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="生产企业" prop="manufacturer">
        <el-input v-model="form.manufacturer" placeholder="请输入生产企业名称" />
      </el-form-item>
      <el-form-item label="储存条件" prop="storage_condition">
        <el-input v-model="form.storage_condition" placeholder="如：密封，阴凉处保存" />
      </el-form-item>
      <el-form-item label="备注" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="其他说明（可选）"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">
          {{ isEdit ? '保存修改' : '创建药品' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useDrugsStore } from '@/stores/drugs'
import type { Drug } from '@/types/drug'

const DOSAGE_FORMS = ['片剂', '胶囊', '注射液', '颗粒剂', '口服液', '软膏', '贴剂', '滴眼液', '其他']
const CATEGORIES = ['处方药', 'OTC', '中药', '中成药', '生物制品']

const props = defineProps<{
  visible: boolean
  drug: Drug | null
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  saved: []
}>()

const visible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const isEdit = computed(() => !!props.drug)

const drugsStore = useDrugsStore()
const formRef = ref<FormInstance>()
const saving = ref(false)

const form = reactive({
  name: '',
  common_name: '',
  approval_number: '',
  specification: '',
  dosage_form: '',
  category: '',
  manufacturer: '',
  storage_condition: '',
  description: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入药品名称', trigger: 'blur' }],
}

// 编辑时回填数据
watch(
  () => props.drug,
  (drug) => {
    if (drug) {
      Object.assign(form, {
        name: drug.name,
        common_name: drug.common_name ?? '',
        approval_number: drug.approval_number ?? '',
        specification: drug.specification ?? '',
        dosage_form: drug.dosage_form ?? '',
        category: drug.category ?? '',
        manufacturer: drug.manufacturer ?? '',
        storage_condition: drug.storage_condition ?? '',
        description: drug.description ?? '',
      })
    }
  },
  { immediate: true },
)

function resetForm() {
  Object.assign(form, {
    name: '', common_name: '', approval_number: '',
    specification: '', dosage_form: '', category: '',
    manufacturer: '', storage_condition: '', description: '',
  })
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  await formRef.value?.validate()
  saving.value = true
  try {
    // 去除空字符串字段，转为 undefined
    const payload = Object.fromEntries(
      Object.entries(form).map(([k, v]) => [k, v === '' ? undefined : v])
    ) as typeof form

    if (isEdit.value) {
      await drugsStore.update(props.drug!.id, payload)
      ElMessage.success('保存成功')
    } else {
      await drugsStore.create(payload)
      ElMessage.success('药品创建成功')
    }
    emit('saved')
  } catch {
    // 错误已由 axios 拦截器处理
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
