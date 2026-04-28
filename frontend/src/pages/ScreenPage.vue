<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import axios from 'axios';
import { useToast } from '../composables/useToast';
import { formatNumber, formatTradeDate } from '../lib/format';
import { http } from '../lib/http';
import type { ApiResponse } from '../types/stock';
import type { MarketHealthPayload, ScreenDynamicConditionForm, ScreenDynamicConditionPayload, ScreenFieldOption, ScreenQueryForm, ScreenResultPayload, ScreenStockRow, ScreenSubmissionPayload } from '../types/screen';

const toast = useToast();
const PAGE_SIZE = 200;

const fieldOptions: ScreenFieldOption[] = [
  { value: 'pe', label: 'PE' }, { value: 'pb', label: 'PB' }, { value: 'ps', label: 'PS' },
  { value: 'dv_ratio', label: '股息率' }, { value: 'total_mv', label: '总市值' }, { value: 'circ_mv', label: '流通市值' },
  { value: 'turnover_rate', label: '换手率' }, { value: 'volume_ratio', label: '量比' },
  { value: 'factor_rsi_6', label: 'RSI(6)' }, { value: 'factor_kdj_k', label: 'KDJ-K' },
  { value: 'factor_macd', label: 'MACD' }, { value: 'factor_cci', label: 'CCI' },
  { value: 'moneyflow_net_amount', label: '净流入' }, { value: 'moneyflow_buy_lg_amount_rate', label: '大单买入比' },
  { value: 'daily_close', label: '收盘价' }, { value: 'factor_pct_change', label: '涨跌幅' },
];

function makeForm(): ScreenQueryForm { return { industry: '', area: '', market: '', trade_date: '', pe_min: '', pe_max: '', pb_min: '', pb_max: '', ps_min: '', ps_max: '', dv_min: '', dv_max: '', mv_min: '', mv_max: '', circ_mv_min: '', circ_mv_max: '', turnover_min: '', turnover_max: '', volume_ratio_min: '', volume_ratio_max: '', rsi6_min: '', rsi6_max: '', kdj_k_min: '', kdj_k_max: '', macd_min: '', macd_max: '', cci_min: '', cci_max: '', net_amount_min: '', net_amount_max: '', lg_buy_rate_min: '', lg_buy_rate_max: '', net_d5_amount_min: '', net_d5_amount_max: '' }; }

let nextId = 1;
function makeCondition(): ScreenDynamicConditionForm { return { id: nextId++, fieldA: '', operator: '', compareMode: 'field', fieldB: '', value: '' }; }

const form = reactive<ScreenQueryForm>(makeForm());
const conditions = ref<ScreenDynamicConditionForm[]>([]);
const industries = ref<string[]>([]);
const areas = ref<string[]>([]);
const results = ref<ScreenStockRow[]>([]);
const resultTotal = ref(0);
const isSubmitting = ref(false);
const resultError = ref('');
const hasSubmitted = ref(false);

const isAuth = computed(() => Boolean(window.__QUANT_APP_CONTEXT__?.auth?.isAuthenticated));
const hasResults = computed(() => hasSubmitted.value && results.value.length > 0);

onMounted(async () => {
  try {
    const [ir, ar] = await Promise.allSettled([
      http.get<ApiResponse<string[]>>('/industries'),
      http.get<ApiResponse<string[]>>('/areas'),
    ]);
    if (ir.status === 'fulfilled' && ir.value.data.data) industries.value = ir.value.data.data as unknown as string[];
    if (ar.status === 'fulfilled' && ar.value.data.data) areas.value = ar.value.data.data as unknown as string[];
  } catch { /* */ }
});

function addCondition() { conditions.value.push(makeCondition()); }
function removeCondition(id: number) { conditions.value = conditions.value.filter(c => c.id !== id); }
function resetFilters() { Object.assign(form, makeForm()); conditions.value = []; results.value = []; resultTotal.value = 0; hasSubmitted.value = false; resultError.value = ''; }

