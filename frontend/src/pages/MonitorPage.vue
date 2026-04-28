<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import BaseEChart from '../components/BaseEChart.vue';
import { useToast } from '../composables/useToast';
import { formatPercent, formatCompactNumber, debounce } from '../lib/format';
import { getMonitorDashboard, getRanking, getShock, searchStocks } from '../modules/monitor/api';
import { getMarketOverview } from '../modules/market/api';
import type { EChartsOption } from 'echarts';

const router = useRouter();
const toast = useToast();
const codes = ref('');
const activeStock = ref<Record<string, unknown> | null>(null);
const stocks = ref<Record<string, unknown>[]>([]);
const indices = ref<Record<string, unknown>[]>([]);
const ranking = ref<Record<string, unknown>[]>([]);
const shockData = ref<Record<string, unknown>[]>([]);
const error = ref('');
const autoRefresh = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;
const searchQuery = ref('');
const searchResults = ref<Record<string, unknown>[]>([]);
const showSearch = ref(false);

async function loadDashboard() {
  error.value = '';
  try {
    const [dash, idx, rank, shock] = await Promise.all([
      getMonitorDashboard(codes.value || ''),
      getMarketOverview(),
      getRanking('pct_change', 20),
      getShock(undefined, 30),
    ]);
    stocks.value = (dash.stocks || []) as Record<string, unknown>[];
    indices.value = (idx.indices || []) as Record<string, unknown>[];
    ranking.value = rank.data || [];
    shockData.value = shock.data || [];
    if (stocks.value.length && !activeStock.value) activeStock.value = stocks.value[0];
  } catch { error.value = '加载失败'; toast.error('监控数据加载失败'); }
}

onMounted(loadDashboard);
onBeforeUnmount(() => { if (refreshTimer) clearInterval(refreshTimer); });

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) refreshTimer = setInterval(loadDashboard, 30000);
  else { if (refreshTimer) clearInterval(refreshTimer); refreshTimer = null; }
}

async function doSearch() {
  if (searchQuery.value.length < 1) { searchResults.value = []; showSearch.value = false; return; }
  try { const res = await searchStocks(searchQuery.value); searchResults.value = (res.data || []) as Record<string, unknown>[]; showSearch.value = true; } catch { /* */ }
}
const debouncedSearch = debounce(doSearch, 300);

function addStock(item: Record<string, unknown>) {
  const c = item.ts_code as string;
  if (c && !codes.value.includes(c)) codes.value = codes.value ? codes.value + ',' + c : c;
  showSearch.value = false; searchQuery.value = ''; loadDashboard();
}

const indexOption = computed(() => {
  const raw = activeStock.value?.series;
  const series = (Array.isArray(raw) ? raw : []) as Record<string, unknown>[];
  if (!series.length) return {};
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 16, top: 16, bottom: 32 },
    xAxis: { type: 'category', data: series.map(s => s.label || '') },
    yAxis: [
      { type: 'value', splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } } },
      { type: 'value', splitLine: { show: false } },
    ],
    series: [
      {
        type: 'candlestick', data: series.map(s => [Number(s.open || 0), Number(s.close || 0), Number(s.low || 0), Number(s.high || 0)]),
        itemStyle: { color: '#ff3b30', color0: '#34c759', borderColor: '#ff3b30', borderColor0: '#34c759' },
      },
      { type: 'bar', data: series.map(s => Number(s.volume || 0)), yAxisIndex: 1, itemStyle: { color: 'rgba(0,113,227,.18)' } },
    ],
  } as EChartsOption;
});
</script>

