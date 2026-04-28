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
const sidebarOpen = ref(false);

const pageTitle = computed(() => {
  const t = route.meta.title;
  return typeof t === 'string' ? t : '量化分析系统';
});

const navItems = [
  { to: '/', label: '市场概览', icon: '📊' },
  { to: '/stocks', label: '股票列表', icon: '📋' },
  { to: '/monitor', label: '实时监控', icon: '📡' },
  { to: '/screen', label: '条件选股', icon: '🔍' },
  { to: '/backtest', label: '策略回测', icon: '⚡' },
  { to: '/news', label: '新闻资讯', icon: '📰' },
  { to: '/ai-assistant', label: 'AI 助手', icon: '🤖' },
];

const userInitial = computed(() => {
  const name = auth?.displayName || 'U';
  return name.charAt(0).toUpperCase();
});

function closeSidebar() {
  sidebarOpen.value = false;
}
</script>

<template>
  <div class="app-layout">
    <!-- Offline Banner -->
    <div v-if="!online" class="offline-banner">
      <span>网络已断开，部分功能不可用</span>
    </div>

    <!-- Mobile overlay -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="closeSidebar" />

    <!-- Sidebar -->
    <aside class="sidebar" :class="{ 'sidebar-open': sidebarOpen }">
      <div class="sidebar-brand">
        <div class="logo-icon">📈</div>
        <h1>A股量化分析</h1>
        <p class="subtitle">Quantitative Analysis</p>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          active-class="active"
          :exact="item.to === '/'"
          @click="closeSidebar"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div v-if="auth?.isAuthenticated" class="user-row">
          <span class="avatar">{{ userInitial }}</span>
          <div>
            <div class="user-name">{{ auth.displayName }}</div>
            <div class="user-role">{{ auth.isAdmin ? '管理员' : '用户' }}</div>
          </div>
        </div>
        <div v-else class="guest-links">
          <a href="/auth/login">登录</a>
          &nbsp;·&nbsp;
          <a href="/auth/register">注册</a>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <main class="main-content">
      <header class="page-header-bar">
        <div class="header-left">
          <button class="hamburger" aria-label="菜单" @click="sidebarOpen = !sidebarOpen">
            <span />
            <span />
            <span />
          </button>
          <h2>{{ pageTitle }}</h2>
        </div>
        <div class="header-right">
          <span v-if="auth?.isAuthenticated" class="badge badge-info">
            {{ auth.isAdmin ? '管理员' : '已登录' }}
          </span>
          <a v-else href="/auth/login" class="btn btn-primary btn-sm">登录</a>
        </div>
      </header>

      <div class="page-body">
        <ErrorBoundary>
          <RouterView />
        </ErrorBoundary>
      </div>
    </main>

    <ToastContainer />
  </div>
</template>

<style scoped>
/* Offline banner */
.offline-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 200;
  background: #f2994a;
  color: #fff;
  text-align: center;
  padding: 6px;
  font-size: .82rem;
  font-weight: 600;
}

/* Hamburger */
.hamburger {
  display: none;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  width: 34px;
  height: 34px;
  justify-content: center;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: background var(--transition);
}
.hamburger:hover { background: var(--color-surface-hover); }
.hamburger span {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--color-text);
  border-radius: 1px;
  transition: all var(--transition);
}

.header-left {
  display: flex;
  align-items: center;
  gap: .75rem;
}

.header-right {
  display: flex;
  align-items: center;
}

/* Sidebar overlay */
.sidebar-overlay {
  display: none;
}

/* Guest links */
.guest-links { font-size: .75rem; }
.guest-links a { color: #9ca3af; }
.guest-links a:hover { color: #fff; }

.user-name { color: #e8eaed; font-weight: 600; font-size: .82rem; }
.user-role { color: #6b7280; font-size: .72rem; }

@media (max-width: 768px) {
  .hamburger { display: flex; }

  .sidebar {
    transform: translateX(-100%);
  }
  .sidebar.sidebar-open {
    transform: translateX(0);
    box-shadow: var(--shadow-lg);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 99;
    background: rgba(0, 0, 0, .35);
  }

  .main-content { margin-left: 0 !important; }
}
</style>
