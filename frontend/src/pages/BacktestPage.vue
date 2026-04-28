<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import BaseEChart from '../components/BaseEChart.vue';
import { useToast } from '../composables/useToast';
import { formatNumber, formatPercent, debounce } from '../lib/format';
import { searchStocks, runBacktest, getBacktestHistory, deleteBacktest, type BacktestResult, type BacktestRecord } from '../modules/backtest/api';
import type { EChartsOption } from 'echarts';

interface StockSearchItem { ts_code: string; symbol: string; name: string }

const toast = useToast();

const stockQuery = ref('');
const stockResults = ref<StockSearchItem[]>([]);
const selectedStock = ref<StockSearchItem | null>(null);
const showDropdown = ref(false);

const strategy = ref('ma_cross');
const startDate = ref('');
const endDate = ref('');
const initialCapital = ref(100000);
const commission = ref(0.03);

const maShort = ref(5); const maLong = ref(20);
const macdFast = ref(12); const macdSlow = ref(26); const macdSignal = ref(9);
const kdjPeriod = ref(9); const kdjOverbought = ref(80); const kdjOversold = ref(20);
const rsiPeriod = ref(14); const rsiOverbought = ref(70); const rsiOversold = ref(30);
const bollPeriod = ref(20); const bollStd = ref(2);

const result = ref<BacktestResult | null>(null);
const loading = ref(false);
const error = ref('');
const history = ref<BacktestRecord[]>([]);
const historyLoading = ref(false);

const strategyOptions = [
  { value: 'ma_cross', label: '均线交叉' },
  { value: 'macd', label: 'MACD' },
  { value: 'kdj', label: 'KDJ' },
  { value: 'rsi', label: 'RSI' },
  { value: 'bollinger', label: '布林带' },
];

const formValid = computed(() => {
  return selectedStock.value && strategy.value && startDate.value && endDate.value;
});

const equityOption = computed<EChartsOption>(() => {
  if (!result.value?.trades?.length) return {};
  const trades = result.value.trades;
  const dates = trades.map((t) => t.trade_date || '');
  const values: number[] = [];
  let cap = initialCapital.value;
  trades.forEach((t) => {
    if (t.action === 'buy') cap = cap - Number(t.amount || 0);
    else if (t.action === 'sell') cap = cap + Number(t.amount || 0);
    values.push(cap);
  });
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 70, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [{ name: '权益曲线', type: 'line', data: values, smooth: true, areaStyle: { opacity: .15 }, lineStyle: { color: '#1a73e8' }, symbol: 'none' }],
  };
});

async function searchStocksDebounced() {
  if (stockQuery.value.length < 1) { stockResults.value = []; showDropdown.value = false; return; }
  try {
    const res = await searchStocks(stockQuery.value);
    stockResults.value = (res.data || []) as unknown as StockSearchItem[];
    showDropdown.value = stockResults.value.length > 0;
  } catch { /* */ }
}
const doSearch = debounce(searchStocksDebounced, 300);
watch(stockQuery, doSearch);

function selectStock(s: StockSearchItem) { selectedStock.value = s; stockQuery.value = s.name || s.ts_code; showDropdown.value = false; }
function hideDropdownLater() { window.setTimeout(() => { showDropdown.value = false; }, 200); }

