<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from '../composables/useToast';
import { getIndustries, getAreas, getStockList } from '../modules/stocks/api';
import { debounce } from '../lib/format';

const router = useRouter();
const toast = useToast();

const industries = ref<string[]>([]);
const areas = ref<string[]>([]);
const stocks = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(true);
const error = ref('');

const filterIndustry = ref('');
const filterArea = ref('');
const searchKeyword = ref('');
const sortField = ref('');
const sortDir = ref<'asc' | 'desc'>('asc');

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const sortedStocks = computed(() => {
  if (!sortField.value) return stocks.value;
  return [...stocks.value].sort((a, b) => {
    const va = a[sortField.value] ?? '';
    const vb = b[sortField.value] ?? '';
    const cmp = String(va).localeCompare(String(vb), 'zh-CN', { numeric: true });
    return sortDir.value === 'asc' ? cmp : -cmp;
  });
});

onMounted(async () => {
  try {
    const [ind, ar] = await Promise.all([getIndustries(), getAreas()]);
    industries.value = (ind.data || []).map((i: { industry: string }) => i.industry).filter(Boolean);
    areas.value = (ar.data || []).map((a: { area: string }) => a.area).filter(Boolean);
  } catch { /* */ }
  loadStocks();
});

async function loadStocks() {
  loading.value = true; error.value = '';
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize };
    if (filterIndustry.value) params.industry = filterIndustry.value;
    if (filterArea.value) params.area = filterArea.value;
    if (searchKeyword.value) params.search = searchKeyword.value;
    const res = await getStockList(params);
    stocks.value = res.data || [];
    total.value = res.total || 0;
  } catch { error.value = '加载失败'; toast.error('股票列表加载失败'); }
  loading.value = false;
}

function applyFilters() { page.value = 1; loadStocks(); }
function resetFilters() { filterIndustry.value = ''; filterArea.value = ''; searchKeyword.value = ''; sortField.value = ''; page.value = 1; loadStocks(); }
function goPage(p: number) { page.value = p; loadStocks(); }
function toggleSort(field: string) {
  sortDir.value = sortField.value === field ? (sortDir.value === 'asc' ? 'desc' : 'asc') : 'asc';
  sortField.value = field;
}
const sortArrow = (f: string) => sortField.value === f ? (sortDir.value === 'asc' ? '↑' : '↓') : '';

watch(searchKeyword, debounce(() => applyFilters(), 300));
</script>

<template>
  <div>
    <div class="card">
      <div class="form-grid" style="margin-bottom:12px;">
        <div class="form-group">
          <label class="form-label">行业</label>
          <select v-model="filterIndustry" class="form-select" @change="applyFilters">
            <option value="">全部</option>
            <option v-for="ind in industries" :key="ind" :value="ind">{{ ind }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">地域</label>
          <select v-model="filterArea" class="form-select" @change="applyFilters">
            <option value="">全部</option>
            <option v-for="a in areas" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">搜索</label>
          <input v-model="searchKeyword" class="form-input" placeholder="代码/名称/拼音" />
        </div>
      </div>
      <div class="flex-between">
        <span class="text-sm text-muted">{{ total }} 只股票</span>
        <div class="flex-between gap-2">
          <button class="btn btn-ghost btn-sm" @click="resetFilters">重置</button>
          <button class="btn btn-primary btn-sm" @click="applyFilters">筛选</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="card"><div v-for="i in 4" :key="i" class="skeleton" style="height:36px;margin-bottom:8px;" /></div>
    <div v-else-if="error" class="alert alert-error">{{ error }} <button class="btn btn-ghost btn-sm" @click="loadStocks">重试</button></div>

    <div v-else class="card" style="padding:0;overflow-x:auto;">
      <table class="data-table w-full">
        <thead>
          <tr>
            <th @click="toggleSort('ts_code')" style="cursor:pointer;">代码 {{ sortArrow('ts_code') }}</th>
            <th @click="toggleSort('name')" style="cursor:pointer;">名称 {{ sortArrow('name') }}</th>
            <th @click="toggleSort('industry')" style="cursor:pointer;">行业 {{ sortArrow('industry') }}</th>
            <th @click="toggleSort('area')" style="cursor:pointer;">地域 {{ sortArrow('area') }}</th>
            <th @click="toggleSort('list_date')" style="cursor:pointer;">上市日 {{ sortArrow('list_date') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sortedStocks" :key="s.ts_code as string">
            <td class="font-mono">{{ s.symbol || s.ts_code }}</td>
            <td class="font-bold">{{ s.name }}</td>
            <td>{{ s.industry }}</td>
            <td>{{ s.area }}</td>
            <td>{{ s.list_date }}</td>
            <td><button class="btn btn-primary btn-sm" @click="router.push('/stock/' + s.ts_code)">详情</button></td>
          </tr>
          <tr v-if="!sortedStocks.length"><td colspan="6" style="text-align:center;padding:32px;color:var(--text-tertiary);">没有匹配的股票</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="totalPages > 1" class="flex-center gap-2">
      <button class="btn btn-ghost btn-sm" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <button v-for="p in Math.min(totalPages, 7)" :key="p" class="btn btn-sm" :class="page === p ? 'btn-primary' : 'btn-ghost'" @click="goPage(p)">{{ p }}</button>
      <button class="btn btn-ghost btn-sm" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>