async function submit() {
  hasSubmitted.value = true; resultError.value = ''; results.value = [];
  if (!isAuth.value) { resultError.value = '请先登录后再使用选股功能'; return; }
  isSubmitting.value = true;
  try {
    const payload: any = { page: 1, page_size: PAGE_SIZE };
    for (const [k, v] of Object.entries(form)) { if (String(v).trim()) payload[k] = String(v).trim(); }
    const dyn = conditions.value.filter(c => c.fieldA && c.operator && (c.compareMode === 'field' ? c.fieldB : c.value.trim())).map(c => { const p: ScreenDynamicConditionPayload = { field_a: c.fieldA, operator: c.operator }; if (c.compareMode === 'field') p.field_b = c.fieldB; else p.value = Number(c.value); return p; });
    if (dyn.length) payload.dynamic_conditions = dyn;
    const r = await http.post<ApiResponse<ScreenResultPayload | ScreenStockRow[]>>('/analysis/screen', payload, { validateStatus: () => true });
    if (r.status === 401 || r.data?.code === 401) { resultError.value = '请先登录'; return; }
    if (r.data?.code !== 200) { resultError.value = r.data?.message || '筛选失败'; return; }
    const d: any = r.data.data;
    const stocks: ScreenStockRow[] = Array.isArray(d) ? d : (d?.stocks || []);
    results.value = stocks;
    resultTotal.value = Array.isArray(d) ? d.length : (d?.total || stocks.length);
    if (!stocks.length) toast.info('没有匹配的股票');
  } catch (e) { resultError.value = axios.isAxiosError(e) ? e.message : '请求失败'; }
  isSubmitting.value = false;
}
function openStock(code: string) { const url = '/app/stock/' + code; window.open(url, '_blank', 'noopener'); }
</script>