async function submit() {
  if (!selectedStock.value) { error.value = '请选择股票'; return; }
  if (!startDate.value || !endDate.value) { error.value = '请选择回测日期区间'; return; }
  if (startDate.value >= endDate.value) { error.value = '开始日期必须早于结束日期'; return; }

  loading.value = true; error.value = ''; result.value = null;
  try {
    const params: Record<string, unknown> = {
      ts_code: selectedStock.value.ts_code,
      strategy: strategy.value,
      start_date: startDate.value,
      end_date: endDate.value,
      initial_capital: initialCapital.value,
      commission: commission.value / 100,
    };
    if (strategy.value === 'ma_cross') { params.ma_short = maShort.value; params.ma_long = maLong.value; }
    else if (strategy.value === 'macd') { params.macd_fast = macdFast.value; params.macd_slow = macdSlow.value; params.macd_signal = macdSignal.value; }
    else if (strategy.value === 'kdj') { params.kdj_period = kdjPeriod.value; params.kdj_overbought = kdjOverbought.value; params.kdj_oversold = kdjOversold.value; }
    else if (strategy.value === 'rsi') { params.rsi_period = rsiPeriod.value; params.rsi_overbought = rsiOverbought.value; params.rsi_oversold = rsiOversold.value; }
    else if (strategy.value === 'bollinger') { params.boll_period = bollPeriod.value; params.boll_std = bollStd.value; }
    result.value = await runBacktest(params);
    toast.success('回测完成');
    loadHistory();
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '回测失败';
    error.value = msg;
    toast.error(msg);
  }
  loading.value = false;
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    const res = await getBacktestHistory(1, 10);
    history.value = res.data || [];
  } catch { /* */ }
  historyLoading.value = false;
}

async function removeHistory(id: number) {
  try { await deleteBacktest(id); loadHistory(); toast.success('已删除'); } catch { toast.error('删除失败'); }
}

function reset() { selectedStock.value = null; stockQuery.value = ''; result.value = null; error.value = ''; }

onMounted(loadHistory);
</script>

