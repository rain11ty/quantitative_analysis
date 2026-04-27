<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import type { EChartsOption } from 'echarts';

import BaseEChart from '../components/BaseEChart.vue';
import { appHttp, http } from '../lib/http';
import {
  average,
  formatCompactNumber,
  formatMarketLabel,
  formatMarketTone,
  formatNumber,
  formatPercent,
  normalizeTradeDate,
  movingAverage,
  toNumber,
} from '../lib/format';
import type {
  ApiResponse,
  CyqChipItem,
  CyqPerfItem,
  FactorItem,
  HistoryItem,
  MoneyflowItem,
  RealtimePayload,
  RealtimeSeriesItem,
  StockDetail,
} from '../types/stock';

type StockTab = 'history' | 'tech-analysis' | 'moneyflow' | 'cyq';
type IndicatorType = 'macd' | 'kdj' | 'rsi' | 'boll';
type RealtimeFrequency = 'daily' | 'weekly' | 'monthly';
type NoticeTone = 'success' | 'error' | 'info';

interface NoticeState {
  tone: NoticeTone;
  text: string;
}

interface OverviewMetric {
  label: string;
  value: string;
}

interface AnalysisSummary {
  trendTitle: string;
  trendChip: string;
  trendText: string;
  momentumText: string;
  volatilityText: string;
  monitorItems: string[];
}

const route = useRoute();
const router = useRouter();
const appContext = window.__QUANT_APP_CONTEXT__;

const activeTab = ref<StockTab>('history');
const realtimeFrequency = ref<RealtimeFrequency>('daily');
const indicatorType = ref<IndicatorType>('macd');

const stockInfo = ref<StockDetail | null>(null);
const realtimeData = ref<RealtimePayload | null>(null);
const historyData = ref<HistoryItem[]>([]);
const analysisHistoryData = ref<HistoryItem[]>([]);
const analysisFactorsData = ref<FactorItem[]>([]);
const moneyflowData = ref<MoneyflowItem[]>([]);
const cyqPerfData = ref<CyqPerfItem[]>([]);
const cyqChipsData = ref<CyqChipItem[]>([]);

const stockLoading = ref(false);
const realtimeLoading = ref(false);
const historyLoading = ref(false);
const analysisLoading = ref(false);
const moneyflowLoading = ref(false);
const cyqLoading = ref(false);
const watchlistLoading = ref(false);

const stockError = ref('');
const realtimeError = ref('');
const historyError = ref('');
const analysisError = ref('');
const moneyflowError = ref('');
const cyqError = ref('');
const notice = ref<NoticeState | null>(null);

const historyDisplayCount = ref(30);
const historyPreset = ref<number | 'custom'>(250);
const historyRangeLabel = ref('最近 250 个交易日');
const historyStartDate = ref('');
const historyEndDate = ref('');

const analysisLoaded = ref(false);
const moneyflowLoaded = ref(false);
const cyqLoaded = ref(false);
const cyqUnauthorized = ref(false);
const selectedMoneyflowDate = ref('');
const selectedCyqDate = ref('');
const watchlistOverride = ref<boolean | null>(null);
const savedAnalysisKey = ref('');

const tsCode = computed(() => String(route.params.tsCode || '').toUpperCase());
const quote = computed(() => realtimeData.value?.quote ?? null);
const isAuthenticated = computed(() => Boolean(appContext?.auth?.isAuthenticated));
const currentPrice = computed(() => {
  return (
    toNumber(quote.value?.price) ||
    toNumber(stockInfo.value?.daily_basic?.close) ||
    toNumber(historyData.value[0]?.close)
  );
});
const isWatchlist = computed(() => {
  if (watchlistOverride.value !== null) {
    return watchlistOverride.value;
  }
  return Boolean(realtimeData.value?.is_watchlist);
});

const tabItems: Array<{ id: StockTab; label: string }> = [
  { id: 'history', label: '历史数据' },
  { id: 'tech-analysis', label: '技术分析' },
  { id: 'moneyflow', label: '资金流向' },
  { id: 'cyq', label: '筹码分布' },
];

const indicatorItems: Array<{ id: IndicatorType; label: string }> = [
  { id: 'macd', label: 'MACD' },
  { id: 'kdj', label: 'KDJ' },
  { id: 'rsi', label: 'RSI' },
  { id: 'boll', label: '布林带' },
];

const frequencyItems: Array<{ id: RealtimeFrequency; label: string }> = [
  { id: 'daily', label: '日K' },
  { id: 'weekly', label: '周K' },
  { id: 'monthly', label: '月K' },
];

function parseTabQuery(value: unknown): StockTab {
  const raw = Array.isArray(value) ? value[0] : value;
  switch (raw) {
    case 'analysis':
    case 'tech-analysis':
      return 'tech-analysis';
    case 'moneyflow':
      return 'moneyflow';
    case 'cyq':
      return 'cyq';
    default:
      return 'history';
  }
}

function sortByTradeDateAsc<T extends { trade_date?: string | null }>(rows: T[]): T[] {
  return [...rows].sort((left, right) =>
    normalizeTradeDate(left.trade_date).localeCompare(normalizeTradeDate(right.trade_date)),
  );
}

function findFactorByTradeDate(factors: FactorItem[], tradeDate?: string | null): FactorItem | null {
  if (!factors.length) {
    return null;
  }

  const target = normalizeTradeDate(tradeDate);
  return (
    factors.find((item) => normalizeTradeDate(item.trade_date) === target) ||
    factors[factors.length - 1] ||
    factors[0]
  );
}

function resetPageState() {
  stockInfo.value = null;
  realtimeData.value = null;
  historyData.value = [];
  analysisHistoryData.value = [];
  analysisFactorsData.value = [];
  moneyflowData.value = [];
  cyqPerfData.value = [];
  cyqChipsData.value = [];

  stockError.value = '';
  realtimeError.value = '';
  historyError.value = '';
  analysisError.value = '';
  moneyflowError.value = '';
  cyqError.value = '';

  historyDisplayCount.value = 30;
  historyPreset.value = 250;
  historyRangeLabel.value = '最近 250 个交易日';
  historyStartDate.value = '';
  historyEndDate.value = '';

  analysisLoaded.value = false;
  moneyflowLoaded.value = false;
  cyqLoaded.value = false;
  cyqUnauthorized.value = false;
  selectedMoneyflowDate.value = '';
  selectedCyqDate.value = '';
  watchlistOverride.value = null;
  savedAnalysisKey.value = '';
  indicatorType.value = 'macd';
  realtimeFrequency.value = 'daily';
  notice.value = null;
}

function setNotice(tone: NoticeTone, text: string) {
  notice.value = { tone, text };
}

async function fetchStockInfo() {
  stockLoading.value = true;
  stockError.value = '';

  try {
    const response = await http.get<ApiResponse<StockDetail>>(`/stocks/${tsCode.value}`);
    if (response.data.code !== 200 || !response.data.data) {
      throw new Error(response.data.message || '股票信息加载失败');
    }
    stockInfo.value = response.data.data;
  } catch (error) {
    stockError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '股票信息加载失败';
  } finally {
    stockLoading.value = false;
  }
}

async function fetchRealtime() {
  realtimeLoading.value = true;
  realtimeError.value = '';

  try {
    const response = await http.get<ApiResponse<RealtimePayload>>(`/stocks/${tsCode.value}/realtime`, {
      params: { freq: realtimeFrequency.value },
    });

    if (response.data.code !== 200 || !response.data.data) {
      throw new Error(response.data.message || '实时行情加载失败');
    }

    realtimeData.value = response.data.data;
    if (watchlistOverride.value === null) {
      watchlistOverride.value = Boolean(response.data.data.is_watchlist);
    }
  } catch (error) {
    realtimeError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '实时行情加载失败';
  } finally {
    realtimeLoading.value = false;
  }
}

