<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import BaseEChart from '../components/BaseEChart.vue';
import { useToast } from '../composables/useToast';
import { formatNumber, formatPercent, formatCompactNumber, debounce } from '../lib/format';
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
const rankingSort = ref('pct_change');
const shockData = ref<Record<string, unknown>[]>([]);
const loading = ref(false);
const error = ref('');
const autoRefresh = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;
let refreshCountdown = ref(0);
let countdownTimer: ReturnType<typeof setInterval> | null = null;

const searchQuery = ref('');
const searchResults = ref<Record<string, unknown>[]>([]);
const showSearch = ref(false);

const chartMode = ref<'daily' | 'intraday'>('daily');

async function loadDashboard() {
  error.value = '';
  try {
    const codeList = codes.value || '';
    const [dash, idx, rank, shock] = await Promise.all([
      getMonitorDashboard(codeList),
      getMarketOverview(),
      getRanking(rankingSort.value, 20),
      getShock(undefined, 30),
    ]);
    stocks.value = (dash.stocks || []) as Record<string, unknown>[];
    indices.value = (idx.indices || []) as Record<string, unknown>[];
    ranking.value = rank.data || [];
    shockData.value = shock.data || [];
    if (stocks.value.length && !activeStock.value) activeStock.value = stocks.value[0];
  } catch {
    error.value = '数据加载失败';
    toast.error('监控数据加载失败');
  }
}

onMounted(() => { loadDashboard(); });
onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (countdownTimer) clearInterval(countdownTimer);
});

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshCountdown.value = 30;
    refreshTimer = setInterval(() => { loadDashboard(); refreshCountdown.value = 30; }, 30000);
    countdownTimer = setInterval(() => { if (refreshCountdown.value > 0) refreshCountdown.value--; }, 1000);
  } else {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
  }
}

async function doSearch() {
  if (searchQuery.value.length < 1) { searchResults.value = []; showSearch.value = false; return; }
  try {
    const res = await searchStocks(searchQuery.value);
    searchResults.value = (res.data || []) as Record<string, unknown>[];
    showSearch.value = true;
  } catch { /* */ }
}
const debouncedSearch = debounce(doSearch, 300);

function addStock(item: Record<string, unknown>) {
  const c = item.ts_code as string;
  if (c && !codes.value.includes(c)) codes.value = codes.value ? codes.value + ',' + c : c;
  showSearch.value = false;
  searchQuery.value = '';
  loadDashboard();
}

function selectStock(s: Record<string, unknown>) { activeStock.value = s; }

const indexOption = computed(() => {
  const series = (activeStock.value?.series || []) as Record<string, unknown>[];
  const dates = series.map((s) => s.label || '');
  const vols = series.map((s) => Number(s.volume || 0));
  const candleData = series.map((s) => [Number(s.open || 0), Number(s.close || 0), Number(s.low || 0), Number(s.high || 0)] as [number, number, number, number]);
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 70, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', splitLine: { lineStyle: { color: '#f0f0f0' } } },
      { type: 'value', splitLine: { show: false } },
    ],
    series: [
      {
        name: '价格', type: 'candlestick', data: candleData,
        itemStyle: { color: '#e15241', color0: '#22ab5e', borderColor: '#e15241', borderColor0: '#22ab5e' },
      },
      { name: '成交量', type: 'bar', data: vols, yAxisIndex: 1, itemStyle: { color: 'rgba(26,115,232,.3)' } },
    ],
  } as EChartsOption;
});

const signalItems = computed(() => {
  const sig = activeStock.value?.signals as Record<string, unknown> | undefined;
  if (!sig) return [];
  return [
    { label: '成交量', key: 'volume', icon: '📊' },
    { label: '动量', key: 'momentum', icon: '📈' },
    { label: 'MACD', key: 'macd', icon: '📉' },
    { label: '波动率', key: 'volatility', icon: '📐' },
  ].map((item) => ({
    ...item,
    value: sig[item.key] || '--',
    tone: String(sig[item.key] || '').includes('强') || String(sig[item.key] || '').includes('多') ? 'up' : 'normal',
  }));
});
</script>

