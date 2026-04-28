<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import type { EChartsOption } from 'echarts';
import BaseEChart from '../components/BaseEChart.vue';
import { useToast } from '../composables/useToast';
import { appHttp, http } from '../lib/http';
import {
  average, formatCompactNumber, formatMarketLabel, formatMarketTone,
  formatNumber, formatPercent, normalizeTradeDate, movingAverage, toNumber,
} from '../lib/format';
import type {
  ApiResponse, CyqChipItem, CyqPerfItem, FactorItem,
  HistoryItem, MoneyflowItem, RealtimePayload, StockDetail,
} from '../types/stock';

type StockTab = 'history' | 'tech' | 'moneyflow' | 'cyq';
type Indicator = 'macd' | 'kdj' | 'rsi' | 'boll';

const route = useRoute();
const router = useRouter();
const toast = useToast();
const ctx = window.__QUANT_APP_CONTEXT__;

const tsCode = computed(() => String(route.params.tsCode || '').toUpperCase());
const isAuth = computed(() => Boolean(ctx?.auth?.isAuthenticated));

const activeTab = ref<StockTab>('history');
const freq = ref<'daily' | 'weekly' | 'monthly'>('daily');
const indicator = ref<Indicator>('macd');
const historyDays = ref(250);
const historyLabel = ref('最近 250 天');

const stockInfo = ref<StockDetail | null>(null);
const realtime = ref<RealtimePayload | null>(null);
const historyData = ref<HistoryItem[]>([]);
const analysisHistory = ref<HistoryItem[]>([]);
const analysisFactors = ref<FactorItem[]>([]);
const moneyflowData = ref<MoneyflowItem[]>([]);
const cyqPerf = ref<CyqPerfItem[]>([]);
const cyqChips = ref<CyqChipItem[]>([]);

const loading = ref({ stock: false, realtime: false, history: false, analysis: false, moneyflow: false, cyq: false });
const errors = ref({ stock: '', realtime: '', history: '', analysis: '', moneyflow: '', cyq: '' });
const notice = ref<{ tone: string; text: string } | null>(null);
const watchlistLoading = ref(false);
const watchlistOverride = ref<boolean | null>(null);
const analysisLoaded = ref(false);
const moneyflowLoaded = ref(false);
const cyqLoaded = ref(false);
const selectedMoneyflowDate = ref('');
const selectedCyqDate = ref('');

const quote = computed(() => realtime.value?.quote ?? null);
const currentPrice = computed(() => toNumber(quote.value?.price) || toNumber(stockInfo.value?.daily_basic?.close) || toNumber(historyData.value[0]?.close));
const isWatchlist = computed(() => watchlistOverride.value !== null ? watchlistOverride.value : Boolean(realtime.value?.is_watchlist));

const priceTone = computed(() => { const c = toNumber(quote.value?.change); return c > 0 ? 'text-up' : c < 0 ? 'text-down' : ''; });
const priceArrow = computed(() => { const c = toNumber(quote.value?.change); return c > 0 ? '+' : c < 0 ? '-' : ''; });

const tabs: Array<{ id: StockTab; label: string }> = [
  { id: 'history', label: '历史数据' }, { id: 'tech', label: '技术分析' },
  { id: 'moneyflow', label: '资金流向' }, { id: 'cyq', label: '筹码分布' },
];

const indicators: Array<{ id: Indicator; label: string }> = [
  { id: 'macd', label: 'MACD' }, { id: 'kdj', label: 'KDJ' }, { id: 'rsi', label: 'RSI' }, { id: 'boll', label: '布林带' },
];

