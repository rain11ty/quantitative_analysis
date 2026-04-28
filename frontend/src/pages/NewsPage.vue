<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useToast } from '../composables/useToast';
import { getNews, type NewsItem } from '../modules/news/api';

const toast = useToast();
const activeSource = ref('');
const news = ref<NewsItem[]>([]);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const hasMore = ref(false);
const searchQuery = ref('');

const sources = [
  { key: '', label: '全部' },
  { key: 'cjzc', label: '财经早餐' },
  { key: 'global', label: '全球快讯' },
  { key: 'cls', label: '财联社' },
  { key: 'ths', label: '同花顺' },
];

onMounted(() => loadNews());

async function loadNews(append = false) {
  loading.value = true; error.value = '';
  try {
    const res = await getNews(activeSource.value || undefined);
    const items = res.data || [];
    news.value = append ? [...news.value, ...items] : items;
    hasMore.value = items.length >= 30;
  } catch { error.value = '加载失败'; toast.error('新闻加载失败'); }
  loading.value = false;
}

function switchSource(key: string) { activeSource.value = key; page.value = 1; news.value = []; loadNews(); }

const filteredNews = computed(() => {
  if (!searchQuery.value) return news.value;
  const q = searchQuery.value.toLowerCase();
  return news.value.filter(n => n.title?.toLowerCase().includes(q) || n.summary?.toLowerCase().includes(q));
});

const sourceColor = (s: string) => ({ eastmoney: '#ff3b30', cls: '#0052ff', ths: '#ff9f0a', cjzc: '#34c759', global: '#af52de' }[s] || '#86868b');
</script>

<template>
  <div>
    <div class="card">
      <div class="flex-between" style="flex-wrap:wrap;gap:12px;">
        <div class="tab-bar">
          <button v-for="s in sources" :key="s.key" class="tab-btn" :class="{ active: activeSource === s.key }" @click="switchSource(s.key)">{{ s.label }}</button>
        </div>
        <div class="flex-between gap-2">
          <input v-model="searchQuery" class="form-input text-xs" placeholder="搜索..." style="width:160px;" />
          <button class="btn btn-ghost btn-sm" @click="loadNews()">刷新</button>
        </div>
      </div>
    </div>

    <div v-if="loading && !news.length">
      <div v-for="i in 4" :key="i" class="skeleton" style="height:72px;margin-bottom:12px;border-radius:var(--radius-lg);" />
    </div>
    <div v-else-if="error" class="alert alert-error">{{ error }} <button class="btn btn-ghost btn-sm" @click="loadNews()">重试</button></div>

    <div v-else style="display:flex;flex-direction:column;gap:12px;">
      <div v-for="(n, i) in filteredNews" :key="i" class="card" style="padding:16px 20px;">
        <div class="flex-between mb-1">
          <span class="badge" :style="{ background: sourceColor(n.source) + '14', color: sourceColor(n.source) }">{{ n.source || '资讯' }}</span>
          <span class="text-xs text-muted">{{ n.time?.includes('T') ? n.time.replace('T',' ').slice(0,16) : n.time }}</span>
        </div>
        <a :href="n.url" target="_blank" style="font-size:15px;font-weight:600;color:var(--text-primary);line-height:1.4;">{{ n.title }}</a>
        <p v-if="n.summary" class="text-sm text-muted mt-1">{{ n.summary }}</p>
      </div>
      <div v-if="!filteredNews.length && !loading" class="empty-state"><h4>{{ searchQuery ? '未找到' : '暂无新闻' }}</h4></div>
      <button v-if="hasMore && !searchQuery" class="btn btn-secondary w-full" @click="loadNews(true)">加载更多</button>
    </div>
  </div>
</template>
