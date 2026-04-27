<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

const route = useRoute();

const pageTitle = computed(() => {
  const title = route.meta.title;
  return typeof title === 'string' ? title : 'Vue Migration';
});

const navItems = [
  { to: '/', label: 'Overview' },
  { to: '/stocks', label: 'Stocks' },
  { to: '/monitor', label: 'Monitor' },
  { to: '/ai-assistant', label: 'AI Assistant' },
  { to: '/screen', label: 'Screen' },
  { to: '/backtest', label: 'Backtest' },
  { to: '/news', label: 'News' },
];
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-card">
        <p class="eyebrow">Quantitative Analysis</p>
        <h1>Vue Frontend</h1>
        <p class="support-copy">
          Safe migration workspace for same-origin Vue + Flask delivery.
        </p>
      </div>

      <nav class="nav-list" aria-label="Primary">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="status-card">
        <span class="status-pill">Legacy pages untouched</span>
        <p>
          This shell is intentionally isolated so the existing Flask templates
          remain the source of truth until each Vue page passes review.
        </p>
      </div>
    </aside>

    <main class="content">
      <header class="page-header">
        <p class="eyebrow">Parallel rollout</p>
        <div class="page-header-row">
          <h2>{{ pageTitle }}</h2>
          <span class="route-chip">/app{{ route.fullPath === '/' ? '' : route.fullPath }}</span>
        </div>
      </header>

      <RouterView />
    </main>
  </div>
</template>
