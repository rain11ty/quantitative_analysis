<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import axios from 'axios';

import { formatNumber, formatTradeDate } from '../lib/format';
import { http } from '../lib/http';
import type { ApiResponse } from '../types/stock';
import type {
  MarketHealthPayload,
  ScreenDynamicConditionForm,
  ScreenDynamicConditionPayload,
  ScreenFieldOption,
  ScreenQueryForm,
  ScreenResultPayload,
  ScreenStockRow,
  ScreenSubmissionPayload,
} from '../types/screen';

type NoticeTone = 'info' | 'success' | 'warning' | 'error';

const PAGE_SIZE = 200;
const appContext = window.__QUANT_APP_CONTEXT__;

const marketOptions = [
  { value: '', label: 'All markets' },
  { value: 'SH', label: 'Shanghai (SH)' },
  { value: 'SZ', label: 'Shenzhen (SZ)' },
  { value: 'BJ', label: 'Beijing (BJ)' },
] as const;

const compareModeOptions = [
  { value: 'field', label: 'Field to field' },
  { value: 'value', label: 'Field to value' },
] as const;

const operatorOptions = ['>', '>=', '<', '<=', '=', '!='] as const;

const screenFieldOptions: ScreenFieldOption[] = [
  { value: 'pe', label: 'PE' },
  { value: 'pb', label: 'PB' },
  { value: 'ps', label: 'PS' },
  { value: 'dv_ratio', label: 'Dividend yield' },
  { value: 'total_mv', label: 'Total market value' },
  { value: 'circ_mv', label: 'Float market value' },
  { value: 'turnover_rate', label: 'Turnover rate' },
  { value: 'volume_ratio', label: 'Volume ratio' },
  { value: 'factor_rsi_6', label: 'RSI(6)' },
  { value: 'factor_kdj_k', label: 'KDJ-K' },
  { value: 'factor_macd', label: 'MACD' },
  { value: 'factor_cci', label: 'CCI' },
  { value: 'moneyflow_net_amount', label: 'Net inflow amount' },
  { value: 'moneyflow_buy_lg_amount_rate', label: 'Large buy rate' },
  { value: 'moneyflow_net_d5_amount', label: '5-day net inflow' },
  { value: 'daily_close', label: 'Close price' },
  { value: 'factor_pct_change', label: 'Pct change' },
  { value: 'ma5', label: 'MA5' },
  { value: 'ma10', label: 'MA10' },
  { value: 'ma20', label: 'MA20' },
  { value: 'ma30', label: 'MA30' },
  { value: 'ma60', label: 'MA60' },
  { value: 'ma120', label: 'MA120' },
];

function createInitialForm(): ScreenQueryForm {
  return {
    industry: '',
    area: '',
    market: '',
    trade_date: '',
    pe_min: '',
    pe_max: '',
    pb_min: '',
    pb_max: '',
    ps_min: '',
    ps_max: '',
    dv_min: '',
    dv_max: '',
    mv_min: '',
    mv_max: '',
    circ_mv_min: '',
    circ_mv_max: '',
    turnover_min: '',
    turnover_max: '',
    volume_ratio_min: '',
    volume_ratio_max: '',
    rsi6_min: '',
    rsi6_max: '',
    kdj_k_min: '',
    kdj_k_max: '',
    macd_min: '',
    macd_max: '',
    cci_min: '',
    cci_max: '',
    net_amount_min: '',
    net_amount_max: '',
    lg_buy_rate_min: '',
    lg_buy_rate_max: '',
    net_d5_amount_min: '',
    net_d5_amount_max: '',
  };
}

let nextDynamicConditionId = 1;

function createDynamicCondition(): ScreenDynamicConditionForm {
  return {
    id: nextDynamicConditionId++,
    fieldA: '',
    operator: '',
    compareMode: 'field',
    fieldB: '',
    value: '',
  };
}

const form = reactive<ScreenQueryForm>(createInitialForm());
const dynamicConditions = ref<ScreenDynamicConditionForm[]>([]);
const industries = ref<string[]>([]);
const areas = ref<string[]>([]);
const latestTradeDate = ref('');

