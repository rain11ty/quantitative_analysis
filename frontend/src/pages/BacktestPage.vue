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
const result = ref<BacktestResult | null>(null);
const loading = ref(false);
const error = ref('');
const history = ref<BacktestRecord[]>([]);

const formValid = computed(() => selectedStock.value && strategy.value && startDate.value && endDate.value && startDate.value < endDate.value);

const equityOption = computed<EChartsOption>(() => {
  const trades = result.value?.trades;
  if (!Array.isArray(trades) || !trades.length) return {};
  const values: number[] = []; let cap = initialCapital.value;
  (trades as Record<string, unknown>[]).forEach(t => { cap = t.action === 'buy' ? cap - Number(t.amount || 0) : cap + Number(t.amount || 0); values.push(cap); });
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 16, top: 12, bottom: 28 },
    xAxis: { type: 'category', data: (trades as Record<string, unknown>[]).map(t => t.trade_date || ''), axisLabel: { fontSize: 10, color: 'rgba(10,11,13,0.48)' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(10,11,13,0.04)' } } },
    series: [{ type: 'line', data: values, smooth: true, lineStyle: { color: '#0052ff', width: 1.5 }, symbol: 'none', areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(0,82,255,0.14)' }, { offset: 1, color: 'rgba(0,82,255,0)' }] } } }],
  };
});

watch(stockQuery, debounce(async () => {
  if (stockQuery.value.length < 1) { stockResults.value = []; showDropdown.value = false; return; }
  try { const res = await searchStocks(stockQuery.value); stockResults.value = (res.data || []) as unknown as StockSearchItem[]; showDropdown.value = true; } catch { /* */ }
}, 300));

function selectStock(s: StockSearchItem) { selectedStock.value = s; stockQuery.value = s.name || s.ts_code; showDropdown.value = false; }
function hideDropdown() { setTimeout(() => { showDropdown.value = false; }, 200); }

async function submit() {
  if (!selectedStock.value) { error.value = '请选择股票'; return; }
  if (!startDate.value || !endDate.value) { error.value = '请选择日期区间'; return; }
  if (startDate.value >= endDate.value) { error.value = '开始日期需早于结束日期'; return; }
  loading.value = true; error.value = ''; result.value = null;
  try {
    const params: Record<string, unknown> = { ts_code: selectedStock.value.ts_code, strategy: strategy.value, start_date: startDate.value, end_date: endDate.value, initial_capital: initialCapital.value, commission: commission.value / 100 };
    if (strategy.value === 'ma_cross') { params.ma_short = maShort.value; params.ma_long = maLong.value; }
    result.value = await runBacktest(params);
    toast.success('回测完成'); loadHistory();
  } catch (e: unknown) { const msg = e instanceof Error ? e.message : '回测失败'; error.value = msg; toast.error(msg); }
  loading.value = false;
}

async function loadHistory() { try { const res = await getBacktestHistory(1, 10); history.value = res.data || []; } catch { /* */ } }
async function removeHistory(id: number) { try { await deleteBacktest(id); loadHistory(); toast.success('已删除'); } catch { toast.error('删除失败'); } }
onMounted(loadHistory);
</script>

<template>
  <div>
    <div class="card">
      <div class="card-header"><h3>回测配置</h3></div>
      <div class="form-grid mb-2">
        <div class="form-group" style="position:relative;">
          <label class="form-label">股票</label>
          <input v-model="stockQuery" class="form-input" placeholder="搜索代码/名称" @focus="showDropdown = stockResults.length > 0" @blur="hideDropdown()" />
          <div v-if="showDropdown" style="position:absolute;top:100%;left:0;right:0;z-index:10;background:var(--cb-white);border:1px solid var(--cb-border);border-radius:var(--cb-radius-lg);max-height:180px;overflow-y:auto;box-shadow:var(--cb-shadow-sm);">
            <div v-for="s in stockResults" :key="s.ts_code" style="padding:8px 12px;cursor:pointer;font-size:13px;" @mousedown.prevent="selectStock(s)">{{ s.symbol || s.ts_code }} - {{ s.name }}</div>
          </div>
          <span v-if="selectedStock" class="text-xs text-down" style="margin-top:4px;">已选: {{ selectedStock.ts_code }} {{ selectedStock.name }}</span>
        </div>
        <div class="form-group"><label class="form-label">策略</label>
          <select v-model="strategy" class="form-select">
            <option value="ma_cross">均线交叉</option><option value="macd">MACD</option><option value="kdj">KDJ</option><option value="rsi">RSI</option><option value="bollinger">布林带</option>
          </select>
        </div>
        <div class="form-group"><label class="form-label">开始日期</label><input v-model="startDate" type="date" class="form-input" /></div>
        <div class="form-group"><label class="form-label">结束日期</label><input v-model="endDate" type="date" class="form-input" /></div>
        <div class="form-group"><label class="form-label">初始资金</label><input v-model="initialCapital" type="number" class="form-input" /></div>
        <div class="form-group"><label class="form-label">佣金率 (%)</label><input v-model="commission" type="number" step="0.01" class="form-input" /></div>
      </div>
      <template v-if="strategy === 'ma_cross'">
        <div class="form-grid mb-2"><div class="form-group"><label class="form-label">短期均线</label><input v-model="maShort" type="number" class="form-input" /></div><div class="form-group"><label class="form-label">长期均线</label><input v-model="maLong" type="number" class="form-input" /></div></div>
      </template>
      <div class="flex-between">
        <button class="btn btn-ghost btn-sm" @click="selectedStock = null; stockQuery = ''; result = null; error = ''">重置</button>
        <button class="btn btn-primary" :disabled="loading || !formValid" @click="submit">{{ loading ? '回测中...' : '开始回测' }}</button>
      </div>
      <div v-if="error" class="alert alert-error mt-2">{{ error }}</div>
    </div>

    <div v-if="result" class="card">
      <div class="card-header"><h3>回测结果</h3><span class="badge badge-info">{{ result.strategy_name }}</span></div>
      <div class="stat-grid mb-3">
        <div class="stat-item"><div class="stat-label">总收益率</div><div class="stat-value" :class="(result.total_return ?? 0) >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(result.total_return) }}</div></div>
        <div class="stat-item"><div class="stat-label">年化收益</div><div class="stat-value">{{ formatPercent(result.annual_return) }}</div></div>
        <div class="stat-item"><div class="stat-label">夏普比率</div><div class="stat-value font-mono">{{ formatNumber(result.sharpe_ratio) }}</div></div>
        <div class="stat-item"><div class="stat-label">最大回撤</div><div class="stat-value text-up">{{ formatPercent(result.max_drawdown) }}</div></div>
        <div class="stat-item"><div class="stat-label">胜率</div><div class="stat-value">{{ formatPercent(result.win_rate) }}</div></div>
        <div class="stat-item"><div class="stat-label">最终资金</div><div class="stat-value font-mono">{{ formatNumber(result.final_capital) }}</div></div>
      </div>
      <BaseEChart v-if="result.trades?.length" :option="equityOption" height="280px" />
    </div>

    <div class="card" style="padding:16px;">
      <div class="card-header" style="margin-bottom:8px;"><h3>回测历史</h3><button class="btn btn-ghost btn-sm" @click="loadHistory">刷新</button></div>
      <div style="overflow-x:auto;">
        <table class="data-table w-full" v-if="history.length">
          <thead><tr><th>ID</th><th>策略</th><th>股票</th><th>总收益</th><th>夏普</th><th>最大回撤</th><th>时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ h.id }}</td><td>{{ h.strategy_name }}</td><td class="font-mono">{{ h.ts_code }}</td>
              <td :class="h.total_return >= 0 ? 'text-down' : 'text-up'">{{ formatPercent(h.total_return) }}</td>
              <td>{{ formatNumber(h.sharpe_ratio) }}</td><td>{{ formatPercent(h.max_drawdown) }}</td>
              <td class="text-xs">{{ h.created_at }}</td>
              <td><button class="btn btn-ghost btn-sm btn-danger" @click="removeHistory(h.id)">删除</button></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state" style="padding:24px;"><h4>暂无记录</h4></div>
      </div>
    </div>
  </div>
</template>
