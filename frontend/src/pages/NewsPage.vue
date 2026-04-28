<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useToast } from '../composables/useToast';
import { debounce } from '../lib/format';
import { getNews, type NewsItem } from '../modules/news/api';

const toast = useToast();

const sources = [
  { key: '', label: '全部' },
  { key: 'cjzc', label: '财经早餐' },
  { key: 'global', label: '全球快讯' },
  { key: 'cls', label: '财联社' },
  { key: 'ths', label: '同花顺' },
];

const activeSource = ref('');
const news = ref<NewsItem[]>([]);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const pageSize = 30;
const hasMore = ref(false);
const searchQuery = ref('');

onMounted(() => loadNews());

async function loadNews(append = false) {
  loading.value = true; error.value = '';
  try {
    const res = await getNews(activeSource.value || undefined);
    const items = res.data || [];
    if (append) news.value = [...news.value, ...items];
    else news.value = items;
    hasMore.value = items.length >= pageSize;
  } catch {
    error.value = '加载失败';
    toast.error('新闻加载失败');
  }
  loading.value = false;
}

function switchSource(key: string) {
  activeSource.value = key;
  page.value = 1;
  news.value = [];
  loadNews();
}

function loadMore() { page.value++; loadNews(true); }

const filteredNews = computed(() => {
  if (!searchQuery.value) return news.value;
  const q = searchQuery.value.toLowerCase();
  return news.value.filter((n) =>
    n.title?.toLowerCase().includes(q) ||
    n.summary?.toLowerCase().includes(q) ||
    n.source?.toLowerCase().includes(q)
  );
});

const sourceColors: Record<string, string> = {
  eastmoney: '#e15241', cls: '#1a73e8', ths: '#f2994a', cjzc: '#00b894', global: '#6c5ce7',
};

function formatTime(time: string) {
  if (!time) return '';
  if (time.includes('T')) return time.replace('T', ' ').slice(0, 16);
  return time;
}
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="card mb-3">
      <div class="card-body">
        <div class="flex-between" style="flex-wrap:wrap;gap:.75rem;">
          <div class="tab-bar">
            <button v-for="s in sources" :key="s.key" class="tab-btn" :class="{ active: activeSource === s.key }" @click="switchSource(s.key)">{{ s.label }}</button>
          </div>
          <div class="flex-between gap-2">
            <input v-model="searchQuery" class="form-input" placeholder="搜索新闻..." style="width:200px;" />
            <button class="btn btn-sm btn-ghost" @click="loadNews()">刷新</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !news.length">
      <div v-for="i in 5" :key="i" class="skeleton" style="height:80px;margin-bottom:12px;border-radius:var(--radius-lg);" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="alert alert-error">
      <span>{{ error }}</span>
      <button class="btn btn-sm btn-outline" @click="loadNews()">重试</button>
    </div>

    <!-- News Feed -->
    <div v-else class="news-feed">
      <div v-for="(n, i) in filteredNews" :key="i" class="card news-card">
        <div class="news-card-inner">
          <div class="flex-between mb-2">
            <span class="badge" :style="{ background: (sourceColors[n.source] || '#9aa0a6') + '18', color: sourceColors[n.source] || '#5f6368' }">{{ n.source || '资讯' }}</span>
            <span class="text-xs text-muted">{{ formatTime(n.time) }}</span>
          </div>
          <a :href="n.url" target="_blank" class="news-link">{{ n.title }}</a>
          <p v-if="n.summary" class="text-sm text-muted mt-2">{{ n.summary }}</p>
        </div>
      </div>

      <div v-if="!filteredNews.length && !loading" class="empty-state">
        <div class="empty-icon">📰</div>
        <h4>{{ searchQuery ? '未找到匹配新闻' : '暂无新闻' }}</h4>
      </div>

      <button v-if="hasMore && !searchQuery" class="btn btn-outline w-full mt-2" @click="loadMore" :disabled="loading">
        {{ loading ? '加载中...' : '加载更多' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.news-feed { display: flex; flex-direction: column; gap: .75rem; }
.news-card { transition: all var(--transition); }
.news-card:hover { border-color: var(--color-primary); box-shadow: var(--shadow-md); }
.news-card-inner { padding: 1rem 1.25rem; }
.news-link {
  font-size: .95rem; font-weight: 700; color: var(--color-text);
  line-height: 1.5; display: block;
}
.news-link:hover { color: var(--color-primary); }
</style>