const isBootstrapping = ref(true);
const isSubmitting = ref(false);
const marketHealthLoading = ref(false);

const lookupsWarning = ref('');
const resultError = ref('');
const hasSubmitted = ref(false);
const resultSummary = ref('Set your filters and run the screen. Results are capped at the first 200 matches.');
const marketHealthTone = ref<NoticeTone>('info');
const marketHealthMessage = ref('Sign in to preload the latest trade date from /api/market/health.');

const results = ref<ScreenStockRow[]>([]);
const resultTotal = ref(0);
const resultHasMore = ref(false);

const isAuthenticated = computed(() => Boolean(appContext?.auth?.isAuthenticated));
const displayName = computed(() => appContext?.auth?.displayName || 'Guest');
const loginUrl = computed(() => `/auth/login?next=${encodeURIComponent('/app/screen')}`);

const baseConditionCount = computed(() =>
  Object.values(form).filter((value) => String(value).trim() !== '').length,
);

const activeDynamicConditionCount = computed(() =>
  dynamicConditions.value.filter((item) => isDynamicConditionComplete(item)).length,
);

const resultCountLabel = computed(() => `${resultTotal.value} matches`);
const authStatusLabel = computed(() => (isAuthenticated.value ? 'Signed in' : 'Sign-in required'));
const selectionSummary = computed(
  () =>
    `${baseConditionCount.value} basic filters and ${activeDynamicConditionCount.value} dynamic rules configured.`,
);

function setMarketHealthState(tone: NoticeTone, message: string) {
  marketHealthTone.value = tone;
  marketHealthMessage.value = message;
}

function normalizeDateInput(value: string | null | undefined): string {
  if (!value) {
    return '';
  }

  if (/^\d{8}$/.test(value)) {
    return formatTradeDate(value);
  }

  return value;
}

function isDynamicConditionComplete(item: ScreenDynamicConditionForm): boolean {
  if (!item.fieldA || !item.operator) {
    return false;
  }

  if (item.compareMode === 'field') {
    return Boolean(item.fieldB);
  }

  return item.value.trim() !== '';
}

function addDynamicCondition() {
  dynamicConditions.value.push(createDynamicCondition());
}

function removeDynamicCondition(id: number) {
  dynamicConditions.value = dynamicConditions.value.filter((item) => item.id !== id);
}

function resetDynamicConditionMode(item: ScreenDynamicConditionForm) {
  if (item.compareMode === 'field') {
    item.value = '';
    return;
  }

  item.fieldB = '';
}

function buildDynamicConditions(): ScreenDynamicConditionPayload[] {
  return dynamicConditions.value
    .filter((item) => isDynamicConditionComplete(item))
    .map((item) => {
      const payload: ScreenDynamicConditionPayload = {
        field_a: item.fieldA,
        operator: item.operator,
      };

      if (item.compareMode === 'field') {
        payload.field_b = item.fieldB;
      } else {
        payload.value = Number(item.value);
      }

      return payload;
    });
}

function buildSubmitPayload(): ScreenSubmissionPayload {
  const payload: ScreenSubmissionPayload = {
    page: 1,
    page_size: PAGE_SIZE,
  };

  for (const [key, value] of Object.entries(form)) {
    const normalized = String(value).trim();
    if (normalized !== '') {
      payload[key as keyof ScreenQueryForm] = normalized;
    }
  }

  const conditions = buildDynamicConditions();
  if (conditions.length > 0) {
    payload.dynamic_conditions = conditions;
  }

  return payload;
}

function resetResultState() {
  hasSubmitted.value = false;
  resultError.value = '';
  results.value = [];
  resultTotal.value = 0;
  resultHasMore.value = false;
  resultSummary.value = 'Set your filters and run the screen. Results are capped at the first 200 matches.';
}

function resetFilters() {
  Object.assign(form, createInitialForm());
  form.trade_date = latestTradeDate.value;
  dynamicConditions.value = [];
  resetResultState();
}

