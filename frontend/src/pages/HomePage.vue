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
const news = ref<{ title: string; source: string; url: string; time: string }[]>([]);
const ranking = ref<Record<string, unknown>[]>([]);
const health = ref<string>('');
const loading = ref(true);
const error = ref('');
const selectedIndex = ref('000001.SH');
const klinePeriod = ref('3M');
const rankingSort = ref('pct_change');
const lastUpdated = ref('');
const autoRefresh = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;
let refreshCountdown = ref(0);
let countdownTimer: ReturnType<typeof setInterval> | null = null;

const indexMap: Record<string, string> = {
  '000001.SH': '上证指数', '399001.SZ': '深证成指', '399006.SZ': '创业板指',
  '000688.SH': '科创50', '000300.SH': '沪深300', '000905.SH': '中证500', '399005.SZ': '中小100',
};

const activeIndexName = computed(() => indexMap[selectedIndex.value] || selectedIndex.value);

const klineOption = computed<EChartsOption>(() => {
  const dates = klineData.value.map((d) => d.trade_date || '');
  const closes = klineData.value.map((d) => d.close ?? 0);
  const ma5 = calcMA(closes, 5);
  const ma10 = calcMA(closes, 10);
  const ma20 = calcMA(closes, 20);
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { formatter: (v: string) => v.slice(5) } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f0f0' } } },
    series: [
      { name: '收盘', type: 'line', data: closes, smooth: true, lineStyle: { width: 2, color: '#1a73e8' }, symbol: 'none' },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { width: 1, color: '#f2994a' }, symbol: 'none' },
      { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { width: 1, color: '#6c5ce7' }, symbol: 'none' },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { width: 1, color: '#00b894' }, symbol: 'none' },
    ],
  };
});

function calcMA(data: number[], days: number) {
  return data.map((_, i) => {
    if (i < days - 1) return null;
    return data.slice(i - days + 1, i + 1).reduce((a, b) => a + b, 0) / days;
  });
}

function updateTimestamp() {
  lastUpdated.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

async function loadOverview() {
  error.value = '';
  try {
    const ov = await getMarketOverview();
    overview.value = ov;
    updateTimestamp();
  } catch {
    error.value = '市场概览加载失败';
    toast.error('市场概览加载失败，请检查网络连接');
  }
}

async function loadKline() {
  try {
    const res = await getIndexKline(selectedIndex.value, klinePeriod.value);
    klineData.value = res.data || [];
  } catch {
    toast.error('K线数据加载失败');
  }
}

async function loadExtra() {
  try {
    const [n, r] = await Promise.all([
      http.get('/api/news', { params: { limit: 8 } }),
      http.get('/api/monitor/ranking', { params: { sort_by: rankingSort.value, limit: 10 } }),
    ]);
    news.value = n.data?.data || [];
    ranking.value = r.data?.data || [];
  } catch { /* non-critical */ }
}

async function checkHealth() {
  try {
    const h = await getMarketHealth();
    health.value = h.success ? '正常' : (h.message || '异常');
    if (h.success) toast.success('Tushare API 连接正常');
    else toast.warning('Tushare API: ' + (h.message || '状态异常'));
  } catch {
    health.value = '检查失败';
    toast.error('API 连通性检查失败');
  }
}

async function loadAll() {
  loading.value = true;
  await Promise.all([loadOverview(), loadKline(), loadExtra()]);
  loading.value = false;
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshCountdown.value = 60;
    refreshTimer = setInterval(() => {
      loadOverview();
      loadKline();
      refreshCountdown.value = 60;
    }, 60000);
    countdownTimer = setInterval(() => {
      if (refreshCountdown.value > 0) refreshCountdown.value--;
    }, 1000);
  } else {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    refreshCountdown.value = 0;
  }
}

onMounted(() => { loadAll(); });
onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (countdownTimer) clearInterval(countdownTimer);
});

const quickActions = [
  { to: '/stocks', label: '股票列表', icon: '📋' },
  { to: '/screen', label: '条件选股', icon: '🔍' },
  { to: '/backtest', label: '策略回测', icon: '⚡' },
  { to: '/monitor', label: '实时监控', icon: '📡' },
  { to: '/news', label: '新闻资讯', icon: '📰' },
  { to: '/ai-assistant', label: 'AI 助手', icon: '🤖' },
];
</script>

