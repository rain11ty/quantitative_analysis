import { createRouter, createWebHistory } from 'vue-router';

import HomePage from '../pages/HomePage.vue';
import MigrationPage from '../pages/MigrationPage.vue';
import NotFoundPage from '../pages/NotFoundPage.vue';
import ScreenPage from '../pages/ScreenPage.vue';
import StockDetailPage from '../pages/StockDetailPage.vue';

const routes = [
  {
    path: '/',
    name: 'overview',
    component: HomePage,
    meta: {
      title: 'Overview',
    },
  },
  {
    path: '/stocks',
    name: 'stocks',
    component: MigrationPage,
    meta: {
      title: 'Stocks',
      summary: 'List page scaffold for stock search, filters, and market snapshots.',
      legacyTemplate: 'app/templates/stocks.html',
      apiGroups: ['/api/stocks', '/api/industries', '/api/areas', '/api/market/overview'],
      priority: 'Phase 2',
    },
  },
  {
    path: '/stock/:tsCode',
    name: 'stock-detail',
    component: StockDetailPage,
    meta: {
      title: 'Stock Detail',
      summary: 'Primary candidate for component extraction, chart lifecycle cleanup, and watchlist UX.',
      legacyTemplate: 'app/templates/stock_detail.html',
      apiGroups: [
        '/api/stocks/:tsCode',
        '/api/stocks/:tsCode/realtime',
        '/api/stocks/:tsCode/history',
        '/api/stocks/:tsCode/factors',
        '/api/stocks/:tsCode/moneyflow',
        '/api/stocks/:tsCode/cyq',
        '/api/watchlist/:tsCode',
      ],
      priority: 'Phase 1',
    },
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: MigrationPage,
    meta: {
      title: 'Realtime Monitor',
      summary: 'Best place to standardize polling, auto-refresh cleanup, and dashboard widgets.',
      legacyTemplate: 'app/templates/realtime_monitor.html',
      apiGroups: [
        '/api/monitor/dashboard',
        '/api/monitor/ranking',
        '/api/monitor/stocks/:tsCode',
        '/api/monitor/intraday/:tsCode',
        '/api/monitor/shock',
      ],
      priority: 'Phase 1',
    },
  },
  {
    path: '/ai-assistant',
    name: 'ai-assistant',
    component: MigrationPage,
    meta: {
      title: 'AI Assistant',
      summary: 'Conversation state, streaming responses, and history management belong in dedicated Vue modules.',
      legacyTemplate: 'app/templates/ai_assistant.html',
      apiGroups: [
        '/api/ai/conversations',
        '/api/ai/conversations/:id/messages',
        '/api/ai/chat',
        '/api/ai/status',
      ],
      priority: 'Phase 1',
    },
  },
  {
    path: '/screen',
    name: 'screen',
    component: ScreenPage,
    meta: {
      title: 'Screen',
      summary: 'Multi-factor stock screening with dynamic field comparisons, login-aware guidance, and result tables.',
      legacyTemplate: 'app/templates/screen.html',
      apiGroups: [
        '/api/industries',
        '/api/areas',
        '/api/market/health',
        '/api/analysis/screen',
      ],
      priority: 'Phase 2',
    },
  },
  {
    path: '/backtest',
    name: 'backtest',
    component: MigrationPage,
    meta: {
      title: 'Backtest',
      summary: 'Strategy forms, result tables, and chart panels should reuse the same Vue data patterns.',
      legacyTemplate: 'app/templates/backtest.html',
      apiGroups: ['/api/analysis/backtest', '/api/user/backtests'],
      priority: 'Phase 2',
    },
  },
  {
    path: '/news',
    name: 'news',
    component: MigrationPage,
    meta: {
      title: 'News',
      summary: 'Lower-risk route for finishing the migration after core trading workflows are stable.',
      legacyTemplate: 'app/templates/news.html',
      apiGroups: ['/api/news', '/api/news/cjzc', '/api/news/global'],
      priority: 'Phase 3',
    },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundPage,
    meta: {
      title: 'Not Found',
    },
  },
] as const;

const router = createRouter({
  history: createWebHistory('/app'),
  routes,
});

export default router;
