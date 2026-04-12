<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  getOverview,
  getInventoryTrend,
  getExpiryDistribution,
  type StatsOverview,
  type TrendPoint,
  type ExpiryDistribution,
} from '@/api/stats'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

// ── 状态 ───────────────────────────────────────────────────
const loading = ref(true)
const overview = ref<StatsOverview | null>(null)
const trendData = ref<TrendPoint[]>([])
const expiryData = ref<ExpiryDistribution | null>(null)

// ── 统计卡片配置 ───────────────────────────────────────────
const cards = computed(() => [
  {
    label: '药品总数',
    value: overview.value?.total_drugs ?? '--',
    unit: '种',
    icon: '💊',
    color: '#3b82f6',
    bg: '#eff6ff',
  },
  {
    label: '有效库存批次',
    value: overview.value?.total_batches ?? '--',
    unit: '批',
    icon: '📦',
    color: '#10b981',
    bg: '#f0fdf4',
  },
  {
    label: '活跃预警',
    value: overview.value?.active_alerts ?? '--',
    unit: '条',
    icon: '🔔',
    color: '#f59e0b',
    bg: '#fffbeb',
  },
  {
    label: '今日入库',
    value: overview.value?.today_stock_in ?? '--',
    unit: '笔',
    icon: '📥',
    color: '#8b5cf6',
    bg: '#f5f3ff',
  },
])

// ── ECharts 折线图配置 ─────────────────────────────────────
const lineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['入库', '出库'], bottom: 0 },
  grid: { left: 16, right: 16, top: 16, bottom: 40, containLabel: true },
  xAxis: {
    type: 'category',
    data: trendData.value.map((d) => d.date.slice(5)), // MM-DD
    axisLine: { lineStyle: { color: '#e5e7eb' } },
    axisTick: { show: false },
    axisLabel: { color: '#9ca3af', fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#f3f4f6' } },
    axisLabel: { color: '#9ca3af', fontSize: 11 },
  },
  series: [
    {
      name: '入库',
      type: 'line',
      smooth: true,
      data: trendData.value.map((d) => d.stock_in),
      lineStyle: { color: '#3b82f6', width: 2 },
      itemStyle: { color: '#3b82f6' },
      areaStyle: { color: 'rgba(59,130,246,0.08)' },
    },
    {
      name: '出库',
      type: 'line',
      smooth: true,
      data: trendData.value.map((d) => d.stock_out),
      lineStyle: { color: '#f59e0b', width: 2 },
      itemStyle: { color: '#f59e0b' },
      areaStyle: { color: 'rgba(245,158,11,0.08)' },
    },
  ],
}))

// ── ECharts 饼图配置 ───────────────────────────────────────
const pieOption = computed(() => {
  const d = expiryData.value
  if (!d) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 批 ({d}%)' },
    legend: { orient: 'vertical', right: 16, top: 'center', itemGap: 10 },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['38%', '50%'],
        data: [
          { value: d.normal, name: '正常', itemStyle: { color: '#10b981' } },
          { value: d.near_90, name: '90天内到期', itemStyle: { color: '#3b82f6' } },
          { value: d.near_30, name: '30天内到期', itemStyle: { color: '#f59e0b' } },
          { value: d.expired, name: '已过期', itemStyle: { color: '#ef4444' } },
        ],
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
      },
    ],
  }
})

// ── 数据加载 ───────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  try {
    const [overviewRes, trendRes, expiryRes] = await Promise.all([
      getOverview(),
      getInventoryTrend(30),
      getExpiryDistribution(),
    ])
    overview.value = overviewRes.data.data
    trendData.value = trendRes.data.data ?? []
    expiryData.value = expiryRes.data.data
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 概览卡片 -->
    <div class="stat-grid">
      <div v-for="card in cards" :key="card.label" class="stat-card" :style="{ '--card-bg': card.bg, '--card-color': card.color }">
        <div class="stat-icon">{{ card.icon }}</div>
        <div class="stat-body">
          <div class="stat-value">
            {{ card.value }}<span class="stat-unit">{{ card.unit }}</span>
          </div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="chart-grid">
      <!-- 出入库趋势折线图 -->
      <div class="chart-card">
        <div class="chart-title">近 30 天出入库趋势</div>
        <v-chart class="chart" :option="lineOption" autoresize />
      </div>

      <!-- 过期分布饼图 -->
      <div class="chart-card">
        <div class="chart-title">批次有效期分布</div>
        <v-chart class="chart" :option="pieOption" autoresize />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}

// 统计卡片网格
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  background: var(--card-bg, #f9fafb);
  border: 1px solid #f3f4f6;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.2s ease-in-out;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  }
}

.stat-icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--card-color, #111827);
  line-height: 1.2;
}

.stat-unit {
  font-size: 13px;
  font-weight: 400;
  color: #9ca3af;
  margin-left: 3px;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

// 图表网格
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: #fff;
  border: 1px solid #f3f4f6;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 16px;
}

.chart {
  height: 260px;
  width: 100%;
}
</style>