async function fetchStock() { loading.value.stock = true; try { const r = await http.get<ApiResponse<StockDetail>>(`/stocks/${tsCode.value}`); if (r.data.code === 200) stockInfo.value = r.data.data; } catch (e) { errors.value.stock = '加载失败'; } loading.value.stock = false; }
async function fetchRealtime() { loading.value.realtime = true; try { const r = await http.get<ApiResponse<RealtimePayload>>(`/stocks/${tsCode.value}/realtime`, { params: { freq: freq.value } }); if (r.data.code === 200) { realtime.value = r.data.data; if (watchlistOverride.value === null) watchlistOverride.value = Boolean(r.data.data.is_watchlist); } } catch { /* */ } loading.value.realtime = false; }
async function fetchHistory(days: number, label: string) { loading.value.history = true; historyDays.value = days; historyLabel.value = label; try { const r = await http.get<ApiResponse<HistoryItem[]>>(`/stocks/${tsCode.value}/history`, { params: { limit: days } }); if (r.data.code === 200) historyData.value = r.data.data || []; } catch { /* */ } loading.value.history = false; }

async function loadAnalysis() { if (analysisLoaded.value) return; loading.value.analysis = true; try { const [hr, fr] = await Promise.allSettled([http.get<ApiResponse<HistoryItem[]>>(`/stocks/${tsCode.value}/history`, { params: { limit: 750 } }), http.get<ApiResponse<FactorItem[]>>(`/stocks/${tsCode.value}/factors`, { params: { limit: 750 } })]); if (hr.status === 'fulfilled' && hr.value.data.code === 200) analysisHistory.value = hr.value.data.data || []; if (fr.status === 'fulfilled' && fr.value.data.code === 200) analysisFactors.value = fr.value.data.data || []; analysisLoaded.value = true; } catch { errors.value.analysis = '加载失败'; } loading.value.analysis = false; }
async function loadMoneyflow() { if (moneyflowLoaded.value) return; loading.value.moneyflow = true; try { const r = await http.get<ApiResponse<MoneyflowItem[]>>(`/stocks/${tsCode.value}/moneyflow`, { params: { limit: 250 } }); if (r.data.code === 200) { moneyflowData.value = r.data.data || []; selectedMoneyflowDate.value = moneyflowData.value[0]?.trade_date || ''; moneyflowLoaded.value = true; } } catch { errors.value.moneyflow = '加载失败'; } loading.value.moneyflow = false; }
async function loadCyq() { if (cyqLoaded.value) return; loading.value.cyq = true; try { const [cr, pr] = await Promise.allSettled([http.get<ApiResponse<CyqChipItem[]>>(`/stocks/${tsCode.value}/cyq_chips`, { params: { limit_days: 5 } }), http.get<ApiResponse<CyqPerfItem[]>>(`/stocks/${tsCode.value}/cyq`, { params: { limit: 250 } })]); if (cr.status === 'fulfilled' && cr.value.data.code === 200) cyqChips.value = cr.value.data.data || []; if (pr.status === 'fulfilled' && pr.value.data.code === 200) cyqPerf.value = pr.value.data.data || []; cyqLoaded.value = true; } catch { errors.value.cyq = '加载失败'; } loading.value.cyq = false; }

async function addWatchlist() { watchlistLoading.value = true; try { const r = await http.post<ApiResponse<unknown>>(`/watchlist/${tsCode.value}`); watchlistOverride.value = true; toast.success(r.data.message || '已加入自选'); } catch (e) { toast.error(axios.isAxiosError(e) ? e.response?.data?.message || '失败' : '失败'); } watchlistLoading.value = false; }

async function switchTab(tab: StockTab) { activeTab.value = tab; if (tab === 'tech') await loadAnalysis(); if (tab === 'moneyflow') await loadMoneyflow(); if (tab === 'cyq') await loadCyq(); }

async function loadPage() {
  await Promise.allSettled([fetchStock(), fetchRealtime(), fetchHistory(250, '最近 250 天')]);
  await switchTab(activeTab.value);
}

watch(tsCode, loadPage, { immediate: true });
watch([stockInfo, quote], () => { const name = stockInfo.value?.name || quote.value?.name; document.title = name ? `${name} (${tsCode.value})` : tsCode.value; });