function normalizeScreenResult(
  payload: ScreenResultPayload | ScreenStockRow[] | null | undefined,
): ScreenResultPayload {
  if (Array.isArray(payload)) {
    return {
      stocks: payload,
      total: payload.length,
      has_more: false,
      error: null,
    };
  }

  return {
    stocks: payload?.stocks || [],
    total: typeof payload?.total === 'number' ? payload.total : (payload?.stocks?.length || 0),
    has_more: Boolean(payload?.has_more),
    error: payload?.error || null,
  };
}

function formatPercent(value: unknown, decimals = 2) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '--';
  }

  return `${number.toFixed(decimals)}%`;
}

function formatSignedPercent(value: unknown, decimals = 2) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '--';
  }

  const sign = number > 0 ? '+' : '';
  return `${sign}${number.toFixed(decimals)}%`;
}

function formatMoneyWan(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '--';
  }

  if (Math.abs(number) >= 10000) {
    return `${(number / 10000).toFixed(2)} wan`;
  }

  return number.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatMarketValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '--';
  }

  // Backend market value fields are stored in "wan CNY".
  if (Math.abs(number) >= 10000) {
    return `${(number / 10000).toFixed(2)} yi`;
  }

  return `${number.toLocaleString('zh-CN')} wan`;
}

function getAxiosMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  return String(error.response?.data?.message || error.message || fallback);
}

async function loadIndustries() {
  try {
    const response = await http.get<ApiResponse<string[]>>('/industries');
    industries.value = Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    lookupsWarning.value = getAxiosMessage(
      error,
      'Failed to load /api/industries. Other filters are still available.',
    );
  }
}

async function loadAreas() {
  try {
    const response = await http.get<ApiResponse<string[]>>('/areas');
    areas.value = Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    const message = getAxiosMessage(
      error,
      'Failed to load /api/areas. Other filters are still available.',
    );
    lookupsWarning.value = lookupsWarning.value ? `${lookupsWarning.value} ${message}` : message;
  }
}

async function loadLatestTradeDate(forceOverride = false) {
  if (!isAuthenticated.value) {
    setMarketHealthState(
      'warning',
      'This endpoint currently requires a signed-in session. Fill the trade date manually or sign in first.',
    );
    return;
  }

  marketHealthLoading.value = true;

  try {
    const response = await http.get<ApiResponse<MarketHealthPayload>>('/market/health', {
      validateStatus: () => true,
    });

    if (response.status === 401 || response.data?.code === 401) {
      setMarketHealthState(
        'warning',
        'The current session is not authorized for /api/market/health. Sign in again to preload the trade date.',
      );
      return;
    }

    if (response.status >= 200 && response.status < 300 && response.data?.code === 200) {
      const date = normalizeDateInput(response.data.data?.latest_trade_date || '');
      latestTradeDate.value = date;
      if (date && (!form.trade_date || forceOverride)) {
        form.trade_date = date;
      }

      setMarketHealthState(
        'success',
        date
          ? `Latest trade date loaded from /api/market/health: ${date}.`
          : 'Market health responded, but no latest trade date was returned.',
      );
      return;
    }

    setMarketHealthState(
      'error',
      response.data?.message || 'Market health did not return a usable trade date.',
    );
  } catch (error) {
    setMarketHealthState(
      'error',
      getAxiosMessage(error, 'Failed to request /api/market/health. Please fill the trade date manually.'),
    );
  } finally {
    marketHealthLoading.value = false;
  }
}