<template>
  <div>
    <div class="card">
      <div class="card-header"><h3>条件选股</h3><span v-if="isAuth" class="badge badge-down">已登录</span></div>
      <p class="text-sm text-muted" style="margin-bottom:16px;">设置筛选条件，结果最多显示前 {{ PAGE_SIZE }} 条</p>

      <!-- Basic filters -->
      <div class="form-grid" style="margin-bottom:12px;">
        <div class="form-group"><label class="form-label">行业</label><select v-model="form.industry" class="form-select"><option value="">全部</option><option v-for="i in industries" :key="i" :value="i">{{ i }}</option></select></div>
        <div class="form-group"><label class="form-label">地域</label><select v-model="form.area" class="form-select"><option value="">全部</option><option v-for="a in areas" :key="a" :value="a">{{ a }}</option></select></div>
        <div class="form-group"><label class="form-label">市场</label><select v-model="form.market" class="form-select"><option value="">全部</option><option value="SH">上海</option><option value="SZ">深圳</option><option value="BJ">北京</option></select></div>
        <div class="form-group"><label class="form-label">交易日期</label><input v-model="form.trade_date" type="date" class="form-input" /></div>
      </div>

      <!-- Valuation range -->
      <div style="font-size:13px;font-weight:600;margin-bottom:8px;">估值范围</div>
      <div class="form-grid mb-2">
        <div class="form-group"><label class="form-label">PE 最小</label><input v-model="form.pe_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">PE 最大</label><input v-model="form.pe_max" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">PB 最小</label><input v-model="form.pb_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">PB 最大</label><input v-model="form.pb_max" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">PS 最小</label><input v-model="form.ps_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">PS 最大</label><input v-model="form.ps_max" type="number" step="0.1" class="form-input" /></div>
      </div>

      <!-- Market value -->
      <div style="font-size:13px;font-weight:600;margin-bottom:8px;">市值与交易</div>
      <div class="form-grid mb-2">
        <div class="form-group"><label class="form-label">总市值最小</label><input v-model="form.mv_min" type="number" step="100" class="form-input" /></div>
        <div class="form-group"><label class="form-label">总市值最大</label><input v-model="form.mv_max" type="number" step="100" class="form-input" /></div>
        <div class="form-group"><label class="form-label">流通市值最小</label><input v-model="form.circ_mv_min" type="number" step="100" class="form-input" /></div>
        <div class="form-group"><label class="form-label">流通市值最大</label><input v-model="form.circ_mv_max" type="number" step="100" class="form-input" /></div>
        <div class="form-group"><label class="form-label">换手率最小(%)</label><input v-model="form.turnover_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">换手率最大(%)</label><input v-model="form.turnover_max" type="number" step="0.1" class="form-input" /></div>
      </div>

      <!-- Technical indicators -->
      <div style="font-size:13px;font-weight:600;margin-bottom:8px;">技术指标</div>
      <div class="form-grid mb-2">
        <div class="form-group"><label class="form-label">RSI6 最小</label><input v-model="form.rsi6_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">RSI6 最大</label><input v-model="form.rsi6_max" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">KDJ-K 最小</label><input v-model="form.kdj_k_min" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">KDJ-K 最大</label><input v-model="form.kdj_k_max" type="number" step="0.1" class="form-input" /></div>
        <div class="form-group"><label class="form-label">MACD 最小</label><input v-model="form.macd_min" type="number" step="0.01" class="form-input" /></div>
        <div class="form-group"><label class="form-label">MACD 最大</label><input v-model="form.macd_max" type="number" step="0.01" class="form-input" /></div>
      </div>

      <!-- Dynamic conditions -->
      <div class="flex-between mb-2"><span style="font-size:13px;font-weight:600;">动态条件</span><button class="btn btn-ghost btn-sm" @click="addCondition">+ 添加</button></div>
      <div v-if="conditions.length" style="display:flex;flex-direction:column;gap:8px;margin-bottom:12px;">
        <div v-for="c in conditions" :key="c.id" class="form-grid" style="background:var(--cb-gray);padding:8px 10px;border-radius:var(--cb-radius-md);">
          <div class="form-group"><label class="form-label">字段A</label><select v-model="c.fieldA" class="form-select" style="font-size:12px;"><option value="">选择</option><option v-for="o in fieldOptions" :key="o.value" :value="o.value">{{ o.label }}</option></select></div>
          <div class="form-group"><label class="form-label">运算符</label><select v-model="c.operator" class="form-select" style="font-size:12px;"><option value="">选择</option><option v-for="op in ['>','>=','<','<=','=','!=']" :key="op" :value="op">{{ op }}</option></select></div>
          <div class="form-group"><label class="form-label">比较方式</label><select v-model="c.compareMode" class="form-select" style="font-size:12px;"><option value="field">字段B</option><option value="value">固定值</option></select></div>
          <div class="form-group" v-if="c.compareMode === 'field'"><label class="form-label">字段B</label><select v-model="c.fieldB" class="form-select" style="font-size:12px;"><option value="">选择</option><option v-for="o in fieldOptions" :key="o.value" :value="o.value">{{ o.label }}</option></select></div>
          <div class="form-group" v-else><label class="form-label">值</label><input v-model="c.value" type="number" step="0.01" class="form-input" style="font-size:12px;" /></div>
          <div class="form-group" style="justify-content:flex-end;"><button class="btn btn-ghost btn-sm btn-danger" @click="removeCondition(c.id)">删除</button></div>
        </div>
      </div>

      <div class="flex-between">
        <button class="btn btn-ghost btn-sm" @click="resetFilters">重置</button>
        <button class="btn btn-primary" :disabled="isSubmitting || !isAuth" @click="submit">{{ isSubmitting ? '筛选中...' : isAuth ? '开始筛选' : '请先登录' }}</button>
      </div>
    </div>

    <!-- Results -->
    <div v-if="isSubmitting" class="card"><div class="skeleton" style="height:120px;" /></div>
    <div v-else-if="resultError" class="alert alert-error">{{ resultError }}</div>
    <div v-else-if="hasResults" class="card card-table">
      <div class="card-header" style="padding:16px;"><h3>筛选结果 ({{ resultTotal }})</h3></div>
      <table class="data-table w-full">
        <thead><tr><th>代码</th><th>名称</th><th>行业</th><th>收盘</th><th>PE</th><th>PB</th><th>换手率</th><th>涨跌幅</th><th>净流入</th><th>总市值</th></tr></thead>
        <tbody>
          <tr v-for="s in results" :key="s.ts_code" class="clickable" @click="openStock(s.ts_code)">
            <td class="font-mono font-bold">{{ s.ts_code }}</td>
            <td class="font-bold">{{ s.name || '--' }}</td>
            <td>{{ s.industry || '--' }}</td>
            <td class="font-mono">{{ formatNumber(s.daily_close) }}</td>
            <td>{{ formatNumber(s.pe) }}</td>
            <td>{{ formatNumber(s.pb) }}</td>
            <td>{{ formatNumber(s.turnover_rate, 1) }}%</td>
            <td :class="Number(s.factor_pct_change || 0) >= 0 ? 'text-up' : 'text-down'">{{ Number(s.factor_pct_change || 0) >= 0 ? '+' : '' }}{{ formatNumber(s.factor_pct_change, 2) }}%</td>
            <td :class="Number(s.moneyflow_net_amount || 0) >= 0 ? 'text-up' : 'text-down'">{{ formatNumber(s.moneyflow_net_amount, 0) }}</td>
            <td class="font-mono">{{ formatNumber(s.total_mv, 0) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="card empty-state"><h4>设置条件后开始筛选</h4><p class="text-sm text-muted">支持多条件组合与动态字段比较</p></div>
  </div>
</template>