/* ---- Computed charts ---- */
const realtimeChartOption = computed(() => {
  const s = realtime.value?.series; if (!Array.isArray(s) || !s.length) return null;
  const labels = s.map(i => i.label || '');
  const prices = s.map(i => toNumber(i.price ?? i.close));
  const vols = s.map(i => toNumber(i.volume));
  const ohlc = s.map(i => [toNumber(i.open), toNumber(i.price ?? i.close), toNumber(i.low), toNumber(i.high)]);
  const ma5 = freq.value === 'daily' ? movingAverage(prices, 5) : [];
  const ma20 = freq.value === 'daily' ? movingAverage(prices, 20) : [];
  return {
    tooltip: { trigger: 'axis' }, grid: [{ left: 52, right: 20, top: 30, height: '58%' }, { left: 52, right: 20, top: '74%', height: '16%' }],
    xAxis: [{ type: 'category', data: labels, axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)', hideOverlap: true } }, { type: 'category', gridIndex: 1, data: labels, axisLabel: { show: false } }],
    yAxis: [{ scale: true, splitLine: { lineStyle: { color: 'rgba(10,11,13,0.04)' } }, axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)' } }, { scale: true, gridIndex: 1, splitLine: { show: false } }],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 }, { type: 'slider', xAxisIndex: [0, 1], bottom: 6, height: 16, borderColor: 'rgba(10,11,13,0.08)', fillerColor: 'rgba(0,82,255,0.08)' }],
    series: [
      { type: 'candlestick', data: ohlc, itemStyle: { color: '#ff3b30', color0: '#34c759', borderColor: '#ff3b30', borderColor0: '#34c759' } },
      ...(freq.value === 'daily' ? [{ type: 'line', data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#ff9f0a' } }, { type: 'line', data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#0052ff' } }] : []),
      { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: vols, itemStyle: { color: 'rgba(0,82,255,0.22)' } },
    ],
  } as EChartsOption;
});

const indicatorChartOption = computed(() => {
  const factors = [...analysisFactors.value].sort((a, b) => normalizeTradeDate(a.trade_date).localeCompare(normalizeTradeDate(b.trade_date)));
  if (!factors.length) return null;
  const labels = factors.map(f => f.trade_date || '');
  const base = { tooltip: { trigger: 'axis' }, grid: { left: 42, right: 16, top: 32, bottom: 24 }, xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)', show: false } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(10,11,13,0.04)' } } } };
  if (indicator.value === 'macd') return { ...base, legend: { data: ['MACD', 'DIF', 'DEA'] }, series: [{ name: 'MACD', type: 'bar', data: factors.map(f => toNumber(f.macd)), itemStyle: { color: (p: { data?: unknown }) => toNumber(p.data) >= 0 ? '#ff3b30' : '#34c759' } }, { name: 'DIF', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.macd_dif)), lineStyle: { color: '#0052ff', width: 1.5 } }, { name: 'DEA', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.macd_dea)), lineStyle: { color: '#ff9f0a', width: 1.5 } }] } as EChartsOption;
  if (indicator.value === 'kdj') return { ...base, legend: { data: ['K', 'D', 'J'] }, yAxis: { ...base.yAxis, min: 0, max: 100 }, series: [{ name: 'K', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.kdj_k)), lineStyle: { color: '#0052ff', width: 1.5 } }, { name: 'D', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.kdj_d)), lineStyle: { color: '#34c759', width: 1.5 } }, { name: 'J', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.kdj_j)), lineStyle: { color: '#ff3b30', width: 1.5 } }] } as EChartsOption;
  if (indicator.value === 'rsi') return { ...base, legend: { data: ['RSI6', 'RSI12', 'RSI24'] }, yAxis: { ...base.yAxis, min: 0, max: 100 }, series: [{ name: 'RSI6', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.rsi_6)), lineStyle: { color: '#ff3b30', width: 1.5 } }, { name: 'RSI12', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.rsi_12)), lineStyle: { color: '#0052ff', width: 1.5 } }, { name: 'RSI24', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.rsi_24)), lineStyle: { color: '#af52de', width: 1.5 } }] } as EChartsOption;
  return { ...base, legend: { data: ['收盘', '上轨', '中轨', '下轨'] }, series: [{ name: '收盘', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.close)), lineStyle: { color: '#0a0b0d', width: 1.5 } }, { name: '上轨', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.boll_upper)), lineStyle: { color: '#ff3b30', width: 1 } }, { name: '中轨', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.boll_mid)), lineStyle: { color: '#0052ff', width: 1 } }, { name: '下轨', type: 'line', smooth: true, symbol: 'none', data: factors.map(f => toNumber(f.boll_lower)), lineStyle: { color: '#34c759', width: 1 } }] } as EChartsOption;
});