async function fetchHistory(params: { limit?: number; startDate?: string; endDate?: string; label: string }) {
  historyLoading.value = true;
  historyError.value = '';

  try {
    const response = await http.get<ApiResponse<HistoryItem[]>>(`/stocks/${tsCode.value}/history`, {
      params: {
        limit: params.limit,
        start_date: params.startDate,
        end_date: params.endDate,
      },
    });

    if (response.data.code !== 200) {
      throw new Error(response.data.message || '历史数据加载失败');
    }

    historyData.value = response.data.data || [];
    historyDisplayCount.value = 30;
    historyRangeLabel.value = params.label;
  } catch (error) {
    historyData.value = [];
    historyError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '历史数据加载失败';
  } finally {
    historyLoading.value = false;
  }
}

async function loadHistoryPreset(days: number) {
  historyPreset.value = days;
  historyStartDate.value = '';
  historyEndDate.value = '';
  await fetchHistory({ limit: days, label: `最近 ${days} 个交易日` });
}

async function loadHistoryByDate() {
  if (!historyStartDate.value && !historyEndDate.value) {
    setNotice('error', '请至少选择一个日期边界。');
    return;
  }

  historyPreset.value = 'custom';
  await fetchHistory({
    limit: 5000,
    startDate: historyStartDate.value || undefined,
    endDate: historyEndDate.value || undefined,
    label: `${historyStartDate.value || '最早'} ~ ${historyEndDate.value || '今天'}`,
  });
}

async function loadTechAnalysis() {
  if (analysisLoaded.value || analysisLoading.value) {
    return;
  }

  analysisLoading.value = true;
  analysisError.value = '';

  try {
    const [historyResponse, factorsResponse] = await Promise.allSettled([
      http.get<ApiResponse<HistoryItem[]>>(`/stocks/${tsCode.value}/history`, { params: { limit: 750 } }),
      http.get<ApiResponse<FactorItem[]>>(`/stocks/${tsCode.value}/factors`, { params: { limit: 750 } }),
    ]);

    if (historyResponse.status !== 'fulfilled' || historyResponse.value.data.code !== 200) {
      throw new Error('技术分析需要的历史数据暂时不可用');
    }

    analysisHistoryData.value = historyResponse.value.data.data || [];
    if (factorsResponse.status === 'fulfilled' && factorsResponse.value.data.code === 200) {
      analysisFactorsData.value = factorsResponse.value.data.data || [];
    } else {
      analysisFactorsData.value = [];
    }

    analysisLoaded.value = true;
    await autoSaveAnalysisRecord();
  } catch (error) {
    analysisError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '技术分析加载失败';
  } finally {
    analysisLoading.value = false;
  }
}

async function loadMoneyflow() {
  if (moneyflowLoaded.value || moneyflowLoading.value) {
    return;
  }

  moneyflowLoading.value = true;
  moneyflowError.value = '';

  try {
    const response = await http.get<ApiResponse<MoneyflowItem[]>>(`/stocks/${tsCode.value}/moneyflow`, {
      params: { limit: 250 },
    });

    if (response.data.code !== 200) {
      throw new Error(response.data.message || '资金流向数据加载失败');
    }

    moneyflowData.value = response.data.data || [];
    selectedMoneyflowDate.value = moneyflowData.value[0]?.trade_date || '';
    moneyflowLoaded.value = true;
  } catch (error) {
    moneyflowError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '资金流向数据加载失败';
  } finally {
    moneyflowLoading.value = false;
  }
}

async function loadCyq() {
  if (cyqLoaded.value || cyqLoading.value) {
    return;
  }

  cyqLoading.value = true;
  cyqError.value = '';
  cyqUnauthorized.value = false;

  try {
    const [chipsResult, perfResult] = await Promise.allSettled([
      http.get<ApiResponse<CyqChipItem[]>>(`/stocks/${tsCode.value}/cyq_chips`, { params: { limit_days: 5 } }),
      http.get<ApiResponse<CyqPerfItem[]>>(`/stocks/${tsCode.value}/cyq`, { params: { limit: 250 } }),
    ]);

    if (chipsResult.status === 'fulfilled' && chipsResult.value.data.code === 200) {
      cyqChipsData.value = chipsResult.value.data.data || [];
    } else if (
      chipsResult.status === 'rejected' &&
      axios.isAxiosError(chipsResult.reason) &&
      chipsResult.reason.response?.status === 401
    ) {
      cyqUnauthorized.value = true;
      cyqChipsData.value = [];
    }

    if (perfResult.status === 'fulfilled' && perfResult.value.data.code === 200) {
      cyqPerfData.value = perfResult.value.data.data || [];
    } else if (perfResult.status === 'rejected') {
      throw perfResult.reason;
    }

    selectedCyqDate.value =
      [...new Set(cyqChipsData.value.map((item) => item.trade_date).filter(Boolean))]
        .sort()
        .reverse()[0] || '';
    cyqLoaded.value = true;
  } catch (error) {
    cyqError.value = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '筹码分布数据加载失败';
  } finally {
    cyqLoading.value = false;
  }
}

async function autoSaveAnalysisRecord() {
  if (!isAuthenticated.value || !analysisHistoryData.value.length) {
    return;
  }

  const latest = analysisHistoryData.value[0];
  const latestFactor = findFactorByTradeDate(analysisFactorsData.value, latest.trade_date);
  const rsi6 = toNumber(latestFactor?.rsi_6);
  const macd = toNumber(latestFactor?.macd);
  const close = toNumber(latest.close);

  let trendText = '指标中性震荡，等待方向确认。';
  if (rsi6 >= 70) {
    trendText = 'RSI 偏热，注意追高风险。';
  } else if (rsi6 <= 30) {
    trendText = 'RSI 进入超卖区，关注企稳反弹。';
  } else if (macd > 0) {
    trendText = 'MACD 位于零轴上方，趋势动能偏多。';
  } else if (macd < 0) {
    trendText = 'MACD 位于零轴下方，短线仍有整理压力。';
  }

  const summary = `查看 ${stockInfo.value?.name || tsCode.value}(${tsCode.value}) 技术分析 | 收盘价 ${close.toFixed(
    2,
  )} | RSI(6): ${rsi6.toFixed(1)} | MACD: ${macd.toFixed(2)} | 结论: ${trendText}`;
  const saveKey = `${tsCode.value}:${latest.trade_date}:${summary}`;
  if (savedAnalysisKey.value === saveKey) {
    return;
  }

  try {
    await appHttp.post('/auth/profile/records/analysis', {
      module_name: '技术分析',
      summary,
      ts_code: tsCode.value,
      stock_name: stockInfo.value?.name || '',
    });
    savedAnalysisKey.value = saveKey;
  } catch {
    // Keep the page responsive even when the history record cannot be saved.
  }
}

async function addToWatchlist() {
  watchlistLoading.value = true;
  try {
    const response = await http.post<ApiResponse<unknown>>(`/watchlist/${tsCode.value}`);
    watchlistOverride.value = true;
    setNotice('success', response.data.message || '已加入自选。');
  } catch (error) {
    const message = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '加入自选失败';
    setNotice('error', message);
  } finally {
    watchlistLoading.value = false;
  }
}

function openBacktest() {
  window.open(`/backtest?stock=${tsCode.value}`, '_blank', 'noopener');
}

function openLegacyPage() {
  window.open(`/stock/${tsCode.value}`, '_blank', 'noopener');
}

function loadMoreHistory() {
  historyDisplayCount.value = Math.min(historyDisplayCount.value + 30, historyData.value.length);
}

