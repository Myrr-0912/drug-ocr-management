import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Drug, DrugCreate, DrugUpdate, DrugListQuery } from '@/types/drug'
import * as drugsApi from '@/api/drugs'

export const useDrugsStore = defineStore('drugs', () => {
  const list = ref<Drug[]>([])
  const total = ref(0)
  const loading = ref(false)
  const currentDrug = ref<Drug | null>(null)

  /** 加载药品列表 */
  async function fetchList(query?: DrugListQuery) {
    loading.value = true
    try {
      const resp = await drugsApi.getDrugList(query)
      const data = resp.data.data!
      list.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  /** 加载单个药品 */
  async function fetchOne(id: number) {
    const resp = await drugsApi.getDrug(id)
    currentDrug.value = resp.data.data!
    return currentDrug.value
  }

  /** 新建药品 */
  async function create(data: DrugCreate) {
    const resp = await drugsApi.createDrug(data)
    return resp.data.data!
  }

  /** 更新药品 */
  async function update(id: number, data: DrugUpdate) {
    const resp = await drugsApi.updateDrug(id, data)
    // 同步列表中的记录
    const updated = resp.data.data!
    const idx = list.value.findIndex((d) => d.id === id)
    if (idx !== -1) {
      list.value = list.value.map((d) => (d.id === id ? updated : d))
    }
    return updated
  }

  /** 删除药品 */
  async function remove(id: number) {
    await drugsApi.deleteDrug(id)
    list.value = list.value.filter((d) => d.id !== id)
    total.value -= 1
  }

  return { list, total, loading, currentDrug, fetchList, fetchOne, create, update, remove }
})
