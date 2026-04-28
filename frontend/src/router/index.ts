import { createRouter, createWebHistory } from 'vue-router';

import HomePage from '../pages/HomePage.vue';
import MigrationPage from '../pages/MigrationPage.vue';
import NotFoundPage from '../pages/NotFoundPage.vue';
import ScreenPage from '../pages/ScreenPage.vue';
import StockDetailPage from '../pages/StockDetailPage.vue';
import StocksPage from '../pages/StocksPage.vue';
import NewsPage from '../pages/NewsPage.vue';
import BacktestPage from '../pages/BacktestPage.vue';
import MonitorPage from '../pages/MonitorPage.vue';
import AIAssistantPage from '../pages/AIAssistantPage.vue';

const routes = [
  {
    path: '/',
    name: 'overview',
    component: HomePage,
    meta: { title: '市场概览', legacyPath: '/' },
  },
  {
    path: '/stocks',
    name: 'stocks',
    component: StocksPage,
    meta: { title: '股票列表', legacyPath: '/stocks' },
  },
  {
    path: '/stock/:tsCode',
    name: 'stock-detail',
    component: StockDetailPage,
    meta: {
      title: '股票详情',
      legacyPath: '/stock/:ts_code',
      legacyTemplate: 'app/templates/stock_detail.html',
      requiresAuth: true,
      priority: 'Phase 1',
    },
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: MonitorPage,
    meta: { title: '实时监控', legacyPath: '/monitor' },
  },
  {
    path: '/ai-assistant',
    name: 'ai-assistant',
    component: AIAssistantPage,
    meta: { title: 'AI 助手', legacyPath: '/ai-assistant', requiresAuth: true },
  },
  {
    path: '/screen',
    name: 'screen',
    component: ScreenPage,
    meta: {
      title: '条件选股',
      legacyPath: '/screen',
      legacyTemplate: 'app/templates/screen.html',
      priority: 'Phase 2',
    },
  },
  {
    path: '/backtest',
    name: 'backtest',
    component: BacktestPage,
    meta: { title: '策略回测', legacyPath: '/backtest', requiresAuth: true },
  },
  {
    path: '/news',
    name: 'news',
    component: NewsPage,
    meta: { title: '新闻资讯', legacyPath: '/news' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundPage,
    meta: { title: '页面未找到' },
  },
];

const router = createRouter({
  history: createWebHistory('/app'),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach((to, _from) => {
  const ctx = window.__QUANT_APP_CONTEXT__;
  const isAuth = ctx?.auth?.isAuthenticated ?? false;

  if (to.meta.requiresAuth && !isAuth) {
    const loginPath = '/auth/login';
    const next = to.fullPath;
    return { path: loginPath, query: { next } };
  }

  if (to.meta.title && typeof to.meta.title === 'string') {
    document.title = `${to.meta.title} - 量化分析系统`;
  }
});

export default router;