async function submitScreening() {
  hasSubmitted.value = true;
  resultError.value = '';
  results.value = [];
  resultTotal.value = 0;
  resultHasMore.value = false;

  if (!isAuthenticated.value) {
    resultError.value =
      'POST /api/analysis/screen is currently blocked for anonymous sessions in this environment. Sign in first.';
    resultSummary.value = 'The page can still be reviewed, but screening requires an authenticated session.';
    return;
  }

  isSubmitting.value = true;

  try {
    const response = await http.post<ApiResponse<ScreenResultPayload | ScreenStockRow[]>>(
      '/analysis/screen',
      buildSubmitPayload(),
      {
        validateStatus: () => true,
      },
    );

    if (response.status === 401 || response.data?.code === 401) {
      resultError.value =
        'The current session is not authorized for /api/analysis/screen. Sign in again and retry.';
      resultSummary.value = 'The screening endpoint rejected the current session.';
      return;
    }

    if (response.status < 200 || response.status >= 300 || response.data?.code !== 200) {
      resultError.value = response.data?.message || 'Screening failed. Please retry after checking your filters.';
      resultSummary.value = 'The backend did not return a usable screening payload.';
      return;
    }

    const normalized = normalizeScreenResult(response.data.data);
    if (normalized.error) {
      resultError.value = normalized.error;
      resultSummary.value = 'The backend reported an error while building the result set.';
      return;
    }

    results.value = normalized.stocks || [];
    resultTotal.value = normalized.total || 0;
    resultHasMore.value = Boolean(normalized.has_more);
    resultSummary.value = resultHasMore.value
      ? `Only the first ${PAGE_SIZE} rows are shown. Narrow the filters for a smaller result set.`
      : 'All matching rows are shown below.';
  } catch (error) {
    resultError.value = getAxiosMessage(error, 'The request failed before a result set was returned.');
    resultSummary.value = 'The result area is showing the request failure state.';
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(async () => {
  document.title = 'Screen - Vue Frontend';
  await Promise.allSettled([loadIndustries(), loadAreas(), loadLatestTradeDate()]);
  isBootstrapping.value = false;
});
</script>

<template>
  <section class="stack screen-page">
    <section class="screen-hero-grid">
      <article class="panel-card accent-card screen-hero-card">
        <div class="page-header-row">
          <div>
            <p class="eyebrow">Stock Screen</p>
            <h3>Multi-factor screening workspace</h3>
          </div>
          <span class="status-pill">{{ authStatusLabel }}</span>
        </div>
        <p>
          This Vue route mirrors the legacy screening contract and keeps the same payload shape for
          <code>/api/analysis/screen</code>, including <code>dynamic_conditions</code>.
        </p>
        <p class="muted">
          Current user: {{ displayName }}. {{ selectionSummary }}
        </p>
        <div class="screen-action-bar">
          <button
            v-if="isAuthenticated"
            class="action-button primary"
            :disabled="isSubmitting"
            @click="submitScreening"
          >
            <span v-if="isSubmitting" class="loading-ring" aria-hidden="true"></span>
            {{ isSubmitting ? 'Running screen...' : 'Run screen' }}
          </button>
          <a v-else class="action-button primary link-button" :href="loginUrl">Sign in to screen</a>
          <button class="action-button ghost" type="button" @click="resetFilters">Clear filters</button>
        </div>
      </article>

      <div class="screen-stat-grid">
        <article class="panel-card stat-card">
          <span class="stat-label">Industries</span>
          <strong>{{ industries.length }}</strong>
          <span class="muted">Loaded from /api/industries</span>
        </article>
        <article class="panel-card stat-card">
          <span class="stat-label">Areas</span>
          <strong>{{ areas.length }}</strong>
          <span class="muted">Loaded from /api/areas</span>
        </article>
        <article class="panel-card stat-card">
          <span class="stat-label">Trade date</span>
          <strong>{{ form.trade_date || '--' }}</strong>
          <span class="muted">{{ latestTradeDate ? 'Preloaded from market health' : 'Manual input ready' }}</span>
        </article>
        <article class="panel-card stat-card">
          <span class="stat-label">Dynamic rules</span>
          <strong>{{ dynamicConditions.length }}</strong>
          <span class="muted">Field-to-field and field-to-value comparisons</span>
        </article>
      </div>
    </section>

    <div v-if="lookupsWarning" class="notice-banner notice-warning">
      {{ lookupsWarning }}
    </div>

    <article class="panel-card">
      <div class="section-header">
        <div>
          <p class="eyebrow">Market health</p>
          <h3>Trade date preload status</h3>
        </div>
        <button
          class="action-button compact"
          type="button"
          :disabled="marketHealthLoading"
          @click="loadLatestTradeDate(true)"
        >
          <span v-if="marketHealthLoading" class="loading-ring" aria-hidden="true"></span>
          {{ marketHealthLoading ? 'Refreshing...' : 'Refresh trade date' }}
        </button>
      </div>
      <div class="notice-banner" :class="`notice-${marketHealthTone}`">
        {{ marketHealthMessage }}
      </div>
    </article>

    <form class="panel-card stack" @submit.prevent="submitScreening">
      <div class="section-header">
        <div>
          <p class="eyebrow">Filters</p>
          <h3>Screen input contract</h3>
        </div>
        <p class="muted section-copy">
          The field names below map directly to the existing backend filters so the legacy and Vue pages
          stay aligned during the migration.
        </p>
      </div>

      <div v-if="isBootstrapping" class="state-card">
        Loading industry, area, and trade date context...
      </div>

      <div class="filter-grid">
        <section class="filter-group">
          <h4>Basic filters</h4>
          <label class="field-block">
            <span>Industry</span>
            <select v-model="form.industry" class="field-input">
              <option value="">All</option>
              <option v-for="industry in industries" :key="industry" :value="industry">
                {{ industry }}
              </option>
            </select>
          </label>
          <label class="field-block">
            <span>Area</span>
            <select v-model="form.area" class="field-input">
              <option value="">All</option>
              <option v-for="area in areas" :key="area" :value="area">
                {{ area }}
              </option>
            </select>
          </label>
          <label class="field-block">
            <span>Market</span>
            <select v-model="form.market" class="field-input">
              <option v-for="market in marketOptions" :key="market.value" :value="market.value">
                {{ market.label }}
              </option>
            </select>
          </label>
          <label class="field-block">
            <span>Trade date</span>
            <input v-model="form.trade_date" class="field-input" type="date" />
            <span class="field-help">Leave blank to rely on the latest backend trade date.</span>
          </label>
        </section>

        <section class="filter-group">
          <h4>Valuation</h4>
          <div class="range-grid">
            <label class="field-block">
              <span>PE min</span>
              <input v-model="form.pe_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>PE max</span>
              <input v-model="form.pe_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>PB min</span>
              <input v-model="form.pb_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>PB max</span>
              <input v-model="form.pb_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>PS min</span>
              <input v-model="form.ps_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>PS max</span>
              <input v-model="form.ps_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Dividend yield min (%)</span>
              <input v-model="form.dv_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Dividend yield max (%)</span>
              <input v-model="form.dv_max" class="field-input" type="number" step="0.1" />
            </label>
          </div>
        </section>

        <section class="filter-group">
          <h4>Market value and trading</h4>
          <div class="range-grid">
            <label class="field-block">
              <span>Total market value min</span>
              <input v-model="form.mv_min" class="field-input" type="number" step="100" />
            </label>
            <label class="field-block">
              <span>Total market value max</span>
              <input v-model="form.mv_max" class="field-input" type="number" step="100" />
            </label>
            <label class="field-block">
              <span>Float market value min</span>
              <input v-model="form.circ_mv_min" class="field-input" type="number" step="100" />
            </label>
            <label class="field-block">
              <span>Float market value max</span>
              <input v-model="form.circ_mv_max" class="field-input" type="number" step="100" />
            </label>
            <label class="field-block">
              <span>Turnover rate min (%)</span>
              <input v-model="form.turnover_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Turnover rate max (%)</span>
              <input v-model="form.turnover_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Volume ratio min</span>
              <input v-model="form.volume_ratio_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Volume ratio max</span>
              <input v-model="form.volume_ratio_max" class="field-input" type="number" step="0.1" />
            </label>
          </div>
        </section>

        <section class="filter-group">
          <h4>Technical indicators</h4>
          <div class="range-grid">
            <label class="field-block">
              <span>RSI(6) min</span>
              <input v-model="form.rsi6_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>RSI(6) max</span>
              <input v-model="form.rsi6_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>KDJ-K min</span>
              <input v-model="form.kdj_k_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>KDJ-K max</span>
              <input v-model="form.kdj_k_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>MACD min</span>
              <input v-model="form.macd_min" class="field-input" type="number" step="0.01" />
            </label>
            <label class="field-block">
              <span>MACD max</span>
              <input v-model="form.macd_max" class="field-input" type="number" step="0.01" />
            </label>
            <label class="field-block">
              <span>CCI min</span>
              <input v-model="form.cci_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>CCI max</span>
              <input v-model="form.cci_max" class="field-input" type="number" step="0.1" />
            </label>
          </div>
        </section>

        <section class="filter-group">
          <h4>Moneyflow</h4>
          <div class="range-grid">
            <label class="field-block">
              <span>Net inflow min</span>
              <input v-model="form.net_amount_min" class="field-input" type="number" step="1" />
            </label>
            <label class="field-block">
              <span>Net inflow max</span>
              <input v-model="form.net_amount_max" class="field-input" type="number" step="1" />
            </label>
            <label class="field-block">
              <span>Large buy rate min (%)</span>
              <input v-model="form.lg_buy_rate_min" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>Large buy rate max (%)</span>
              <input v-model="form.lg_buy_rate_max" class="field-input" type="number" step="0.1" />
            </label>
            <label class="field-block">
              <span>5-day net inflow min</span>
              <input v-model="form.net_d5_amount_min" class="field-input" type="number" step="1" />
            </label>
            <label class="field-block">
              <span>5-day net inflow max</span>
              <input v-model="form.net_d5_amount_max" class="field-input" type="number" step="1" />
            </label>
          </div>
        </section>

        <section class="filter-group filter-group-wide">
          <div class="section-header">
            <div>
              <h4>Dynamic comparisons</h4>
              <p class="muted section-copy">
                Add reusable conditions like <code>MA5 &gt; MA10</code> or <code>PE &lt; 20</code>.
              </p>
            </div>
            <button class="action-button compact" type="button" @click="addDynamicCondition">
              Add rule
            </button>
          </div>

          <div v-if="dynamicConditions.length === 0" class="state-card">
            No dynamic rules yet. Add one when you need cross-field comparisons.
          </div>

          <div v-else class="dynamic-list">
            <div v-for="item in dynamicConditions" :key="item.id" class="dynamic-row">
              <div class="dynamic-grid">
                <label class="field-block">
                  <span>Field A</span>
                  <select v-model="item.fieldA" class="field-input">
                    <option value="">Choose a field</option>
                    <option v-for="option in screenFieldOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label class="field-block">
                  <span>Operator</span>
                  <select v-model="item.operator" class="field-input">
                    <option value="">Choose</option>
                    <option v-for="operator in operatorOptions" :key="operator" :value="operator">
                      {{ operator }}
                    </option>
                  </select>
                </label>

                <label class="field-block">
                  <span>Mode</span>
                  <select v-model="item.compareMode" class="field-input" @change="resetDynamicConditionMode(item)">
                    <option v-for="option in compareModeOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label v-if="item.compareMode === 'field'" class="field-block">
                  <span>Field B</span>
                  <select v-model="item.fieldB" class="field-input">
                    <option value="">Choose a field</option>
                    <option v-for="option in screenFieldOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label v-else class="field-block">
                  <span>Fixed value</span>
                  <input
                    v-model="item.value"
                    class="field-input"
                    type="number"
                    step="0.01"
                    placeholder="Enter a numeric value"
                  />
                </label>

                <button class="action-button compact danger-button" type="button" @click="removeDynamicCondition(item.id)">
                  Remove
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="form-footer">
        <p class="muted result-copy">
          Submission keeps the legacy payload shape with <code>page=1</code>, <code>page_size={{ PAGE_SIZE }}</code>,
          and the existing <code>dynamic_conditions</code> array.
        </p>
        <div class="screen-action-bar">
          <button v-if="isAuthenticated" class="action-button primary" type="submit" :disabled="isSubmitting">
            <span v-if="isSubmitting" class="loading-ring" aria-hidden="true"></span>
            {{ isSubmitting ? 'Submitting...' : 'Submit screen' }}
          </button>
          <a v-else class="action-button primary link-button" :href="loginUrl">Sign in first</a>
          <button class="action-button ghost" type="button" @click="resetFilters">Reset form</button>
        </div>
      </div>
    </form>

    <article class="panel-card stack">
      <div class="section-header">
        <div>
          <p class="eyebrow">Results</p>
          <h3>Screened stocks</h3>
        </div>
        <span class="status-pill">{{ resultCountLabel }}</span>
      </div>

      <p class="muted result-copy">{{ resultSummary }}</p>

      <div v-if="isSubmitting" class="state-card loading-state">
        <span class="loading-ring" aria-hidden="true"></span>
        <span>Submitting to /api/analysis/screen...</span>
      </div>

      <div v-else-if="resultError" class="state-card state-error stack">
        <p>{{ resultError }}</p>
        <a v-if="!isAuthenticated" class="action-button primary link-button inline-action" :href="loginUrl">
          Go to sign in
        </a>
      </div>

      <div v-else-if="hasSubmitted && results.length === 0" class="state-card empty-state">
        No stocks matched the current filters. Try relaxing the valuation, technical, or dynamic rules.
      </div>

      <div v-else-if="results.length > 0" class="stack">
        <div v-if="resultHasMore" class="notice-banner notice-warning">
          More than {{ PAGE_SIZE }} rows matched. Only the first {{ PAGE_SIZE }} rows are shown.
        </div>

        <div class="table-shell">
          <table class="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Industry / Area</th>
                <th>Trade date</th>
                <th>Close</th>
                <th>PE</th>
                <th>PB</th>
                <th>Turnover</th>
                <th>Pct change</th>
                <th>Net inflow</th>
                <th>Total MV</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="stock in results" :key="stock.ts_code">
                <td>
                  <strong>{{ stock.ts_code }}</strong>
                </td>
                <td>
                  <div class="table-primary">{{ stock.name || '--' }}</div>
                  <div class="table-secondary">{{ stock.symbol || '--' }}</div>
                </td>
                <td>
                  <div>{{ stock.industry || '--' }}</div>
                  <div class="table-secondary">{{ stock.area || '--' }}</div>
                </td>
                <td>{{ normalizeDateInput(stock.trade_date || '') || '--' }}</td>
                <td>{{ formatNumber(stock.daily_close) }}</td>
                <td>{{ formatNumber(stock.pe) }}</td>
                <td>{{ formatNumber(stock.pb) }}</td>
                <td>{{ formatPercent(stock.turnover_rate) }}</td>
                <td :class="Number(stock.factor_pct_change || 0) >= 0 ? 'up' : 'down'">
                  {{ formatSignedPercent(stock.factor_pct_change) }}
                </td>
                <td :class="Number(stock.moneyflow_net_amount || 0) >= 0 ? 'up' : 'down'">
                  {{ formatMoneyWan(stock.moneyflow_net_amount) }}
                </td>
                <td>{{ formatMarketValue(stock.total_mv) }}</td>
                <td>
                  <div class="table-actions">
                    <RouterLink class="table-link" :to="`/stock/${stock.ts_code}`">Vue detail</RouterLink>
                    <a class="table-link subtle-link" :href="`/stock/${stock.ts_code}`" target="_blank" rel="noopener">
                      Legacy page
                    </a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="state-card empty-state">
        Configure the filters above and run the screen to view matching stocks.
      </div>
    </article>
  </section>
</template>

<style scoped>
.screen-page {
  gap: 1rem;
}

.screen-hero-grid,
.screen-stat-grid,
.filter-grid,
.range-grid {
  display: grid;
  gap: 1rem;
}

.screen-hero-grid {
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 1fr);
}

.screen-stat-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.screen-hero-card {
  gap: 1rem;
  display: flex;
  flex-direction: column;
}

.section-header,
.screen-action-bar,
.table-actions {
  display: flex;
  gap: 0.75rem;
}

.section-header {
  justify-content: space-between;
  align-items: flex-start;
}

.screen-action-bar {
  flex-wrap: wrap;
}

.form-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding-top: 0.25rem;
}

