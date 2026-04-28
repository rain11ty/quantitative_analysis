<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import BaseEChart from '../components/BaseEChart.vue';
import { useToast } from '../composables/useToast';
import { formatNumber, formatPercent, formatCompactNumber } from '../lib/format';
import { getMarketOverview, getIndexKline, getMarketHealth, type MarketOverview, type IndexKlineItem } from '../modules/market/api';
import { http } from '../lib/http';
import type { EChartsOption } from 'echarts';

const router = useRouter();
const toast = useToast();

const overview = ref<MarketOverview | null>(null);
const klineData = ref<IndexKlineItem[]>([]);
const ranking = ref<Record<string, unknown>[]>([]);
const health = ref('');
const loading = ref(true);
const error = ref('');
const selectedIndex = ref('000300.SH');
const klinePeriod = ref('3M');
const rankingSort = ref('pct_change');
const lastUpdated = ref('');
const autoRefresh = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const indexMap: Record<string, string> = {
  '000001.SH': '上证', '399001.SZ': '深证', '399006.SZ': '创业板',
  '000688.SH': '科创50', '000300.SH': '沪深300', '000905.SH': '中证500',
};

const activeIndexName = computed(() => indexMap[selectedIndex.value] || selectedIndex.value);

const klineOption = computed<EChartsOption>(() => {
  if (!Array.isArray(klineData.value) || !klineData.value.length) return {};
  const dates = klineData.value.map((d) => d.trade_date || '');
  const closes = klineData.value.map((d) => d.close ?? 0);
  const ma5 = calcMA(closes, 5);
  const ma20 = calcMA(closes, 20);
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 16, top: 12, bottom: 28 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)', formatter: (v: string) => v.slice(5) },
      axisLine: { lineStyle: { color: 'rgba(10,11,13,0.08)' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', splitLine: { lineStyle: { color: 'rgba(10,11,13,0.04)' } },
      axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)' },
    },
    series: [
      { name: '收盘', type: 'line', data: closes, smooth: true, lineStyle: { width: 1.5, color: '#0052ff' }, symbol: 'none', areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(0,82,255,0.12)' }, { offset: 1, color: 'rgba(0,82,255,0)' }] } } },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { width: 1, color: '#ff9f0a' }, symbol: 'none' },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { width: 1, color: '#34c759' }, symbol: 'none' },
    ],
  };
});

function calcMA(data: number[], days: number) {
  return data.map((_, i) => {
    if (i < days - 1) return null;
    return data.slice(i - days + 1, i + 1).reduce((a, b) => a + b, 0) / days;
  });
}

async function loadAll() {
  loading.value = true; error.value = '';
  try {
    const [ov, kl, rk] = await Promise.all([
      getMarketOverview(),
      getIndexKline(selectedIndex.value, klinePeriod.value),
      http.get('/api/monitor/ranking', { params: { sort_by: rankingSort.value, limit: 10 } }),
    ]);
    overview.value = ov;
    klineData.value = kl.data || [];
    ranking.value = rk.data?.data || [];
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  } catch (e) {
    error.value = '数据加载失败，请检查网络连接';
    toast.error('市场数据加载失败');
  }
  loading.value = false;
}

async function checkHealth() {
  try {
    const h = await getMarketHealth();
    health.value = h.success ? '正常' : '异常';
    if (h.success) toast.success('API 连接正常');
    else toast.warning('API: ' + (h.message || '状态异常'));
  } catch { toast.error('连通性检查失败'); }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshTimer = setInterval(loadAll, 60000);
  } else {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  }
}

onMounted(loadAll);
onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer); });
</script>