<template>
  <div>
    <!-- Strategy Form -->
    <div class="card mb-3">
      <div class="card-header"><h3>回测配置</h3></div>
      <div class="card-body">
        <div class="form-grid">
          <div class="form-group" style="position:relative;">
            <label class="form-label">股票 <span class="text-up">*</span></label>
            <input v-model="stockQuery" class="form-input" placeholder="输入代码/名称搜索" @focus="showDropdown = stockResults.length > 0" @blur="hideDropdownLater()" />
            <div v-if="showDropdown" class="search-dropdown">
              <div v-for="s in stockResults" :key="s.ts_code" class="search-item" @mousedown.prevent="selectStock(s)">
                {{ s.symbol || s.ts_code }} - {{ s.name }}
              </div>
            </div>
            <span v-if="selectedStock" class="text-xs text-down mt-1">已选: {{ selectedStock.ts_code }} {{ selectedStock.name }}</span>
          </div>
          <div class="form-group">
            <label class="form-label">策略</label>
            <select v-model="strategy" class="form-select">
              <option v-for="opt in strategyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div class="form-group"><label class="form-label">开始日期 <span class="text-up">*</span></label><input v-model="startDate" type="date" class="form-input" /></div>
          <div class="form-group"><label class="form-label">结束日期 <span class="text-up">*</span></label><input v-model="endDate" type="date" class="form-input" /></div>
          <div class="form-group"><label class="form-label">初始资金</label><input v-model="initialCapital" type="number" class="form-input" /></div>
          <div class="form-group"><label class="form-label">佣金率 (%)</label><input v-model="commission" type="number" step="0.01" class="form-input" /></div>
        </div>

        <!-- Dynamic params -->
        <div class="form-grid mt-3">
          <template v-if="strategy === 'ma_cross'">
            <div class="form-group"><label class="form-label">短期均线</label><input v-model="maShort" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">长期均线</label><input v-model="maLong" type="number" class="form-input" /></div>
          </template>
          <template v-else-if="strategy === 'macd'">
            <div class="form-group"><label class="form-label">快线</label><input v-model="macdFast" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">慢线</label><input v-model="macdSlow" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">信号线</label><input v-model="macdSignal" type="number" class="form-input" /></div>
          </template>
          <template v-else-if="strategy === 'kdj'">
            <div class="form-group"><label class="form-label">周期</label><input v-model="kdjPeriod" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">超买阈值</label><input v-model="kdjOverbought" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">超卖阈值</label><input v-model="kdjOversold" type="number" class="form-input" /></div>
          </template>
          <template v-else-if="strategy === 'rsi'">
            <div class="form-group"><label class="form-label">周期</label><input v-model="rsiPeriod" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">超买阈值</label><input v-model="rsiOverbought" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">超卖阈值</label><input v-model="rsiOversold" type="number" class="form-input" /></div>
          </template>
          <template v-else-if="strategy === 'bollinger'">
            <div class="form-group"><label class="form-label">周期</label><input v-model="bollPeriod" type="number" class="form-input" /></div>
            <div class="form-group"><label class="form-label">标准差倍数</label><input v-model="bollStd" type="number" step="0.5" class="form-input" /></div>
          </template>
        </div>

        <div class="flex-between mt-3">
          <button class="btn btn-outline btn-sm" @click="reset">重置</button>
          <button class="btn btn-primary" :disabled="loading || !formValid" @click="submit">
            {{ loading ? '回测中...' : '开始回测' }}
          </button>
        </div>
        <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>
      </div>
    </div>

    <!-- Results -->
    <div v-if="result" class="card mb-3">
      <div class="card-header"><h3>回测结果</h3><span class="badge badge-info">{{ result.strategy_name }}</span></div>
      <div class="card-body">
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-label">总收益率</div><div class="stat-value" :class="(result.total_return ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(result.total_return) }}</div></div>
          <div class="stat-card"><div class="stat-label">年化收益</div><div class="stat-value">{{ formatPercent(result.annual_return) }}</div></div>
          <div class="stat-card"><div class="stat-label">夏普比率</div><div class="stat-value font-mono">{{ formatNumber(result.sharpe_ratio) }}</div></div>
          <div class="stat-card"><div class="stat-label">最大回撤</div><div class="stat-value text-up">{{ formatPercent(result.max_drawdown) }}</div></div>
          <div class="stat-card"><div class="stat-label">胜率</div><div class="stat-value">{{ formatPercent(result.win_rate) }}</div></div>
          <div class="stat-card"><div class="stat-label">波动率</div><div class="stat-value">{{ formatPercent(result.volatility) }}</div></div>
          <div class="stat-card"><div class="stat-label">最终资金</div><div class="stat-value font-mono">{{ formatNumber(result.final_capital) }}</div></div>
          <div class="stat-card"><div class="stat-label">总佣金</div><div class="stat-value font-mono">{{ formatNumber(result.total_commission) }}</div></div>
        </div>

        <div v-if="result.trades?.length" class="mt-3">
          <BaseEChart :option="equityOption" height="300px" />
        </div>

        <div v-if="result.trades?.length" class="mt-3">
          <h4 class="font-bold mb-2">交易记录 (最近20条)</h4>
          <div style="max-height:300px;overflow-y:auto;">
            <table class="data-table w-full">
              <thead><tr><th>日期</th><th>操作</th><th>价格</th><th>数量</th><th>金额</th><th>收益率</th></tr></thead>
              <tbody>
                <tr v-for="(t, i) in result.trades.slice(0, 20)" :key="i">
                  <td>{{ t.trade_date }}</td>
                  <td><span :class="t.action === 'buy' ? 'badge badge-up' : 'badge badge-down'">{{ t.action === 'buy' ? '买入' : '卖出' }}</span></td>
                  <td class="font-mono">{{ t.price }}</td>
                  <td>{{ t.quantity }}</td>
                  <td class="font-mono">{{ formatNumber(t.amount) }}</td>
                  <td :class="Number(t.return_rate ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(t.return_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- History -->
    <div class="card">
      <div class="card-header"><h3>回测历史</h3><button class="btn btn-ghost btn-sm" @click="loadHistory">刷新</button></div>
      <div class="card-body" style="overflow-x:auto;padding:0;">
        <table class="data-table w-full" v-if="history.length">
          <thead><tr><th>ID</th><th>策略</th><th>股票</th><th>总收益</th><th>夏普</th><th>最大回撤</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ h.id }}</td><td>{{ h.strategy_name }}</td><td class="font-mono">{{ h.ts_code }}</td>
              <td :class="h.total_return >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(h.total_return) }}</td>
              <td>{{ formatNumber(h.sharpe_ratio) }}</td>
              <td>{{ formatPercent(h.max_drawdown) }}</td>
              <td class="text-xs">{{ h.created_at }}</td>
              <td><button class="btn btn-sm btn-danger" @click="removeHistory(h.id)">删除</button></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state"><h4>暂无回测记录</h4></div>
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