function setRealtimeFrequency(freq: RealtimeFrequency) {
  if (realtimeFrequency.value === freq && !realtimeError.value) {
    return;
  }
  realtimeFrequency.value = freq;
  void fetchRealtime();
}

function setIndicator(type: IndicatorType) {
  indicatorType.value = type;
}

function setActiveTab(tab: StockTab) {
  if (activeTab.value === tab) {
    void ensureTabData(tab);
    return;
  }
  activeTab.value = tab;
}

async function ensureTabData(tab: StockTab) {
  if (tab === 'tech-analysis') {
    await loadTechAnalysis();
  }
  if (tab === 'moneyflow') {
    await loadMoneyflow();
  }
  if (tab === 'cyq') {
    await loadCyq();
  }
}

async function loadPage() {
  resetPageState();
  await Promise.allSettled([fetchStockInfo(), fetchRealtime(), loadHistoryPreset(250)]);
  await ensureTabData(activeTab.value);
}

watch(
  () => route.query.tab,
  (value) => {
    activeTab.value = parseTabQuery(value);
  },
  { immediate: true },
);

watch(activeTab, (tab) => {
  const queryTab = tab === 'history' ? undefined : tab === 'tech-analysis' ? 'analysis' : tab;
  const currentQuery = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab;

  if (queryTab !== currentQuery) {
    const nextQuery = { ...route.query };
    if (queryTab) {
      nextQuery.tab = queryTab;
    } else {
      delete nextQuery.tab;
    }
    void router.replace({ query: nextQuery });
  }

  void ensureTabData(tab);
});

watch(
  tsCode,
  () => {
    void loadPage();
  },
  { immediate: true },
);

watch(
  [stockInfo, quote],
  () => {
    const name = stockInfo.value?.name || quote.value?.name;
    document.title = name ? `${name} (${tsCode.value}) - Vue Stock Detail` : `${tsCode.value} - Vue Stock Detail`;
  },
  { deep: true },
);

const priceToneClass = computed(() => {
  const change = toNumber(quote.value?.change);
  if (change > 0) {
    return 'up';
  }
  if (change < 0) {
    return 'down';
  }
  return 'flat';
});

const priceArrow = computed(() => {
  const change = toNumber(quote.value?.change);
  if (change > 0) {
    return '+';
  }
  if (change < 0) {
    return '-';
  }
  return '=';
});

const stockIdentityMetrics = computed<OverviewMetric[]>(() => {
  const info = stockInfo.value;
  if (!info) {
    return [];
  }

  return [
    { label: '股票代码', value: info.ts_code || '--' },
    { label: '股票简称', value: info.symbol || '--' },
    { label: '所属行业', value: info.industry || '--' },
    { label: '所属地区', value: info.area || '--' },
    { label: '上市日期', value: info.list_date || '--' },
    { label: '市场', value: formatMarketLabel(info.ts_code || '') },
  ];
});

const valuationMetrics = computed<OverviewMetric[]>(() => {
  const db = stockInfo.value?.daily_basic;
  if (!db?.trade_date) {
    return [];
  }

  return [
    { label: 'PE-TTM', value: formatNumber(db.pe_ttm) },
    { label: 'PB', value: formatNumber(db.pb) },
    { label: 'PS-TTM', value: formatNumber(db.ps_ttm) },
    { label: '股息率', value: formatPercent(db.dv_ratio, 2, false) },
    { label: '总市值', value: formatCompactNumber(db.total_mv) },
    { label: '流通市值', value: formatCompactNumber(db.circ_mv) },
    { label: '换手率', value: formatPercent(db.turnover_rate, 2, false) },
    { label: '量比', value: formatNumber(db.volume_ratio) },
  ];
});

const sourceLabel = computed(() => {
  const source = quote.value?.source || realtimeData.value?.quote_source;
  const sourceMap: Record<string, string> = {
    sina_realtime: '新浪实时',
    realtime_quote: 'Tushare 实时',
    latest_trade_day: '最近交易日',
    local_cache: '本地缓存',
  };
  return source ? sourceMap[source] || source : '行情数据';
});

const realtimeSeries = computed<RealtimeSeriesItem[]>(() => realtimeData.value?.series || []);

const realtimeChartOption = computed(() => {
  if (!realtimeSeries.value.length) {
    return null;
  }

  const labels = realtimeSeries.value.map((item) => item.label || '--');
  const prices = realtimeSeries.value.map((item) => toNumber(item.price ?? item.close));
  const volumes = realtimeSeries.value.map((item) => toNumber(item.volume));
  const ohlc = realtimeSeries.value.map((item) => [
    toNumber(item.open),
    toNumber(item.price ?? item.close),
    toNumber(item.low),
    toNumber(item.high),
  ]);

  const ma5 = realtimeFrequency.value === 'daily' ? movingAverage(prices, 5) : [];
  const ma10 = realtimeFrequency.value === 'daily' ? movingAverage(prices, 10) : [];
  const ma20 = realtimeFrequency.value === 'daily' ? movingAverage(prices, 20) : [];
  const legend = ['K线', '成交量'];
  if (realtimeFrequency.value === 'daily') {
    legend.splice(1, 0, 'MA5', 'MA10', 'MA20');
  }

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 12 },
    },
    legend: {
      data: legend,
      top: 0,
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: [
      { left: 52, right: 20, top: 34, height: '58%' },
      { left: 52, right: 20, top: '74%', height: '16%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: labels,
        boundaryGap: true,
        axisLabel: { color: '#64748b', fontSize: 10, hideOverlap: true },
        axisLine: { lineStyle: { color: '#cbd5e1' } },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: labels,
        boundaryGap: true,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: '#cbd5e1' } },
      },
    ],
    yAxis: [
      {
        scale: true,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#eef2f7', type: 'dashed' } },
      },
      {
        scale: true,
        gridIndex: 1,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 6,
        height: 18,
        borderColor: '#d9e2ec',
        fillerColor: 'rgba(24, 119, 242, 0.12)',
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#16a34a',
          borderColor: '#ef4444',
          borderColor0: '#16a34a',
        },
      },
      ...(realtimeFrequency.value === 'daily'
        ? [
            {
              name: 'MA5',
              type: 'line',
              data: ma5,
              smooth: true,
              symbol: 'none',
              lineStyle: { width: 1.4, color: '#f59e0b' },
            },
            {
              name: 'MA10',
              type: 'line',
              data: ma10,
              smooth: true,
              symbol: 'none',
              lineStyle: { width: 1.4, color: '#3b82f6' },
            },
            {
              name: 'MA20',
              type: 'line',
              data: ma20,
              smooth: true,
              symbol: 'none',
              lineStyle: { width: 1.4, color: '#8b5cf6' },
            },
          ]
        : []),
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: 'rgba(59, 130, 246, 0.52)' },
      },
    ],
  } as EChartsOption;
});

const historyRows = computed(() => historyData.value.slice(0, historyDisplayCount.value));
const historyCanLoadMore = computed(() => historyDisplayCount.value < historyData.value.length);

const sortedAnalysisFactors = computed(() => sortByTradeDateAsc(analysisFactorsData.value));
const analysisTableRows = computed(() => {
  const factorMap = new Map(
    analysisFactorsData.value.map((item) => [normalizeTradeDate(item.trade_date), item]),
  );

  return analysisHistoryData.value.slice(0, 20).map((row) => ({
    ...row,
    ...(factorMap.get(normalizeTradeDate(row.trade_date)) || {}),
  }));
});