const moneyflowChartOption = computed(() => {
  const e = moneyflowData.value.find(i => i.trade_date === selectedMoneyflowDate.value) || moneyflowData.value[0]; if (!e) return null;
  return { title: { text: '分单资金', subtext: e.trade_date || '', left: 'center', textStyle: { fontSize: 13 } }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { data: ['买入', '卖出'], top: 26 }, grid: { left: '4%', right: '4%', bottom: '6%', containLabel: true }, xAxis: { type: 'category', data: ['特大单', '大单', '中单', '小单'] }, yAxis: { type: 'value' }, series: [{ name: '买入', type: 'bar', data: [toNumber(e.buy_elg_amount), toNumber(e.buy_lg_amount), toNumber(e.buy_md_amount), toNumber(e.buy_sm_amount)], itemStyle: { color: '#ff3b30' } }, { name: '卖出', type: 'bar', data: [-toNumber(e.sell_elg_amount), -toNumber(e.sell_lg_amount), -toNumber(e.sell_md_amount), -toNumber(e.sell_sm_amount)], itemStyle: { color: '#34c759' } }] } as EChartsOption;
});

const netflowChartOption = computed(() => {
  if (!moneyflowData.value.length) return null;
  const ordered = [...moneyflowData.value].reverse();
  return { title: { text: '净流入趋势', left: 'center', textStyle: { fontSize: 13 } }, tooltip: { trigger: 'axis' }, grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true }, xAxis: { type: 'category', data: ordered.map(i => i.trade_date || ''), axisLabel: { rotate: 45, fontSize: 10 } }, yAxis: { type: 'value' }, dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 6, height: 16 }], series: [{ type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.net_mf_amount)), lineStyle: { color: '#0052ff', width: 1.5 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(0,82,255,0.2)' }, { offset: 1, color: 'rgba(0,82,255,0)' }] } } }] } as EChartsOption;
});

const cyqChipsChartOption = computed(() => {
  if (!selectedCyqDate.value) return null;
  const dayData = [...cyqChips.value].filter(i => i.trade_date === selectedCyqDate.value).sort((a, b) => toNumber(a.price) - toNumber(b.price));
  if (!dayData.length) return null;
  return { title: { text: `筹码分布 (${selectedCyqDate.value})`, left: 'center', textStyle: { fontSize: 13 } }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, grid: { left: '12%', right: '8%', top: 40, bottom: 30 }, xAxis: { type: 'value', name: '占比(%)', axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(10,11,13,0.04)', type: 'dashed' } } }, yAxis: { type: 'category', data: dayData.map(i => formatNumber(i.price, 2)), axisLabel: { fontSize: 10 } }, series: [{ type: 'bar', data: dayData.map((item, idx) => { const price = toNumber(item.price); const near = currentPrice.value > 0 && Math.abs(price - currentPrice.value) / currentPrice.value < 0.005; return { value: toNumber(item.percent), itemStyle: { color: near ? '#ff3b30' : price <= currentPrice.value ? 'rgba(52,199,89,0.7)' : 'rgba(10,11,13,0.16)' } }; }), barWidth: '70%' }] } as EChartsOption;
});

const cyqCostChartOption = computed(() => {
  if (!cyqPerf.value.length) return null;
  const ordered = [...cyqPerf.value].reverse();
  return { title: { text: '成本分位曲线', left: 'center', textStyle: { fontSize: 13 } }, tooltip: { trigger: 'axis' }, legend: { data: ['5%', '15%', '50%', '85%', '95%', '加权'], top: 28 }, grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true }, xAxis: { type: 'category', data: ordered.map(i => i.trade_date || ''), axisLabel: { rotate: 45, fontSize: 10 } }, yAxis: { type: 'value' }, dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 6, height: 16 }], series: [{ name: '5%', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.cost_5pct)) }, { name: '15%', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.cost_15pct)) }, { name: '50%', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.cost_50pct)), lineStyle: { width: 2 } }, { name: '85%', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.cost_85pct)) }, { name: '95%', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.cost_95pct)) }, { name: '加权', type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.weight_avg)), lineStyle: { type: 'dashed', width: 2 } }] } as EChartsOption;
});

