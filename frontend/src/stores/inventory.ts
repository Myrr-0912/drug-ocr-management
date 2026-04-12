import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  InventoryRecord,
  StockInRequest,
  StockOutRequest,
  AdjustRequest,
  InventoryListQuery,
} from '@/types/inventory'
import * as inventoryApi from '@/api/inventory'

export const useInventoryStore = defineStore('inventory', () => {
  const records = ref<InventoryRecord[]>([])
  const total = ref(0)
  const loading = ref(false)

  /** 加载库存流水记录 */
  async function fetchRecords(query?: InventoryListQuery) {
    loading.value = true
    try {
      const resp = await inventoryApi.getInventoryRecords(query)
      const data = resp.data.data!
      records.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  /** 入库 */
  async function doStockIn(data: StockInRequest) {
    const resp = await inventoryApi.stockIn(data)
    return resp.data.data!
  }

  /** 出库 */
  async function doStockOut(data: StockOutRequest) {
    const resp = await inventoryApi.stockOut(data)
    return resp.data.data!
  }

  /** 盘点调整 */
  async function doAdjust(data: AdjustRequest) {
    const resp = await inventoryApi.adjustInventory(data)
    return resp.data.data!
  }

  return { records, total, loading, fetchRecords, doStockIn, doStockOut, doAdjust }
})