const analysisSummary = computed<AnalysisSummary | null>(() => {
  if (!analysisHistoryData.value.length) {
    return null;
  }

  const latest = analysisHistoryData.value[0];
  const previous = analysisHistoryData.value[1] || null;
  const latestFactor = findFactorByTradeDate(analysisFactorsData.value, latest.trade_date);
  const latestClose = toNumber(latest.close);
  const priceChange = previous
    ? ((latestClose - toNumber(previous.close)) / Math.max(toNumber(previous.close), 1)) * 100
    : 0;
  const ma5 = average(analysisHistoryData.value.slice(0, 5).map((item) => toNumber(item.close)));
  const ma20 = average(analysisHistoryData.value.slice(0, 20).map((item) => toNumber(item.close)));
  const avgVolume5 = average(analysisHistoryData.value.slice(1, 6).map((item) => toNumber(item.vol)));
  const volumeRatio = avgVolume5 > 0 ? toNumber(latest.vol) / avgVolume5 : 1;
  const rsi6 = toNumber(latestFactor?.rsi_6);
  const macd = toNumber(latestFactor?.macd);
  const kdjK = toNumber(latestFactor?.kdj_k);
  const bollUpper = toNumber(latestFactor?.boll_upper);
  const bollLower = toNumber(latestFactor?.boll_lower);

  let trendTitle = '区间震荡观察';
  let trendChip = `MA5 ${formatNumber(ma5, 2)} / MA20 ${formatNumber(ma20, 2)}`;
  let trendText = '趋势方向尚未拉开，建议结合量能确认突破。';

  if (latestClose >= ma5 && latestClose >= ma20 && priceChange >= 0) {
    trendTitle = '短线趋势偏强';
    trendText = '价格位于短中期均线上方，趋势延续性更强。';
  } else if (latestClose < ma5 && latestClose < ma20 && priceChange < 0) {
    trendTitle = '短线走势承压';
    trendText = '价格位于均线下方，仍需关注止跌信号。';
  }

  let momentumText = `指标中性，KDJ-K ${formatNumber(kdjK, 2)}。`;
  if (macd > 0 && rsi6 >= 55) {
    momentumText = `MACD 与 RSI 共振偏强，KDJ-K ${formatNumber(kdjK, 2)}。`;
  } else if (rsi6 >= 70) {
    momentumText = `RSI(6) ${formatNumber(rsi6, 2)} 偏热，注意高位回撤。`;
  } else if (macd < 0 && rsi6 <= 45) {
    momentumText = `MACD 偏弱且 RSI 回落，KDJ-K ${formatNumber(kdjK, 2)}。`;
  }

  let volatilityText = '暂无布林带数据。';
  if (bollUpper && latestClose >= bollUpper) {
    volatilityText = '触及布林上轨，波动正在放大。';
  } else if (bollLower && latestClose <= bollLower) {
    volatilityText = '接近布林下轨，防守压力较大。';
  } else if (bollUpper && bollLower) {
    volatilityText = `布林区间 ${formatNumber(bollLower, 2)} - ${formatNumber(bollUpper, 2)}。`;
  }

  const monitorItems = [
    `收盘价 ${formatNumber(latestClose, 2)}，日内涨跌 ${formatPercent(priceChange)}`,
    `量能比过去 5 日均量 ${volumeRatio.toFixed(2)} 倍`,
    `RSI(6) ${formatNumber(rsi6, 2)} / MACD ${formatNumber(macd, 4)}`,
    trendChip,
  ];

  return {
    trendTitle,
    trendChip,
    trendText,
    momentumText,
    volatilityText,
    monitorItems,
  };
});

const indicatorChartOption = computed(() => {
  if (!sortedAnalysisFactors.value.length) {
    return null;
  }

  const labels = sortedAnalysisFactors.value.map((item) => item.trade_date || '--');
  const closeSeries = sortedAnalysisFactors.value.map((item) => toNumber(item.close));

  if (indicatorType.value === 'macd') {
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['MACD', 'DIF', 'DEA'] },
      grid: { left: 36, right: 18, top: 40, bottom: 26 },
      xAxis: { type: 'category', data: labels, axisLabel: { show: false } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [
        {
          name: 'MACD',
          type: 'bar',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.macd)),
          itemStyle: {
            color: (params: { data?: unknown }) => (toNumber(params.data) >= 0 ? '#ef4444' : '#16a34a'),
          },
        },
        {
          name: 'DIF',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.macd_dif)),
          lineStyle: { color: '#2563eb', width: 1.6 },
        },
        {
          name: 'DEA',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.macd_dea)),
          lineStyle: { color: '#f59e0b', width: 1.6 },
        },
      ],
    } as EChartsOption;
  }

  if (indicatorType.value === 'kdj') {
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['K', 'D', 'J'] },
      grid: { left: 36, right: 18, top: 40, bottom: 26 },
      xAxis: { type: 'category', data: labels, axisLabel: { show: false } },
      yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [
        {
          name: 'K',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.kdj_k)),
          lineStyle: { color: '#2563eb', width: 1.6 },
        },
        {
          name: 'D',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.kdj_d)),
          lineStyle: { color: '#16a34a', width: 1.6 },
        },
        {
          name: 'J',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.kdj_j)),
          lineStyle: { color: '#ef4444', width: 1.6 },
        },
      ],
    } as EChartsOption;
  }

  if (indicatorType.value === 'rsi') {
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['RSI6', 'RSI12', 'RSI24'] },
      grid: { left: 36, right: 18, top: 40, bottom: 26 },
      xAxis: { type: 'category', data: labels, axisLabel: { show: false } },
      yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [
        {
          name: 'RSI6',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.rsi_6)),
          lineStyle: { color: '#ef4444', width: 1.6 },
        },
        {
          name: 'RSI12',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.rsi_12)),
          lineStyle: { color: '#2563eb', width: 1.6 },
        },
        {
          name: 'RSI24',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: sortedAnalysisFactors.value.map((item) => toNumber(item.rsi_24)),
          lineStyle: { color: '#9333ea', width: 1.6 },
        },
      ],
    } as EChartsOption;
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['收盘价', '上轨', '中轨', '下轨'] },
    grid: { left: 36, right: 18, top: 40, bottom: 26 },
    xAxis: { type: 'category', data: labels, axisLabel: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series: [
      {
        name: '收盘价',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: closeSeries,
        lineStyle: { color: '#111827', width: 1.6 },
      },
      {
        name: '上轨',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: sortedAnalysisFactors.value.map((item) => toNumber(item.boll_upper)),
        lineStyle: { color: '#ef4444', width: 1.4 },
      },
      {
        name: '中轨',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: sortedAnalysisFactors.value.map((item) => toNumber(item.boll_mid)),
        lineStyle: { color: '#2563eb', width: 1.4 },
      },
      {
        name: '下轨',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: sortedAnalysisFactors.value.map((item) => toNumber(item.boll_lower)),
        lineStyle: { color: '#16a34a', width: 1.4 },
      },
    ],
  } as EChartsOption;
});

const moneyflowDates = computed(() => moneyflowData.value.map((item) => item.trade_date || '').filter(Boolean));
const selectedMoneyflowEntry = computed(() => {
  return (
    moneyflowData.value.find((item) => item.trade_date === selectedMoneyflowDate.value) ||
    moneyflowData.value[0] ||
    null
  );
});