.section-copy,
.result-copy {
  margin: 0;
}

.stat-card {
  min-height: 132px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  justify-content: center;
}

.stat-card strong {
  font-size: 1.4rem;
}

.stat-label,
.field-block span,
.table-secondary {
  color: #64748b;
  font-size: 0.88rem;
}

.filter-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.filter-group {
  border-radius: 20px;
  border: 1px solid rgba(20, 32, 43, 0.08);
  background: rgba(248, 250, 252, 0.86);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.filter-group h4 {
  margin: 0;
}

.filter-group-wide {
  grid-column: 1 / -1;
}

.range-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field-help {
  color: #64748b;
  font-size: 0.82rem;
}

.field-input,
.action-button,
.table-link {
  border-radius: 16px;
  border: 1px solid rgba(20, 32, 43, 0.12);
}

.field-input {
  width: 100%;
  min-height: 44px;
  padding: 0.7rem 0.85rem;
  background: rgba(255, 255, 255, 0.94);
  color: #14202b;
}

.field-input:focus {
  outline: 2px solid rgba(24, 98, 76, 0.18);
  border-color: rgba(24, 98, 76, 0.35);
}

.action-button,
.table-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  min-height: 44px;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.84);
  color: #14202b;
  cursor: pointer;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
}

.action-button:hover,
.table-link:hover {
  transform: translateY(-1px);
  border-color: rgba(20, 32, 43, 0.2);
}