<template>
  <div>
    <!-- Loading -->
    <template v-if="loading">
      <div class="card"><div class="skeleton" style="height:360px;" /></div>
    </template>

    <template v-else>
      <!-- Error -->
      <div v-if="error" class="alert alert-error">
        {{ error }}
        <button class="btn btn-ghost btn-sm" @click="loadAll">重试</button>
      </div>

      <!-- Index Selector + Refresh -->
      <div class="flex-between" style="flex-wrap:wrap;gap:8px;">
        <div class="tab-bar">
          <button v-for="(name, code) in indexMap" :key="code"
            class="tab-btn" :class="{ active: selectedIndex === code }"
            @click="selectedIndex = code; loadAll()"
          >{{ name }}</button>
        </div>
        <div class="flex-between gap-2">
          <span v-if="lastUpdated" class="text-xs text-muted">更新于 {{ lastUpdated }}</span>
          <button class="btn btn-sm" :class="autoRefresh ? 'btn-primary' : 'btn-ghost'"
            @click="toggleAutoRefresh"
          >{{ autoRefresh ? '自动刷新' : '手动刷新' }}</button>
        </div>
      </div>

      <!-- Index Prices -->
      <div v-if="overview?.indices" class="stat-grid">
        <div v-for="idx in overview.indices.slice(0, 4)" :key="idx.ts_code" class="stat-item">
          <div class="stat-label">{{ idx.name }}</div>
          <div class="stat-value">{{ idx.price?.toFixed(2) }}</div>
          <div class="stat-sub" :class="(idx.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">
            {{ formatPercent(idx.pct_chg) }}
          </div>
        </div>
      </div>

      <!-- Chart -->
      <div class="card" style="padding:16px;">
        <div class="card-header mb-2">
          <h3>{{ activeIndexName }}</h3>
          <div class="tab-bar">
            <button v-for="p in ['1M','3M','1Y','3Y']" :key="p"
              class="tab-btn" :class="{ active: klinePeriod === p }"
              @click="klinePeriod = p; loadAll()"
            >{{ p }}</button>
          </div>
        </div>
        <BaseEChart :option="klineOption" height="360px" />
      </div>

      <!-- Stats + Health -->
      <div class="grid-2">
        <div v-if="overview?.summary" class="card">
          <div class="card-header"><h3>市场概况</h3></div>
          <div class="stat-grid">
            <div class="stat-item"><div class="stat-label">成交额</div><div class="stat-value stat-value-sm">{{ formatCompactNumber(overview.summary.total_turnover) }}</div></div>
            <div class="stat-item"><div class="stat-label">成交量</div><div class="stat-value stat-value-sm">{{ formatCompactNumber(overview.summary.total_volume) }}</div></div>
            <div class="stat-item"><div class="stat-label">涨停</div><div class="stat-value text-down stat-value-sm">{{ overview.summary.limit_up }}</div></div>
            <div class="stat-item"><div class="stat-label">跌停</div><div class="stat-value text-up stat-value-sm">{{ overview.summary.limit_down }}</div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>系统状态</h3></div>
          <div class="stat-item mb-2">
            <div class="stat-label">Tushare API</div>
            <div class="stat-value stat-value-sm" :class="health === '正常' ? 'text-down' : health ? 'text-up' : ''">
              {{ health || '未检查' }}
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="checkHealth">测试连通性</button>
        </div>
      </div>

      <!-- Ranking -->
      <div class="card" style="padding:16px;">
        <div class="card-header mb-2">
          <h3>涨跌排行</h3>
          <select v-model="rankingSort" class="form-select" style="width:auto;font-size:12px;" @change="loadAll">
            <option value="pct_change">涨跌幅</option>
            <option value="turnover_rate">换手率</option>
            <option value="amount">成交额</option>
          </select>
        </div>
        <table class="data-table w-full" v-if="ranking.length">
          <thead><tr><th>#</th><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in ranking" :key="i" class="clickable" @click="router.push('/stock/' + r.ts_code)">
              <td style="color:var(--cb-text-tertiary);font-size:11px;">{{ i + 1 }}</td>
              <td class="font-mono">{{ r.ts_code }}</td>
              <td class="font-bold">{{ r.name }}</td>
              <td class="font-mono">{{ (r as any).price ?? (r as any).close }}</td>
              <td><span :class="Number(r.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(r.pct_chg) }}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="text-sm text-muted" style="text-align:center;padding:20px;">暂无数据</div>
      </div>
    </template>
  </div>
</template>
