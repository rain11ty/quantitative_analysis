<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';
import ToastContainer from './components/ToastContainer.vue';
import ErrorBoundary from './components/ErrorBoundary.vue';
import { useOnline } from './composables/useOnline';

const route = useRoute();
const ctx = window.__QUANT_APP_CONTEXT__;
const auth = ctx?.auth;
const { online } = useOnline();
const mobileOpen = ref(false);

const pageTitle = computed(() => {
  const t = route.meta.title;
  return typeof t === 'string' ? t : '量化分析';
});

const navItems = [
  { to: '/', label: '概览', exact: true },
  { to: '/stocks', label: '股票' },
  { to: '/monitor', label: '监控' },
  { to: '/screen', label: '选股' },
  { to: '/backtest', label: '回测' },
  { to: '/news', label: '资讯' },
  { to: '/ai-assistant', label: 'AI' },
];

const userLabel = computed(() => {
  if (!auth?.isAuthenticated) return null;
  return auth.displayName || '用户';
});

function closeMobile() { mobileOpen.value = false; }
</script>

<template>
  <div>
    <!-- Offline -->
    <div v-if="!online" class="offline-banner">网络已断开</div>

    <!-- Navigation Bar -->
    <nav class="nav-bar">
      <div class="nav-inner">
        <RouterLink to="/" class="nav-brand" @click="closeMobile">
          <span style="font-size:18px;">&#63743;</span>
          Quant
        </RouterLink>

        <div class="nav-links">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            active-class="active"
            :exact="item.exact"
          >{{ item.label }}</RouterLink>
        </div>

        <div class="nav-user">
          <template v-if="userLabel">
            <span>{{ userLabel }}</span>
            <span v-if="auth?.isAdmin" class="badge badge-info">管理</span>
          </template>
          <template v-else>
            <a href="/auth/login">登录</a>
            <a href="/auth/register">注册</a>
          </template>
        </div>

        <button class="nav-hamburger" aria-label="菜单" @click="mobileOpen = !mobileOpen">
          <span /><span /><span />
        </button>
      </div>
    </nav>

    <!-- Mobile Menu -->
    <div class="mobile-menu-overlay" :class="{ open: mobileOpen }" @click="closeMobile" />
    <div class="mobile-menu" :class="{ open: mobileOpen }">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-link"
        active-class="active"
        :exact="item.exact"
        @click="closeMobile"
      >{{ item.label }}</RouterLink>
    </div>

    <!-- Page Content -->
    <div class="page-wrap">
      <ErrorBoundary>
        <RouterView />
      </ErrorBoundary>
    </div>

    <ToastContainer />
  </div>
</template>
