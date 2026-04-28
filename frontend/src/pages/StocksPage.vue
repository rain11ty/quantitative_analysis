<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from '../composables/useToast';
import { getIndustries, getAreas, getStockList } from '../modules/stocks/api';
import { formatNumber } from '../lib/format';
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
const visiblePages = computed(() => {
  const tp = totalPages.value;
  const current = page.value;
  const pages: number[] = [];
  let start = Math.max(1, current - 4);
  let end = Math.min(tp, start + 9);
  if (end - start < 9) start = Math.max(1, end - 9);
  for (let i = start; i <= end; i++) pages.push(i);
  return pages;
});

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
  } catch { /* non-critical */ }
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
  } catch {
    error.value = '加载失败';
    toast.error('股票列表加载失败');
  }
  loading.value = false;
}

function applyFilters() { page.value = 1; loadStocks(); }
function resetFilters() {
  filterIndustry.value = ''; filterArea.value = ''; searchKeyword.value = '';
  sortField.value = ''; sortDir.value = 'asc';
  page.value = 1; loadStocks();
}
function goPage(p: number) { page.value = p; loadStocks(); }
function toggleSort(field: string) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortField.value = field;
    sortDir.value = 'asc';
  }
}

const sortIndicator = (field: string) => {
  if (sortField.value !== field) return '';
  return sortDir.value === 'asc' ? ' ▲' : ' ▼';
};

watch(searchKeyword, debounce(() => applyFilters(), 300));
</script>

<template>
  <div>
    <!-- Filter Bar -->
    <div class="card mb-3">
      <div class="card-body">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">行业</label>
            <select v-model="filterIndustry" class="form-select" @change="applyFilters">
              <option value="">全部行业</option>
              <option v-for="ind in industries" :key="ind" :value="ind">{{ ind }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">地域</label>
            <select v-model="filterArea" class="form-select" @change="applyFilters">
              <option value="">全部地域</option>
              <option v-for="a in areas" :key="a" :value="a">{{ a }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">搜索</label>
            <input v-model="searchKeyword" class="form-input" placeholder="股票代码/名称/拼音" />
          </div>
        </div>
        <div class="flex-between mt-3">
          <span class="text-sm text-muted">共 {{ total }} 只股票</span>
          <div class="flex-between gap-2">
            <button class="btn btn-ghost btn-sm" @click="resetFilters">重置</button>
            <button class="btn btn-primary btn-sm" @click="applyFilters">筛选</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card">
      <div class="card-body">
        <div v-for="i in 5" :key="i" class="skeleton" style="height:40px;margin-bottom:8px;" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="alert alert-error">
      <span>{{ error }}</span>
      <button class="btn btn-sm btn-outline" @click="loadStocks">重试</button>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <div class="card-body" style="overflow-x:auto;padding:0;">
        <table class="data-table w-full">
          <thead>
            <tr>
              <th class="sortable" @click="toggleSort('ts_code')">代码{{ sortIndicator('ts_code') }}</th>
              <th class="sortable" @click="toggleSort('name')">名称{{ sortIndicator('name') }}</th>
              <th class="sortable" @click="toggleSort('industry')">行业{{ sortIndicator('industry') }}</th>
              <th class="sortable" @click="toggleSort('area')">地域{{ sortIndicator('area') }}</th>
              <th class="sortable" @click="toggleSort('list_date')">上市日期{{ sortIndicator('list_date') }}</th>
              <th>操作</th>
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
            <tr v-if="!sortedStocks.length">
              <td colspan="6" style="text-align:center;padding:2rem;color:var(--color-text-muted);">没有匹配的股票</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex-center gap-2 mt-3">
      <button class="btn btn-sm btn-ghost" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <button
        v-for="p in visiblePages" :key="p"
        class="btn btn-sm" :class="page === p ? 'btn-primary' : 'btn-ghost'"
        @click="goPage(p)"
      >{{ p }}</button>
      <button class="btn btn-sm btn-ghost" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--color-primary); }
</style>