const moneyflowChartOption = computed(() => {
  const target = selectedMoneyflowEntry.value;
  if (!target) {
    return null;
  }

  return {
    title: { text: '分单资金买卖对比', subtext: target.trade_date || '--', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['买入', '卖出'], top: 28 },
    grid: { left: '4%', right: '4%', bottom: '6%', containLabel: true },
    xAxis: { type: 'category', data: ['特大单', '大单', '中单', '小单'] },
    yAxis: { type: 'value' },
    series: [
      {
        name: '买入',
        type: 'bar',
        data: [
          toNumber(target.buy_elg_amount),
          toNumber(target.buy_lg_amount),
          toNumber(target.buy_md_amount),
          toNumber(target.buy_sm_amount),
        ],
        itemStyle: { color: '#ef4444' },
      },
      {
        name: '卖出',
        type: 'bar',
        data: [
          -toNumber(target.sell_elg_amount),
          -toNumber(target.sell_lg_amount),
          -toNumber(target.sell_md_amount),
          -toNumber(target.sell_sm_amount),
        ],
        itemStyle: { color: '#16a34a' },
      },
    ],
  } as EChartsOption;
});

const netflowChartOption = computed(() => {
  if (!moneyflowData.value.length) {
    return null;
  }

  const ordered = [...moneyflowData.value].reverse();
  return {
    title: { text: '净流入趋势', left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true },
    xAxis: { type: 'category', data: ordered.map((item) => item.trade_date || '--'), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', bottom: 6, height: 18, borderColor: '#d9e2ec', fillerColor: 'rgba(24, 119, 242, 0.12)' },
    ],
    series: [
      {
        name: '净流入',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: ordered.map((item) => toNumber(item.net_mf_amount)),
        lineStyle: { color: '#2563eb', width: 1.6 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(37, 99, 235, 0.25)' },
              { offset: 1, color: 'rgba(37, 99, 235, 0.04)' },
            ],
          },
        },
      },
    ],
  } as EChartsOption;
});

const moneyflowIndicators = computed(() => {
  const entry = selectedMoneyflowEntry.value;
  if (!entry) {
    return [];
  }

  const totalBuy =
    toNumber(entry.buy_elg_amount) +
    toNumber(entry.buy_lg_amount) +
    toNumber(entry.buy_md_amount) +
    toNumber(entry.buy_sm_amount);
  const mainBuy = toNumber(entry.buy_elg_amount) + toNumber(entry.buy_lg_amount);
  const mainSell = toNumber(entry.sell_elg_amount) + toNumber(entry.sell_lg_amount);
  const mainNetFlow = mainBuy - mainSell;
  const lgBuyRate = totalBuy > 0 ? (toNumber(entry.buy_lg_amount) / totalBuy) * 100 : 0;
  const elgBuyRate = totalBuy > 0 ? (toNumber(entry.buy_elg_amount) / totalBuy) * 100 : 0;

  return [
    { label: '净流入额', value: `${formatNumber(entry.net_mf_amount, 0)} 万` },
    { label: '大单买入占比', value: `${formatNumber(lgBuyRate, 1)}%` },
    { label: '特大单买入占比', value: `${formatNumber(elgBuyRate, 1)}%` },
    { label: '主力净流入', value: `${formatNumber(mainNetFlow, 0)} 万` },
  ];
});

const moneyflowTableRows = computed(() => moneyflowData.value.slice(0, 30));

const cyqTradeDates = computed(() => {
  return [...new Set(cyqChipsData.value.map((item) => item.trade_date || '').filter(Boolean))]
    .sort()
    .reverse();
});

const selectedCyqDayData = computed(() => {
  const targetDate = selectedCyqDate.value || cyqTradeDates.value[0];
  return [...cyqChipsData.value]
    .filter((item) => item.trade_date === targetDate)
    .sort((left, right) => toNumber(left.price) - toNumber(right.price));
});

const cyqIndicators = computed(() => {
  const dayData = selectedCyqDayData.value;
  if (!dayData.length) {
    return [];
  }

  const totalPercent = dayData.reduce((sum, item) => sum + toNumber(item.percent), 0);
  const sorted = [...dayData].sort((left, right) => toNumber(right.percent) - toNumber(left.percent));
  const concentratedPrices: number[] = [];
  let cumulativePercent = 0;

  for (const item of sorted) {
    cumulativePercent += toNumber(item.percent);
    concentratedPrices.push(toNumber(item.price));
    if (cumulativePercent >= 90) {
      break;
    }
  }

  const concentrationLow = Math.min(...concentratedPrices);
  const concentrationHigh = Math.max(...concentratedPrices);
  const concentration =
    concentrationHigh > concentrationLow
      ? ((concentrationHigh - concentrationLow) / ((concentrationHigh + concentrationLow) / 2)) * 100
      : 0;
  const avgCost =
    totalPercent > 0
      ? dayData.reduce((sum, item) => sum + toNumber(item.price) * toNumber(item.percent), 0) / totalPercent
      : 0;
  const profitRate =
    currentPrice.value > 0
      ? dayData
          .filter((item) => toNumber(item.price) <= currentPrice.value)
          .reduce((sum, item) => sum + toNumber(item.percent), 0)
      : 0;

  return [
    { label: '平均成本', value: formatNumber(avgCost, 2) },
    { label: '获利比例', value: `${formatNumber(profitRate, 2)}%` },
    { label: '筹码集中度', value: `${formatNumber(concentration, 1)}%` },
    { label: '90% 筹码区间', value: `${formatNumber(concentrationLow, 2)} ~ ${formatNumber(concentrationHigh, 2)}` },
  ];
});

const cyqChipsChartOption = computed(() => {
  if (!selectedCyqDayData.value.length) {
    return null;
  }

  const prices = selectedCyqDayData.value.map((item) => formatNumber(item.price, 2));
  const percents = selectedCyqDayData.value.map((item) => toNumber(item.percent));
  const targetDate = selectedCyqDate.value || cyqTradeDates.value[0] || '--';

  return {
    title: { text: `筹码分布 (${targetDate})`, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '12%', right: '8%', top: 40, bottom: 30 },
    xAxis: {
      type: 'value',
      name: '占比 (%)',
      axisLabel: { formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#eef2f7', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: prices,
      axisLabel: { fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: percents.map((value, index) => {
          const price = toNumber(selectedCyqDayData.value[index].price);
          const isNearCurrent =
            currentPrice.value > 0 && Math.abs(price - currentPrice.value) / currentPrice.value < 0.005;

          return {
            value,
            itemStyle: {
              color: isNearCurrent
                ? '#ef4444'
                : price <= currentPrice.value
                  ? 'rgba(22, 163, 74, 0.72)'
                  : 'rgba(148, 163, 184, 0.56)',
            },
          };
        }),
        barWidth: '70%',
        label: {
          show: true,
          position: 'right',
          formatter: (params: { value?: unknown }) =>
            toNumber(params.value) >= 0.5 ? `${formatNumber(params.value, 1)}%` : '',
          fontSize: 9,
          color: '#64748b',
        },
      },
    ],
  } as EChartsOption;
});

const cyqCostChartOption = computed(() => {
  if (!cyqPerfData.value.length) {
    return null;
  }

  const ordered = [...cyqPerfData.value].reverse();
  const dates = ordered.map((item) => item.trade_date || '--');

  return {
    title: { text: '成本分位曲线', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['5%', '15%', '50%', '85%', '95%', '加权平均'], top: 30 },
    grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', bottom: 6, height: 18, borderColor: '#d9e2ec', fillerColor: 'rgba(24, 119, 242, 0.12)' },
    ],
    series: [
      { name: '5%', type: 'line', smooth: true, symbol: 'none', data: ordered.map((item) => toNumber(item.cost_5pct)) },
      { name: '15%', type: 'line', smooth: true, symbol: 'none', data: ordered.map((item) => toNumber(item.cost_15pct)) },
      { name: '50%', type: 'line', smooth: true, symbol: 'none', data: ordered.map((item) => toNumber(item.cost_50pct)), lineStyle: { width: 3 } },
      { name: '85%', type: 'line', smooth: true, symbol: 'none', data: ordered.map((item) => toNumber(item.cost_85pct)) },
      { name: '95%', type: 'line', smooth: true, symbol: 'none', data: ordered.map((item) => toNumber(item.cost_95pct)) },
      {
        name: '加权平均',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: ordered.map((item) => toNumber(item.weight_avg)),
        lineStyle: { type: 'dashed', width: 2 },
      },
    ],
  } as EChartsOption;
});