<template>
  <div>
    <!-- Stock Input -->
    <div class="card mb-3">
      <div class="card-body">
        <div class="flex-between gap-2" style="flex-wrap:wrap;">
          <div style="display:flex;gap:.5rem;flex:1;">
            <input v-model="codes" class="form-input" placeholder="输入股票代码，逗号分隔" style="flex:1;" @keyup.enter="loadDashboard" />
            <div style="position:relative;">
              <input v-model="searchQuery" class="form-input" placeholder="搜索添加" @input="debouncedSearch" @focus="showSearch = searchResults.length > 0" style="width:180px;" />
              <div v-if="showSearch" class="search-dropdown">
                <div v-for="r in searchResults" :key="r.ts_code as string" class="search-item" @mousedown.prevent="addStock(r)">
                  {{ r.symbol || r.ts_code }} - {{ r.name }}
                </div>
              </div>
            </div>
          </div>
          <div class="flex-between gap-2">
            <button class="btn btn-primary btn-sm" @click="loadDashboard">应用</button>
            <button class="btn btn-sm" :class="autoRefresh ? 'btn-primary' : 'btn-outline'" @click="toggleAutoRefresh">
              {{ autoRefresh ? `自动刷新中(${refreshCountdown}s)` : '自动刷新' }}
            </button>
          </div>
        </div>
        <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>
      </div>
    </div>

    <!-- Index Strip -->
    <div v-if="indices.length" class="card mb-3" style="padding:.6rem 1.25rem;">
      <div style="display:flex;gap:1.5rem;overflow-x:auto;flex-wrap:wrap;">
        <span v-for="idx in indices" :key="idx.ts_code as string" class="text-sm font-mono">
          <strong>{{ (idx.price as number)?.toFixed(2) }}</strong>
          <span :class="(idx.pct_chg as number ?? 0) >= 0 ? 'text-down' : 'text-up'"> {{ formatPercent(idx.pct_chg) }}</span>
        </span>
      </div>
    </div>

    <!-- Stock Tabs -->
    <div v-if="stocks.length" class="tab-bar mb-3" style="flex-wrap:wrap;">
      <button v-for="s in stocks" :key="s.ts_code as string" class="tab-btn" :class="{ active: activeStock?.ts_code === s.ts_code }" @click="selectStock(s)">
        {{ s.name || s.ts_code }}
      </button>
    </div>

    <!-- Active Stock Detail -->
    <div v-if="activeStock" class="grid-2">
      <div class="card">
        <div class="card-header">
          <h3>{{ activeStock.name || activeStock.ts_code }}</h3>
          <div class="tab-bar">
            <button class="tab-btn" :class="{ active: chartMode === 'daily' }" @click="chartMode = 'daily'">日线</button>
            <button class="tab-btn" :class="{ active: chartMode === 'intraday' }" @click="chartMode = 'intraday'">分时</button>
          </div>
        </div>
        <div class="card-body">
          <div class="stat-grid mb-3">
            <div class="stat-card"><div class="stat-label">最新价</div><div class="stat-value font-mono">{{ (activeStock.quote as any)?.price }}</div></div>
            <div class="stat-card"><div class="stat-label">涨跌幅</div><div class="stat-value" :class="((activeStock.quote as any)?.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent((activeStock.quote as any)?.pct_chg) }}</div></div>
            <div class="stat-card"><div class="stat-label">成交量</div><div class="stat-value font-mono">{{ formatCompactNumber((activeStock.quote as any)?.volume) }}</div></div>
            <div class="stat-card"><div class="stat-label">成交额</div><div class="stat-value font-mono">{{ formatCompactNumber((activeStock.quote as any)?.amount) }}</div></div>
          </div>
          <BaseEChart :option="indexOption" height="360px" />
        </div>
      </div>

      <div>
        <div class="grid-2 mb-3">
          <div v-for="s in signalItems" :key="s.key" class="stat-card">
            <div class="stat-label">{{ s.icon }} {{ s.label }}</div>
            <div class="stat-value text-sm" style="margin-top:.25rem;">{{ s.value }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state when no stocks -->
    <div v-if="!stocks.length && !loading" class="card">
      <div class="card-body empty-state">
        <div class="empty-icon">📡</div>
        <h4>输入股票代码开始监控</h4>
        <p class="text-sm text-muted">支持多只股票，用逗号分隔</p>
      </div>
    </div>

    <!-- Ranking + Shock -->
    <div class="grid-2 mt-3">
      <div class="card">
        <div class="card-header">
          <h3>涨跌排行</h3>
          <select v-model="rankingSort" class="form-select" style="width:auto;" @change="loadDashboard">
            <option value="pct_change">涨跌幅</option>
            <option value="turnover_rate">换手率</option>
            <option value="amount">成交额</option>
          </select>
        </div>
        <div class="card-body" style="max-height:500px;overflow-y:auto;">
          <table class="data-table w-full" v-if="ranking.length">
            <thead><tr><th>#</th><th>股票</th><th>价格</th><th>涨跌幅</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in ranking" :key="i" class="clickable" @click="router.push('/stock/' + r.ts_code)">
                <td class="text-xs">{{ i + 1 }}</td>
                <td class="font-mono text-xs">{{ r.symbol || r.ts_code }} <span class="font-bold">{{ r.name }}</span></td>
                <td class="font-mono text-sm">{{ r.price || r.close }}</td>
                <td :class="(r.pct_chg as number ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(r.pct_chg) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="text-xs text-muted" style="text-align:center;padding:1rem;">暂无排行数据</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><h3>异动监控</h3><button class="btn btn-ghost btn-sm" @click="loadDashboard">刷新</button></div>
        <div class="card-body" style="max-height:500px;overflow-y:auto;">
          <table class="data-table w-full" v-if="shockData.length">
            <thead><tr><th>股票</th><th>时间</th><th>类型</th><th>描述</th></tr></thead>
            <tbody>
              <tr v-for="(s, i) in shockData" :key="i" class="clickable" @click="router.push('/stock/' + s.ts_code)">
                <td class="font-mono text-xs">{{ s.ts_code }}</td>
                <td class="text-xs">{{ s.trade_date || s.time }}</td>
                <td><span class="badge badge-warn">{{ s.shock_type || '异动' }}</span></td>
                <td class="text-xs">{{ s.description || s.reason }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-state"><h4>暂无异动</h4></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-dropdown {
  position:absolute;top:100%;left:0;right:0;z-index:10;
  background:var(--color-surface);border:1px solid var(--color-border);
  border-radius:var(--radius-md);max-height:200px;overflow-y:auto;
  box-shadow:var(--shadow-md);
}
.search-item {
  padding:.5rem .75rem;cursor:pointer;font-size:.82rem;
  transition: background var(--transition);
}
.search-item:hover { background: var(--color-surface-hover); }
</style>