<template>
  <div>
    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="card" style="padding:.85rem 1.25rem;margin-bottom:1.25rem;">
        <div style="display:flex;gap:.75rem;flex-wrap:wrap;">
          <div v-for="i in 7" :key="i" class="skeleton" style="width:80px;height:32px;" />
        </div>
      </div>
      <div class="grid-2">
        <div class="card"><div class="card-body"><div class="skeleton" style="height:380px;" /></div></div>
        <div>
          <div class="card mb-3"><div class="card-body"><div v-for="i in 3" :key="i" class="skeleton" style="height:48px;margin-bottom:8px;" /></div></div>
          <div class="card"><div class="card-body"><div class="skeleton" style="height:120px;" /></div></div>
        </div>
      </div>
    </template>

    <template v-else>
      <!-- Error state -->
      <div v-if="error" class="alert alert-error mb-3">
        <span>{{ error }}</span>
        <button class="btn btn-sm btn-outline" @click="loadAll">重试</button>
      </div>

      <!-- Index Ticker Row -->
      <div class="card" style="padding:.85rem 1.25rem;margin-bottom:1.25rem;">
        <div style="display:flex;gap:.5rem;align-items:center;justify-content:space-between;flex-wrap:wrap;">
          <div style="display:flex;gap:.5rem;overflow-x:auto;flex-wrap:wrap;">
            <button
              v-for="(name, code) in indexMap" :key="code"
              class="btn btn-sm" :class="selectedIndex === code ? 'btn-primary' : 'btn-ghost'"
              @click="selectedIndex = code; loadKline()"
            >
              {{ name }}
            </button>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center;">
            <span v-if="autoRefresh" class="text-xs text-muted">下次刷新: {{ refreshCountdown }}s</span>
            <button class="btn btn-sm" :class="autoRefresh ? 'btn-primary' : 'btn-outline'" @click="toggleAutoRefresh">
              {{ autoRefresh ? '自动刷新中' : '自动刷新' }}
            </button>
          </div>
        </div>
        <div v-if="overview?.indices" style="display:flex;gap:1.5rem;margin-top:.75rem;flex-wrap:wrap;align-items:center;">
          <span v-for="idx in overview.indices" :key="idx.ts_code" class="text-sm font-mono">
            <strong>{{ idx.price?.toFixed(2) }}</strong>
            <span :class="(idx.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">
              {{ formatPercent(idx.pct_chg) }}
            </span>
          </span>
          <span v-if="lastUpdated" class="text-xs text-muted" style="margin-left:auto;">更新于 {{ lastUpdated }}</span>
        </div>
      </div>

      <!-- Breadth + Update -->
      <div v-if="overview" class="flex-between mb-3 text-sm text-muted">
        <span v-if="overview.breadth">上涨 {{ overview.breadth.up }} / 下跌 {{ overview.breadth.down }} / 平盘 {{ overview.breadth.flat }}</span>
        <span v-if="overview.summary">交易日期: {{ overview.summary.trade_date }}</span>
      </div>

      <div class="grid-2">
        <!-- K-line Chart -->
        <div class="card">
          <div class="card-header">
            <h3>{{ activeIndexName }} K线图</h3>
            <div class="tab-bar">
              <button v-for="p in ['1M','3M','1Y','3Y']" :key="p" class="tab-btn" :class="{ active: klinePeriod === p }" @click="klinePeriod = p; loadKline()">{{ p }}</button>
            </div>
          </div>
          <div class="card-body">
            <BaseEChart :option="klineOption" height="380px" />
          </div>
        </div>

        <!-- Market Summary -->
        <div>
          <div v-if="overview?.summary" class="card mb-3">
            <div class="card-header"><h3>市场概况</h3></div>
            <div class="card-body">
              <div class="stat-grid">
                <div class="stat-card"><div class="stat-label">成交额</div><div class="stat-value">{{ formatCompactNumber(overview.summary.total_turnover) }}</div></div>
                <div class="stat-card"><div class="stat-label">成交量</div><div class="stat-value">{{ formatCompactNumber(overview.summary.total_volume) }}</div></div>
                <div class="stat-card"><div class="stat-label">涨停</div><div class="stat-value text-down">{{ overview.summary.limit_up }}</div></div>
                <div class="stat-card"><div class="stat-label">跌停</div><div class="stat-value text-up">{{ overview.summary.limit_down }}</div></div>
              </div>
            </div>
          </div>

          <!-- System Status -->
          <div class="card">
            <div class="card-header"><h3>系统状态</h3><button class="btn btn-sm btn-outline" @click="checkHealth">测试连通性</button></div>
            <div class="card-body">
              <div class="text-sm text-muted mb-2">Tushare API 状态:
                <span :class="health === '正常' ? 'badge badge-down' : health ? 'badge badge-up' : 'badge badge-neutral'">
                  {{ health || '未检查' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="flex-between mt-4 mb-3 gap-2" style="flex-wrap:wrap;">
        <button v-for="item in quickActions" :key="item.to" class="btn btn-outline" @click="router.push(item.to)">
          {{ item.icon }} {{ item.label }}
        </button>
      </div>

      <!-- Ranking + News -->
      <div class="grid-2 mt-3">
        <div class="card">
          <div class="card-header">
            <h3>涨跌排行</h3>
            <select v-model="rankingSort" class="form-select" style="width:auto;" @change="loadExtra">
              <option value="pct_change">涨跌幅</option>
              <option value="turnover_rate">换手率</option>
              <option value="amount">成交额</option>
            </select>
          </div>
          <div class="card-body">
            <table class="data-table w-full" v-if="ranking.length">
              <thead><tr><th>#</th><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in ranking" :key="i" class="clickable" @click="router.push('/stock/' + r.ts_code)">
                  <td>{{ i + 1 }}</td>
                  <td class="font-mono">{{ r.ts_code }}</td>
                  <td>{{ r.name }}</td>
                  <td class="font-mono">{{ (r as any).price ?? (r as any).close }}</td>
                  <td :class="Number(r.pct_chg ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(r.pct_chg) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state"><div class="empty-icon">📊</div><h4>暂无数据</h4></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h3>快讯</h3></div>
          <div class="card-body">
            <div v-if="news.length" style="max-height:400px;overflow-y:auto;">
              <div v-for="(n, i) in news" :key="i" class="news-item">
                <a :href="n.url" target="_blank" class="news-title">{{ n.title }}</a>
                <div class="flex-between text-xs text-muted mt-1"><span>{{ n.source }}</span><span>{{ n.time }}</span></div>
              </div>
            </div>
            <div v-else class="empty-state"><h4>加载中...</h4></div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.news-item {
  padding: .6rem 0;
  border-bottom: 1px solid var(--color-border);
}
.news-item:last-child { border-bottom: none; }
.news-title {
  font-size: .85rem;
  color: var(--color-text);
  font-weight: 700;
  line-height: 1.4;
}
.news-title:hover { color: var(--color-primary); }
</style>
