import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Batch, BatchCreate, BatchUpdate, BatchListQuery } from '@/types/batch'
import * as batchesApi from '@/api/batches'

export const useBatchesStore = defineStore('batches', () => {
  const list = ref<Batch[]>([])
  const total = ref(0)
  const loading = ref(false)

  /** 加载批次列表 */
  async function fetchList(query?: BatchListQuery) {
    loading.value = true
    try {
      const resp = await batchesApi.getBatchList(query)
      const data = resp.data.data!
      list.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  /** 新建批次 */
  async function create(data: BatchCreate) {
    const resp = await batchesApi.createBatch(data)
    return resp.data.data!
  }

  /** 更新批次 */
  async function update(id: number, data: BatchUpdate) {
    const resp = await batchesApi.updateBatch(id, data)
    const updated = resp.data.data!
    list.value = list.value.map((b) => (b.id === id ? updated : b))
    return updated
  }

  /** 删除批次 */
  async function remove(id: number) {
    await batchesApi.deleteBatch(id)
    list.value = list.value.filter((b) => b.id !== id)
    total.value -= 1
  }

  return { list, total, loading, fetchList, create, update, remove }
})