const cyqWinnerChartOption = computed(() => {
  if (!cyqPerf.value.length) return null;
  const ordered = [...cyqPerf.value].reverse();
  return { title: { text: '胜率变化', left: 'center', textStyle: { fontSize: 13 } }, tooltip: { trigger: 'axis' }, grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true }, xAxis: { type: 'category', data: ordered.map(i => i.trade_date || ''), axisLabel: { rotate: 45, fontSize: 10 } }, yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } }, dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 6, height: 16 }], series: [{ type: 'line', smooth: true, symbol: 'none', data: ordered.map(i => toNumber(i.winner_rate)), lineStyle: { color: '#34c759', width: 1.8 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(52,199,89,0.16)' }, { offset: 1, color: 'rgba(52,199,89,0)' }] } }, markLine: { data: [{ yAxis: 50 }], lineStyle: { color: '#ff3b30', type: 'dashed' } } }] } as EChartsOption;
});

const historyRows = computed(() => historyData.value.slice(0, 30));
const analysisTableRows = computed(() => { const fm = new Map(analysisFactors.value.map(i => [normalizeTradeDate(i.trade_date), i])); return analysisHistory.value.slice(0, 20).map(r => ({ ...r, ...(fm.get(normalizeTradeDate(r.trade_date)) || {}) })); });
const moneyflowDates = computed(() => moneyflowData.value.map(i => i.trade_date || '').filter(Boolean));
</script>

<template>
  <div>
    <div v-if="notice" class="alert" :class="'alert-' + notice.tone">{{ notice.text }}</div>

    <!-- Header: identity + price + actions -->
    <div class="card">
      <div class="flex-between" style="flex-wrap:wrap;gap:16px;">
        <div>
          <div class="text-xs text-muted" style="margin-bottom:4px;">Stock Detail</div>
          <h3 style="font-size:20px;font-weight:600;letter-spacing:-0.022em;">
            {{ stockInfo?.name || quote?.name || tsCode }}
            <span style="font-size:14px;color:var(--text-muted);font-weight:400;">{{ stockInfo?.symbol || tsCode }}</span>
          </h3>
          <div v-if="stockInfo" class="text-xs text-muted mt-1">
            {{ stockInfo.industry || '--' }} · {{ stockInfo.area || '--' }} · 上市 {{ stockInfo.list_date || '--' }}
          </div>
        </div>
        <div class="flex-between gap-2" style="flex-wrap:wrap;">
          <span v-if="quote" class="font-mono" style="font-size:28px;font-weight:600;letter-spacing:-0.03em;" :class="priceTone">{{ priceArrow }}{{ formatNumber(quote.price, 2) }}</span>
          <span v-if="quote" :class="priceTone" style="font-size:15px;font-weight:500;">{{ formatPercent(quote.pct_chg) }}</span>
          <div class="flex-between gap-1">
            <button class="btn btn-primary btn-sm" :disabled="watchlistLoading" @click="addWatchlist">{{ isWatchlist ? '已自选' : '+ 自选' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tab-bar">
      <button v-for="t in tabs" :key="t.id" class="tab-btn" :class="{ active: activeTab === t.id }" @click="switchTab(t.id)">{{ t.label }}</button>
    </div>

    <!-- HISTORY TAB -->
    <div v-if="activeTab === 'history'" class="card" style="padding:0;overflow-x:auto;">
      <div class="card-header" style="padding:16px 16px 12px;">
        <h3>{{ historyLabel }}</h3>
        <div class="tab-bar">
          <button v-for="d in [60,120,250,750]" :key="d" class="tab-btn" :class="{ active: historyDays === d }" @click="fetchHistory(d, `最近 ${d} 天`)">{{ d === 750 ? '3年' : d + '天' }}</button>
        </div>
      </div>
      <table class="data-table w-full">
        <thead><tr><th>日期</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th><th>成交量</th><th>成交额</th><th>涨跌幅</th></tr></thead>
        <tbody>
          <tr v-for="item in historyRows" :key="item.trade_date ?? ''">
            <td class="font-bold">{{ item.trade_date }}</td>
            <td>{{ formatNumber(item.open, 2) }}</td>
            <td class="text-up">{{ formatNumber(item.high, 2) }}</td>
            <td class="text-down">{{ formatNumber(item.low, 2) }}</td>
            <td class="font-bold">{{ formatNumber(item.close, 2) }}</td>
            <td>{{ formatNumber(toNumber(item.vol) / 10000, 1) }}万手</td>
            <td>{{ formatNumber(toNumber(item.amount) / 10000, 0) }}万</td>
            <td :class="toNumber(item.pct_chg) >= 0 ? 'text-up' : 'text-down'">{{ formatPercent(item.pct_chg) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!historyRows.length" class="empty-state"><h4>暂无数据</h4></div>
    </div>

    <!-- TECH ANALYSIS TAB -->
    <div v-if="activeTab === 'tech'">
      <div v-if="loading.analysis" class="card"><div class="skeleton" style="height:200px;" /></div>
      <template v-else-if="analysisHistory.length">
        <!-- Summary -->
        <div class="grid-2">
          <div class="card">
            <div class="card-header"><h3>实时分析</h3></div>
            <div v-if="analysisFactors.length" class="text-sm">
              <div class="stat-item mb-2" v-for="m in [{ l: '最新收盘', v: formatNumber(analysisHistory[0]?.close, 2) },{ l: 'RSI(6)', v: formatNumber(analysisFactors[analysisFactors.length-1]?.rsi_6, 2) },{ l: 'MACD', v: formatNumber(analysisFactors[analysisFactors.length-1]?.macd, 4) },{ l: 'KDJ-K', v: formatNumber(analysisFactors[analysisFactors.length-1]?.kdj_k, 2) }]" :key="m.l">
                <span class="stat-label">{{ m.l }}</span>
                <span class="stat-value" style="font-size:16px;">{{ m.v }}</span>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="card-header"><h3>最新行情</h3></div>
            <div v-if="quote" class="stat-grid">
              <div class="stat-item"><div class="stat-label">今开</div><div class="stat-value" style="font-size:18px;">{{ formatNumber(quote.open, 2) }}</div></div>
              <div class="stat-item"><div class="stat-label">昨收</div><div class="stat-value" style="font-size:18px;">{{ formatNumber(quote.pre_close, 2) }}</div></div>
              <div class="stat-item"><div class="stat-label">最高</div><div class="stat-value text-up" style="font-size:18px;">{{ formatNumber(quote.high, 2) }}</div></div>
              <div class="stat-item"><div class="stat-label">最低</div><div class="stat-value text-down" style="font-size:18px;">{{ formatNumber(quote.low, 2) }}</div></div>
              <div class="stat-item"><div class="stat-label">成交量</div><div class="stat-value font-mono" style="font-size:16px;">{{ formatCompactNumber(quote.volume) }}</div></div>
              <div class="stat-item"><div class="stat-label">换手率</div><div class="stat-value" style="font-size:18px;">{{ formatPercent(quote.turnover_rate, 2, false) }}</div></div>
            </div>
          </div>
        </div>
        <!-- Indicator chart -->
        <div class="card">
          <div class="card-header">
            <h3>技术指标</h3>
            <div class="pill-group"><button v-for="ind in indicators" :key="ind.id" class="tab-btn" :class="{ active: indicator === ind.id }" @click="indicator = ind.id">{{ ind.label }}</button></div>
          </div>
          <BaseEChart v-if="indicatorChartOption" :option="indicatorChartOption" height="340px" />
          <div v-else class="empty-state" style="padding:32px;"><h4>指标数据不可用</h4></div>
        </div>
        <!-- Realtime chart -->
        <div class="card">
          <div class="card-header">
            <h3>实时行情</h3>
            <div class="pill-group"><button v-for="f in [{id:'daily',l:'日K'},{id:'weekly',l:'周K'},{id:'monthly',l:'月K'}]" :key="f.id" class="tab-btn" :class="{ active: freq === f.id }" @click="freq = f.id as any; fetchRealtime()">{{ f.l }}</button></div>
          </div>
          <BaseEChart v-if="realtimeChartOption" :option="realtimeChartOption" height="400px" />
        </div>
        <!-- Analysis table -->
        <div class="card" style="padding:0;overflow-x:auto;">
          <div class="card-header" style="padding:16px;"><h3>分析明细</h3></div>
          <table class="data-table w-full">
            <thead><tr><th>日期</th><th>开盘</th><th>收盘</th><th>涨跌幅</th><th>RSI6</th><th>MACD</th><th>KDJ-K</th></tr></thead>
            <tbody><tr v-for="item in analysisTableRows" :key="item.trade_date ?? ''"><td class="font-bold">{{ item.trade_date }}</td><td>{{ formatNumber(item.open, 2) }}</td><td class="font-bold">{{ formatNumber(item.close, 2) }}</td><td :class="toNumber(item.pct_chg) >= 0 ? 'text-up' : 'text-down'">{{ formatPercent(item.pct_chg) }}</td><td :class="toNumber(item.rsi_6) > 70 ? 'text-up' : toNumber(item.rsi_6) < 30 ? 'text-down' : ''">{{ formatNumber(item.rsi_6, 2) }}</td><td :class="toNumber(item.macd) >= 0 ? 'text-up' : 'text-down'">{{ formatNumber(item.macd, 4) }}</td><td>{{ formatNumber(item.kdj_k, 2) }}</td></tr></tbody>
          </table>
        </div>
      </template>
      <div v-else class="card empty-state"><h4>暂无技术分析数据</h4><p class="text-sm text-muted">点击上方"技术分析"标签加载</p></div>
    </div>

    <!-- MONEYFLOW TAB -->
    <div v-if="activeTab === 'moneyflow'">
      <div v-if="loading.moneyflow" class="card"><div class="skeleton" style="height:200px;" /></div>
      <template v-else-if="moneyflowData.length">
        <div class="card">
          <div class="card-header"><h3>资金流向</h3><select v-model="selectedMoneyflowDate" class="form-select" style="width:auto;font-size:12px;"><option v-for="d in moneyflowDates.slice(0,60)" :key="d" :value="d">{{ d }}</option></select></div>
          <div class="grid-2">
            <BaseEChart v-if="moneyflowChartOption" :option="moneyflowChartOption" height="340px" />
            <BaseEChart v-if="netflowChartOption" :option="netflowChartOption" height="340px" />
          </div>
        </div>
        <div class="card" style="padding:0;overflow-x:auto;">
          <div class="card-header" style="padding:16px;"><h3>资金流向明细</h3></div>
          <table class="data-table w-full"><thead><tr><th>日期</th><th>净流入</th><th>特大买</th><th>特大卖</th><th>大单买</th><th>大单卖</th></tr></thead>
            <tbody><tr v-for="item in moneyflowData.slice(0,30)" :key="item.trade_date ?? ''"><td>{{ item.trade_date }}</td><td :class="toNumber(item.net_mf_amount) >= 0 ? 'text-up' : 'text-down'">{{ formatNumber(item.net_mf_amount, 0) }}</td><td class="text-up">{{ formatNumber(item.buy_elg_amount, 0) }}</td><td class="text-down">{{ formatNumber(item.sell_elg_amount, 0) }}</td><td class="text-up">{{ formatNumber(item.buy_lg_amount, 0) }}</td><td class="text-down">{{ formatNumber(item.sell_lg_amount, 0) }}</td></tr></tbody>
          </table>
        </div>
      </template>
      <div v-else class="card empty-state"><h4>暂无资金流向数据</h4></div>
    </div>

    <!-- CYQ TAB -->
    <div v-if="activeTab === 'cyq'">
      <div v-if="loading.cyq" class="card"><div class="skeleton" style="height:200px;" /></div>
      <template v-else-if="cyqPerf.length || cyqChips.length">
        <div class="card">
          <div class="card-header"><h3>筹码分布</h3><select v-if="cyqChips.length" v-model="selectedCyqDate" class="form-select" style="width:auto;font-size:12px;"><option v-for="d in [...new Set(cyqChips.map(i=>i.trade_date).filter(Boolean))].sort().reverse().slice(0,10)" :key="(d ?? '')" :value="d">{{ d }}</option></select></div>
          <div class="grid-2">
            <BaseEChart v-if="cyqChipsChartOption" :option="cyqChipsChartOption" height="460px" />
            <div>
              <BaseEChart v-if="cyqWinnerChartOption" :option="cyqWinnerChartOption" height="220px" />
              <div v-if="currentPrice" class="stat-grid mt-2"><div class="stat-item"><div class="stat-label">当前价</div><div class="stat-value" style="font-size:18px;">{{ formatNumber(currentPrice, 2) }}</div></div></div>
            </div>
          </div>
        </div>
        <div v-if="cyqCostChartOption" class="card"><BaseEChart :option="cyqCostChartOption" height="320px" /></div>
        <div v-if="cyqPerf.length" class="card" style="padding:0;overflow-x:auto;">
          <div class="card-header" style="padding:16px;"><h3>筹码胜率明细</h3></div>
          <table class="data-table w-full"><thead><tr><th>日期</th><th>历史低</th><th>5%</th><th>50%</th><th>95%</th><th>历史高</th><th>加权</th><th>胜率</th></tr></thead>
            <tbody><tr v-for="item in cyqPerf.slice(0,30)" :key="item.trade_date ?? ''"><td>{{ item.trade_date }}</td><td class="text-down">{{ formatNumber(item.his_low, 2) }}</td><td>{{ formatNumber(item.cost_5pct, 2) }}</td><td class="font-bold">{{ formatNumber(item.cost_50pct, 2) }}</td><td>{{ formatNumber(item.cost_95pct, 2) }}</td><td class="text-up">{{ formatNumber(item.his_high, 2) }}</td><td class="font-bold">{{ formatNumber(item.weight_avg, 2) }}</td><td :class="toNumber(item.winner_rate) >= 50 ? 'text-up' : 'text-down'">{{ formatPercent(item.winner_rate, 2, false) }}</td></tr></tbody>
          </table>
        </div>
      </template>
      <div v-else class="card empty-state"><h4>暂无筹码分布数据</h4></div>
    </div>
  </div>
</template>

<style scoped>
.pill-group { display: flex; gap: 2px; padding: 2px; background: var(--bg-stat); border-radius: var(--radius-full); }
.pill-group .tab-btn { padding: 5px 14px; border-radius: var(--radius-full); font-family: var(--font-sans); font-size: 14px; font-weight: 600; color: var(--text-secondary); border: none; background: transparent; cursor: pointer; transition: all var(--transition); }
.pill-group .tab-btn.active { background: var(--bg-card); color: var(--text-primary); }
</style>