const cyqWinnerChartOption = computed(() => {
  if (!cyqPerfData.value.length) {
    return null;
  }

  const ordered = [...cyqPerfData.value].reverse();
  return {
    title: { text: '胜率变化', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: '4%', right: '4%', bottom: '16%', containLabel: true },
    xAxis: { type: 'category', data: ordered.map((item) => item.trade_date || '--'), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', bottom: 6, height: 18, borderColor: '#d9e2ec', fillerColor: 'rgba(24, 119, 242, 0.12)' },
    ],
    series: [
      {
        name: '胜率',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: ordered.map((item) => toNumber(item.winner_rate)),
        lineStyle: { color: '#16a34a', width: 1.8 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(22, 163, 74, 0.24)' },
              { offset: 1, color: 'rgba(22, 163, 74, 0.04)' },
            ],
          },
        },
        markLine: {
          data: [{ yAxis: 50 }],
          lineStyle: { color: '#ef4444', type: 'dashed' },
        },
      },
    ],
  } as EChartsOption;
});

const cyqPerfRows = computed(() => cyqPerfData.value.slice(0, 30));
</script>

<template>
  <section class="stock-page stack">
    <div v-if="notice" class="notice-banner" :class="`notice-${notice.tone}`">
      {{ notice.text }}
    </div>

    <div class="hero-grid">
      <article class="panel-card stack">
        <div class="section-header">
          <div>
            <p class="eyebrow">Stock Detail</p>
            <h3>
              {{ stockInfo?.name || quote?.name || tsCode }}
              <span class="muted code-inline">({{ stockInfo?.symbol || tsCode }})</span>
            </h3>
          </div>
          <span class="market-badge" :class="`market-${formatMarketTone(tsCode)}`">
            {{ formatMarketLabel(tsCode) }}
          </span>
        </div>

        <div v-if="stockLoading" class="state-card">正在加载股票基础信息...</div>
        <div v-else-if="stockError" class="state-card state-error">{{ stockError }}</div>
        <template v-else>
          <div class="facts-grid">
            <div v-for="item in stockIdentityMetrics" :key="item.label" class="fact-card">
              <span class="fact-label">{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>

          <div v-if="valuationMetrics.length" class="stack">
            <div class="section-subtitle">
              估值与交易指标
              <span class="muted">
                {{ stockInfo?.daily_basic?.trade_date || '--' }}
              </span>
            </div>
            <div class="facts-grid">
              <div v-for="item in valuationMetrics" :key="item.label" class="fact-card soft-card">
                <span class="fact-label">{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </div>
        </template>
      </article>

      <aside class="panel-card stack action-panel">
        <div>
          <p class="eyebrow">Quick Actions</p>
          <h3>保留旧页，同时推进 Vue</h3>
          <p class="muted">这块保留了旧页的快捷能力，也加了一个入口方便你随时对照 legacy 页面。</p>
        </div>

        <button class="action-button primary" :disabled="watchlistLoading" @click="addToWatchlist">
          {{ watchlistLoading ? '正在提交...' : isWatchlist ? '已在自选中' : '加入自选' }}
        </button>
        <button class="action-button" @click="openBacktest">打开回测</button>
        <button class="action-button ghost" @click="openLegacyPage">对照旧版页面</button>
      </aside>
    </div>

    <article class="panel-card stack">
      <div class="section-header">
        <div>
          <p class="eyebrow">Realtime Quote</p>
          <h3>实时行情</h3>
        </div>
        <div class="header-actions">
          <div class="pill-group">
            <button
              v-for="item in frequencyItems"
              :key="item.id"
              class="pill-button"
              :class="{ active: realtimeFrequency === item.id }"
              @click="setRealtimeFrequency(item.id)"
            >
              {{ item.label }}
            </button>
          </div>
          <button class="action-button compact" @click="fetchRealtime">刷新</button>
          <span class="status-pill">{{ sourceLabel }}</span>
        </div>
      </div>

      <div v-if="realtimeLoading" class="state-card">正在加载实时行情...</div>
      <div v-else-if="realtimeError" class="state-card state-error">{{ realtimeError }}</div>
      <template v-else-if="quote">
        <div class="quote-grid">
          <div class="price-panel">
            <div class="price-line" :class="priceToneClass">
              {{ formatNumber(quote.price, 2) }}
            </div>
            <div class="price-change" :class="priceToneClass">
              <span>{{ priceArrow }} {{ formatNumber(quote.change, 2) }}</span>
              <span>{{ formatPercent(quote.pct_chg) }}</span>
            </div>
            <p class="muted meta-line">
              {{ quote.trade_date || '--' }} {{ quote.trade_time || '' }}
            </p>
            <p v-if="realtimeData?.quote_message" class="muted meta-line">
              {{ realtimeData.quote_message }}
            </p>
          </div>

          <div class="facts-grid realtime-facts">
            <div class="fact-card soft-card">
              <span class="fact-label">今开</span>
              <strong>{{ formatNumber(quote.open, 2) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">昨收</span>
              <strong>{{ formatNumber(quote.pre_close, 2) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">最高</span>
              <strong class="up">{{ formatNumber(quote.high, 2) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">最低</span>
              <strong class="down">{{ formatNumber(quote.low, 2) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">成交量</span>
              <strong>{{ formatCompactNumber(quote.volume) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">成交额</span>
              <strong>{{ formatCompactNumber(quote.amount) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">振幅</span>
              <strong>{{ formatPercent(quote.amplitude, 2, false) }}</strong>
            </div>
            <div class="fact-card soft-card">
              <span class="fact-label">换手率</span>
              <strong>{{ formatPercent(quote.turnover_rate, 2, false) }}</strong>
            </div>
          </div>
        </div>

        <BaseEChart v-if="realtimeChartOption" :option="realtimeChartOption" height="420px" />
      </template>
    </article>

    <section class="stack">
      <div class="tab-row">
        <button
          v-for="item in tabItems"
          :key="item.id"
          class="tab-button"
          :class="{ active: activeTab === item.id }"
          @click="setActiveTab(item.id)"
        >
          {{ item.label }}
        </button>
      </div>

      <article v-if="activeTab === 'history'" class="panel-card stack">
        <div class="section-header">
          <div>
            <p class="eyebrow">History</p>
            <h3>历史价格数据</h3>
          </div>
          <div class="header-actions history-actions">
            <div class="pill-group">
              <button
                v-for="days in [60, 120, 250, 750]"
                :key="days"
                class="pill-button"
                :class="{ active: historyPreset === days }"
                @click="loadHistoryPreset(days)"
              >
                {{ days === 750 ? '3年' : `${days}天` }}
              </button>
            </div>
            <div class="date-filter-row">
              <input v-model="historyStartDate" type="date" class="date-input" />
              <span class="muted">至</span>
              <input v-model="historyEndDate" type="date" class="date-input" />
              <button class="action-button compact" @click="loadHistoryByDate">查询</button>
            </div>
          </div>
        </div>

        <div v-if="historyLoading" class="state-card">正在加载历史数据...</div>
        <div v-else-if="historyError" class="state-card state-error">{{ historyError }}</div>
        <template v-else-if="historyRows.length">
          <div class="table-caption">
            <span>{{ historyRangeLabel }}</span>
            <span>显示 1 - {{ historyRows.length }} / {{ historyData.length }}</span>
          </div>
          <div class="table-shell">
            <table class="data-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>开盘</th>
                  <th>最高</th>
                  <th>最低</th>
                  <th>收盘</th>
                  <th>成交量(万手)</th>
                  <th>成交额(万元)</th>
                  <th>涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in historyRows" :key="item.trade_date || `${tsCode}-history-row`">
                  <td><strong>{{ item.trade_date || '--' }}</strong></td>
                  <td>{{ formatNumber(item.open, 2) }}</td>
                  <td class="up">{{ formatNumber(item.high, 2) }}</td>
                  <td class="down">{{ formatNumber(item.low, 2) }}</td>
                  <td><strong>{{ formatNumber(item.close, 2) }}</strong></td>
                  <td>{{ formatNumber(toNumber(item.vol) / 10000, 1) }}</td>
                  <td>{{ formatNumber(toNumber(item.amount) / 10000, 0) }}</td>
                  <td :class="toNumber(item.pct_chg) >= 0 ? 'up' : 'down'">
                    {{ formatPercent(item.pct_chg) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="historyCanLoadMore" class="action-button compact self-center" @click="loadMoreHistory">
            加载更多 ({{ historyRows.length }}/{{ historyData.length }})
          </button>
        </template>
        <div v-else class="state-card">暂无历史数据。</div>
      </article>

      <article v-else-if="activeTab === 'tech-analysis'" class="stack">
        <div v-if="analysisLoading" class="panel-card state-card">正在加载技术分析...</div>
        <div v-else-if="analysisError" class="panel-card state-card state-error">{{ analysisError }}</div>
        <template v-else-if="analysisHistoryData.length">
          <div class="analysis-grid">
            <article class="panel-card stack">
              <div class="section-header">
                <div>
                  <p class="eyebrow">Realtime Analysis</p>
                  <h3>{{ analysisSummary?.trendTitle || '实时分析' }}</h3>
                </div>
                <span class="status-pill">最新分析</span>
              </div>
              <p class="muted emphasis">{{ analysisSummary?.trendChip }}</p>
              <p>{{ analysisSummary?.trendText }}</p>
              <p>{{ analysisSummary?.momentumText }}</p>
              <p>{{ analysisSummary?.volatilityText }}</p>
            </article>

            <article class="panel-card stack">
              <div class="section-header">
                <div>
                  <p class="eyebrow">Realtime Monitor</p>
                  <h3>监控信号</h3>
                </div>
                <span class="status-pill">观察中</span>
              </div>
              <ul class="signal-list">
                <li v-for="item in analysisSummary?.monitorItems || []" :key="item">
                  {{ item }}
                </li>
              </ul>
            </article>
          </div>

          <article class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Indicators</p>
                <h3>技术指标图表</h3>
              </div>
              <div class="pill-group">
                <button
                  v-for="item in indicatorItems"
                  :key="item.id"
                  class="pill-button"
                  :class="{ active: indicatorType === item.id }"
                  @click="setIndicator(item.id)"
                >
                  {{ item.label }}
                </button>
              </div>
            </div>

            <div v-if="!analysisFactorsData.length" class="state-card">
              技术指标接口当前不可用，已保留历史数据分析能力。
            </div>
            <BaseEChart v-else-if="indicatorChartOption" :option="indicatorChartOption" height="380px" />
          </article>

          <article class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Data Table</p>
                <h3>技术分析明细</h3>
              </div>
            </div>
            <div class="table-shell">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>开盘</th>
                    <th>收盘</th>
                    <th>涨跌幅</th>
                    <th>RSI(6)</th>
                    <th>MACD</th>
                    <th>KDJ-K</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="item in analysisTableRows"
                    :key="item.trade_date || `${tsCode}-analysis-row`"
                  >
                    <td><strong>{{ item.trade_date || '--' }}</strong></td>
                    <td>{{ formatNumber(item.open, 2) }}</td>
                    <td><strong>{{ formatNumber(item.close, 2) }}</strong></td>
                    <td :class="toNumber(item.pct_chg) >= 0 ? 'up' : 'down'">
                      {{ formatPercent(item.pct_chg) }}
                    </td>
                    <td :class="toNumber(item.rsi_6) > 70 ? 'up' : toNumber(item.rsi_6) < 30 ? 'down' : ''">
                      {{ formatNumber(item.rsi_6, 2) }}
                    </td>
                    <td :class="toNumber(item.macd) >= 0 ? 'up' : 'down'">
                      {{ formatNumber(item.macd, 4) }}
                    </td>
                    <td>{{ formatNumber(item.kdj_k, 2) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </template>
        <div v-else class="panel-card state-card">暂无技术分析数据。</div>
      </article>

      <article v-else-if="activeTab === 'moneyflow'" class="stack">
        <div v-if="moneyflowLoading" class="panel-card state-card">正在加载资金流向...</div>
        <div v-else-if="moneyflowError" class="panel-card state-card state-error">{{ moneyflowError }}</div>
        <template v-else-if="moneyflowData.length">
          <article class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Money Flow</p>
                <h3>资金流向总览</h3>
              </div>
              <select v-model="selectedMoneyflowDate" class="select-input">
                <option v-for="date in moneyflowDates.slice(0, 60)" :key="date" :value="date">
                  {{ date }}
                </option>
              </select>
            </div>

            <div class="facts-grid">
              <div v-for="item in moneyflowIndicators" :key="item.label" class="fact-card soft-card">
                <span class="fact-label">{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </article>

          <div class="analysis-grid">
            <article class="panel-card">
              <BaseEChart v-if="moneyflowChartOption" :option="moneyflowChartOption" height="400px" />
            </article>
            <article class="panel-card">
              <BaseEChart v-if="netflowChartOption" :option="netflowChartOption" height="400px" />
            </article>
          </div>

          <article class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Money Flow Table</p>
                <h3>最近 30 条资金流向记录</h3>
              </div>
            </div>
            <div class="table-shell">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>净流入额</th>
                    <th>特大单买入</th>
                    <th>特大单卖出</th>
                    <th>大单买入</th>
                    <th>大单卖出</th>
                    <th>中单买入</th>
                    <th>中单卖出</th>
                    <th>小单买入</th>
                    <th>小单卖出</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="item in moneyflowTableRows"
                    :key="item.trade_date || `${tsCode}-moneyflow-row`"
                  >
                    <td>{{ item.trade_date || '--' }}</td>
                    <td :class="toNumber(item.net_mf_amount) >= 0 ? 'up' : 'down'">
                      {{ formatNumber(item.net_mf_amount, 0) }}
                    </td>
                    <td class="up">{{ formatNumber(item.buy_elg_amount, 0) }}</td>
                    <td class="down">{{ formatNumber(item.sell_elg_amount, 0) }}</td>
                    <td class="up">{{ formatNumber(item.buy_lg_amount, 0) }}</td>
                    <td class="down">{{ formatNumber(item.sell_lg_amount, 0) }}</td>
                    <td class="up">{{ formatNumber(item.buy_md_amount, 0) }}</td>
                    <td class="down">{{ formatNumber(item.sell_md_amount, 0) }}</td>
                    <td class="up">{{ formatNumber(item.buy_sm_amount, 0) }}</td>
                    <td class="down">{{ formatNumber(item.sell_sm_amount, 0) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </template>
        <div v-else class="panel-card state-card">暂无资金流向数据。</div>
      </article>

      <article v-else-if="activeTab === 'cyq'" class="stack">
        <div v-if="cyqLoading" class="panel-card state-card">正在加载筹码分布...</div>
        <div v-else-if="cyqError" class="panel-card state-card state-error">{{ cyqError }}</div>
        <template v-else-if="cyqPerfData.length || cyqChipsData.length">
          <article class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Chip Distribution</p>
                <h3>筹码分布概览</h3>
              </div>
              <select v-if="cyqTradeDates.length" v-model="selectedCyqDate" class="select-input">
                <option v-for="date in cyqTradeDates" :key="date" :value="date">
                  {{ date }}
                </option>
              </select>
            </div>

            <div v-if="cyqUnauthorized" class="state-card">
              当前登录态没有拿到筹码明细接口，仍然保留了筹码胜率与成本分位图。
            </div>

            <div class="analysis-grid">
              <article class="panel-card nested-panel">
                <BaseEChart v-if="cyqChipsChartOption" :option="cyqChipsChartOption" height="500px" />
                <div v-else class="state-card compact-state">暂无筹码明细。</div>
              </article>
              <article class="panel-card nested-panel stack">
                <div class="facts-grid single-column">
                  <div v-for="item in cyqIndicators" :key="item.label" class="fact-card soft-card">
                    <span class="fact-label">{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
                <BaseEChart v-if="cyqWinnerChartOption" :option="cyqWinnerChartOption" height="280px" />
              </article>
            </div>
          </article>

          <article v-if="cyqCostChartOption" class="panel-card">
            <BaseEChart :option="cyqCostChartOption" height="350px" />
          </article>

          <article v-if="cyqPerfRows.length" class="panel-card stack">
            <div class="section-header">
              <div>
                <p class="eyebrow">Chip Table</p>
                <h3>筹码胜率明细</h3>
              </div>
            </div>
            <div class="table-shell">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>历史最低</th>
                    <th>历史最高</th>
                    <th>5%</th>
                    <th>15%</th>
                    <th>50%</th>
                    <th>85%</th>
                    <th>95%</th>
                    <th>加权平均</th>
                    <th>胜率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in cyqPerfRows" :key="item.trade_date || `${tsCode}-cyq-row`">
                    <td>{{ item.trade_date || '--' }}</td>
                    <td class="down">{{ formatNumber(item.his_low, 2) }}</td>
                    <td class="up">{{ formatNumber(item.his_high, 2) }}</td>
                    <td>{{ formatNumber(item.cost_5pct, 2) }}</td>
                    <td>{{ formatNumber(item.cost_15pct, 2) }}</td>
                    <td><strong>{{ formatNumber(item.cost_50pct, 2) }}</strong></td>
                    <td>{{ formatNumber(item.cost_85pct, 2) }}</td>
                    <td>{{ formatNumber(item.cost_95pct, 2) }}</td>
                    <td><strong>{{ formatNumber(item.weight_avg, 2) }}</strong></td>
                    <td :class="toNumber(item.winner_rate) >= 50 ? 'up' : 'down'">
                      {{ formatPercent(item.winner_rate, 2, false) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </template>
        <div v-else class="panel-card state-card">暂无筹码分布数据。</div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.stock-page {
  gap: 1rem;
}

.hero-grid,
.analysis-grid,
.quote-grid {
  display: grid;
  gap: 1rem;
}

.hero-grid {
  grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.9fr);
}

.analysis-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.quote-grid {
  grid-template-columns: minmax(240px, 0.8fr) minmax(0, 1.2fr);
  align-items: start;
}

.section-header,
.header-actions,
.pill-group,
.date-filter-row,
.table-caption,
.tab-row {
  display: flex;
  gap: 0.75rem;
}

.section-header,
.table-caption {
  justify-content: space-between;
  align-items: flex-start;
}

.header-actions {
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.history-actions {
  max-width: 100%;
}

.tab-row {
  flex-wrap: wrap;
}

.tab-button,
.pill-button,
.action-button,
.date-input,
.select-input {
  border: 1px solid rgba(20, 32, 43, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #14202b;
  transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;
}

.tab-button,
.pill-button,
.action-button {
  cursor: pointer;
}

.tab-button,
.pill-button {
  padding: 0.65rem 1rem;
  font-size: 0.92rem;
}

.tab-button.active,
.pill-button.active,
.action-button.primary {
  background: #18624c;
  border-color: #18624c;
  color: #fff;
}

.action-button {
  padding: 0.85rem 1rem;
  font-weight: 600;
}

.action-button.compact {
  padding: 0.55rem 0.9rem;
}

.action-button.ghost {
  background: rgba(20, 32, 43, 0.04);
}

.tab-button:hover,
.pill-button:hover,
.action-button:hover {
  transform: translateY(-1px);
}

.facts-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.realtime-facts {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.single-column {
  grid-template-columns: 1fr;
}

.fact-card,
.state-card,
.price-panel,
.nested-panel {
  border-radius: 20px;
  border: 1px solid rgba(20, 32, 43, 0.08);
  background: rgba(248, 250, 252, 0.82);
}

.fact-card,
.price-panel,
.state-card {
  padding: 1rem;
}

.nested-panel {
  padding: 1rem;
  background: rgba(255, 255, 255, 0.7);
}

.fact-label,
.meta-line,
.section-subtitle {
  display: block;
  color: #64748b;
  font-size: 0.88rem;
}

.price-panel {
  min-height: 100%;
}

.price-line {
  font-size: clamp(2rem, 3vw, 3rem);
  line-height: 1.05;
  font-weight: 800;
}

.price-change {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.75rem;
  font-size: 1rem;
  font-weight: 700;
}

.up {
  color: #dc2626;
}

.down {
  color: #15803d;
}

.flat {
  color: #64748b;
}

.market-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
}

.market-danger {
  background: rgba(220, 38, 38, 0.12);
  color: #b91c1c;
}

.market-success {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
}

.market-warning {
  background: rgba(245, 158, 11, 0.18);
  color: #92400e;
}

.table-shell {
  overflow: auto;
  border-radius: 18px;
  border: 1px solid rgba(20, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.76);
}

.data-table {
  width: 100%;
  min-width: 820px;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 0.8rem 0.95rem;
  border-bottom: 1px solid rgba(20, 32, 43, 0.07);
  text-align: left;
  white-space: nowrap;
}

.data-table thead th {
  position: sticky;
  top: 0;
  background: rgba(248, 250, 252, 0.96);
  color: #475569;
  font-size: 0.84rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.notice-banner {
  padding: 0.9rem 1rem;
  border-radius: 18px;
  font-weight: 600;
}

.notice-success {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
}

.notice-error {
  background: rgba(220, 38, 38, 0.12);
  color: #991b1b;
}

.notice-info {
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.state-card {
  color: #475569;
}

.state-error {
  background: rgba(254, 242, 242, 0.92);
  color: #991b1b;
}

.compact-state {
  min-height: 160px;
  display: grid;
  place-items: center;
}

.signal-list {
  margin: 0;
  padding-left: 1.1rem;
  display: grid;
  gap: 0.6rem;
}

.code-inline {
  font-size: 0.88em;
}

.emphasis {
  font-weight: 700;
}

.action-panel {
  justify-content: space-between;
}

.date-input,
.select-input {
  padding: 0.7rem 0.9rem;
}

.select-input {
  min-width: 150px;
}

.self-center {
  align-self: center;
}

@media (max-width: 1100px) {
  .hero-grid,
  .analysis-grid,
  .quote-grid {
    grid-template-columns: 1fr;
  }

  .realtime-facts,
  .facts-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .facts-grid,
  .realtime-facts {
    grid-template-columns: 1fr;
  }

  .section-header,
  .header-actions,
  .table-caption,
  .date-filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .tab-row,
  .pill-group {
    flex-wrap: wrap;
  }

  .select-input,
  .date-input,
  .action-button.compact {
    width: 100%;
  }
}
</style>