.action-button.primary {
  background: #18624c;
  border-color: #18624c;
  color: #fff;
}

.action-button.ghost {
  background: rgba(20, 32, 43, 0.05);
}

.action-button.compact {
  min-height: 40px;
  padding: 0.6rem 0.85rem;
}

.link-button {
  text-decoration: none;
}

.inline-action {
  align-self: flex-start;
}

.danger-button {
  background: rgba(220, 38, 38, 0.08);
  border-color: rgba(220, 38, 38, 0.16);
  color: #b91c1c;
}

.notice-banner {
  padding: 0.95rem 1rem;
  border-radius: 18px;
  font-weight: 600;
}

.notice-info {
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.notice-success {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
}

.notice-warning {
  background: rgba(245, 158, 11, 0.18);
  color: #92400e;
}

.notice-error,
.state-error {
  background: rgba(220, 38, 38, 0.12);
  color: #991b1b;
}

.state-card {
  border-radius: 18px;
  border: 1px solid rgba(20, 32, 43, 0.08);
  background: rgba(248, 250, 252, 0.9);
  color: #475569;
  padding: 1rem;
}

.loading-state,
.empty-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dynamic-list {
  display: grid;
  gap: 0.85rem;
}

.dynamic-row {
  border-radius: 18px;
  border: 1px dashed rgba(20, 32, 43, 0.16);
  background: rgba(255, 255, 255, 0.8);
  padding: 0.95rem;
}

.dynamic-grid {
  display: grid;
  grid-template-columns: 1.35fr 0.8fr 0.9fr 1.35fr auto;
  gap: 0.75rem;
  align-items: end;
}

.table-shell {
  overflow: auto;
  border-radius: 18px;
  border: 1px solid rgba(20, 32, 43, 0.08);
  background: rgba(255, 255, 255, 0.8);
}

.data-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 0.85rem 0.95rem;
  border-bottom: 1px solid rgba(20, 32, 43, 0.07);
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}

.data-table thead th {
  position: sticky;
  top: 0;
  background: rgba(248, 250, 252, 0.96);
  color: #475569;
  font-size: 0.82rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.table-primary {
  font-weight: 700;
}

.table-actions {
  flex-wrap: wrap;
}

.table-link {
  min-height: 36px;
  padding: 0.45rem 0.7rem;
  font-size: 0.88rem;
  text-decoration: none;
}

.subtle-link {
  background: rgba(20, 32, 43, 0.04);
}

.up {
  color: #dc2626;
}

.down {
  color: #15803d;
}

.loading-ring {
  width: 0.95rem;
  height: 0.95rem;
  border-radius: 999px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  animation: screen-spin 0.9s linear infinite;
}

@keyframes screen-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .screen-hero-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .screen-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-group-wide {
    grid-column: auto;
  }

  .dynamic-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .screen-stat-grid,
  .range-grid,
  .dynamic-grid {
    grid-template-columns: 1fr;
  }

  .section-header,
  .screen-action-bar,
  .table-actions,
  .form-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .action-button,
  .table-link {
    width: 100%;
  }

  .loading-state,
  .empty-state {
    align-items: flex-start;
  }
}
</style>