<template>
  <div>
    <div class="card">
      <div class="flex-between gap-2" style="flex-wrap:wrap;">
        <div style="display:flex;gap:8px;flex:1;">
          <input v-model="codes" class="form-input" placeholder="股票代码，逗号分隔" style="flex:1;" @keyup.enter="loadDashboard" />
          <div style="position:relative;">
            <input v-model="searchQuery" class="form-input" placeholder="搜索添加" style="width:160px;" @input="debouncedSearch" @focus="showSearch = searchResults.length > 0" />
            <div v-if="showSearch" style="position:absolute;top:100%;left:0;right:0;z-index:10;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);max-height:180px;overflow-y:auto;box-shadow:var(--shadow-elevated);">
              <div v-for="r in searchResults" :key="r.ts_code as string" style="padding:8px 12px;cursor:pointer;font-size:13px;" @mousedown.prevent="addStock(r)">{{ r.symbol || r.ts_code }} - {{ r.name }}</div>
            </div>
          </div>
        </div>
        <div class="flex-between gap-2">
          <button class="btn btn-primary btn-sm" @click="loadDashboard">应用</button>
          <button class="btn btn-sm" :class="autoRefresh ? 'btn-primary' : 'btn-ghost'" @click="toggleAutoRefresh">{{ autoRefresh ? '刷新中' : '自动刷新' }}</button>
        </div>
      </div>
      <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>
    </div>

    <div v-if="indices.length" class="flex-between gap-3 text-sm" style="overflow-x:auto;padding:4px 0;">
      <span v-for="idx in indices" :key="idx.ts_code as string" class="font-mono">
        <strong>{{ (idx.price as number)?.toFixed(2) }}</strong>
        <span :class="(idx.pct_chg as number ?? 0) >= 0 ? 'text-down' : 'text-up'"> {{ formatPercent(idx.pct_chg) }}</span>
      </span>
    </div>

    <div v-if="stocks.length" class="tab-bar" style="flex-wrap:wrap;">
      <button v-for="s in stocks" :key="s.ts_code as string" class="tab-btn" :class="{ active: activeStock?.ts_code === s.ts_code }" @click="activeStock = s">{{ s.name || s.ts_code }}</button>
    </div>

    <div v-if="activeStock" class="grid-2">
      <div class="card" style="padding:16px;">
        <div class="card-header" style="margin-bottom:12px;"><h3>{{ activeStock.name || activeStock.ts_code }}</h3></div>
        <div class="stat-grid" style="margin-bottom:12px;">
          <div class="stat-item"><div class="stat-label">最新价</div><div class="stat-value font-mono" style="font-size:20px;">{{ (activeStock.quote as any)?.price }}</div></div>
          <div class="stat-item"><div class="stat-label">涨跌幅</div><div class="stat-value" style="font-size:20px;" :class="((activeStock.quote as any)?.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent((activeStock.quote as any)?.pct_chg) }}</div></div>
          <div class="stat-item"><div class="stat-label">成交量</div><div class="stat-value font-mono" style="font-size:20px;">{{ formatCompactNumber((activeStock.quote as any)?.volume) }}</div></div>
          <div class="stat-item"><div class="stat-label">成交额</div><div class="stat-value font-mono" style="font-size:20px;">{{ formatCompactNumber((activeStock.quote as any)?.amount) }}</div></div>
        </div>
        <BaseEChart :option="indexOption" height="320px" />
      </div>
      <div class="card"><div class="empty-state" style="padding:48px 24px;"><h4>信号面板</h4><p class="text-sm text-muted">成交量 / 动量 / MACD / 波动率</p></div></div>
    </div>

    <div class="grid-2">
      <div class="card" style="padding:16px;">
        <div class="card-header" style="margin-bottom:8px;"><h3>涨跌排行</h3></div>
        <table class="data-table w-full" v-if="ranking.length">
          <thead><tr><th>#</th><th>股票</th><th>价格</th><th>涨跌幅</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in ranking" :key="i" class="clickable" @click="router.push('/stock/' + r.ts_code)">
              <td style="color:var(--text-tertiary);font-size:11px;">{{ i + 1 }}</td>
              <td class="font-mono" style="font-size:12px;">{{ r.symbol || r.ts_code }} <span class="font-bold">{{ r.name }}</span></td>
              <td class="font-mono" style="font-size:13px;">{{ r.price || r.close }}</td>
              <td :class="(r.pct_chg as number ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(r.pct_chg) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card" style="padding:16px;">
        <div class="card-header" style="margin-bottom:8px;"><h3>异动监控</h3><button class="btn btn-ghost btn-sm" @click="loadDashboard">刷新</button></div>
        <table class="data-table w-full" v-if="shockData.length">
          <thead><tr><th>股票</th><th>时间</th><th>类型</th></tr></thead>
          <tbody>
            <tr v-for="(s, i) in shockData" :key="i" class="clickable" @click="router.push('/stock/' + s.ts_code)">
              <td class="font-mono" style="font-size:12px;">{{ s.ts_code }}</td>
              <td style="font-size:11px;">{{ s.trade_date || s.time }}</td>
              <td><span class="badge badge-warn">{{ s.shock_type || '异动' }}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state" style="padding:24px;"><h4>暂无异动</h4></div>
      </div>
    </div>
  </div>
</template>
