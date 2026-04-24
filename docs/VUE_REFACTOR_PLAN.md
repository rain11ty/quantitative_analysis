# Vue 前端重构计划 —— 股票量化分析系统

> **项目路径**: `quantitative_analysis-vue/`
> **原项目备份**: `quantitative_analysis/` (已 Git 提交，commit `9108978c`)
> **重构目标**: Flask 后端不变 + Jinja2 模板替换为 Vue3 SPA 前端

---

## 一、总体架构图

```
【重构前】                                    【重构后】
                                                     
浏览器                                        浏览器
  │                                            │
  ▼                                            ▼
Flask (Jinja2渲染HTML)                       Nginx
  ├── /stock/* → render_template()   →         │
  ├── /analysis → render_template()            ├── / → dist/index.html (Vue SPA)
  ├── /auth/* → render_template()             ├── /api/* → proxy_pass Flask:5000
  ├── /admin/* → render_template()             └── /auth/* → proxy_pass Flask:5000
  └── /api/* → return JSON (已有)                    │
                                                    ▼
                                              Flask (纯API服务)
                                                └── 只保留 /api/* + /auth/*
```

---

## 二、目录结构规划

```
quantitative_analysis-vue/
├── frontend/                              ← 【新建】Vue3 前端项目
│   ├── index.html                         ← 入口 HTML（空壳）
│   ├── package.json                       ← 依赖声明
│   ├── vite.config.ts                     ← Vite 构建配置（代理Flask）
│   ├── tsconfig.json                      ← TypeScript 配置
│   ├── env.d.ts                           ← Vite 类型声明
│   └── src/
│       ├── main.ts                        ← 应用入口：创建Vue实例、挂载插件
│       ├── App.vue                         ← 根组件：router-view 容器
│       │
│       ├── api/                           ← API 接口层（对应 Flask /api/*）
│       │   ├── request.ts                 ← Axios 封装（拦截器、错误处理）
│       │   ├── stock.ts                   ← 股票相关接口（9个）
│       │   ├── analysis.ts                ← 分析/回测接口（4个）
│       │   ├── auth.ts                    ← 认证接口（5个）
│       │   ├── monitor.ts                 ← 监控接口（2个）
│       │   ├── ai.ts                      ← AI助手接口（1个SSE）
│       │   └── admin.ts                   ← 管理端接口（6个）
│       │
│       ├── views/                         ← 页面视图（对应原22个HTML）
│       │   ├── stock/
│       │   │   ├── StockDetail.vue        ← stock_detail.html（核心页）
│       │   │   └── StockList.vue          ← stocks.html
│       │   ├── analysis/
│       │   │   └── AnalysisPage.vue       ← analysis.html
│       │   ├── backtest/
│       │   │   └── BacktestPage.vue       ← backtest.html
│       │   ├── screen/
│       │   │   └── ScreenPage.vue         ← screen.html
│       │   ├── monitor/
│       │   │   └── MonitorPage.vue        ← realtime_monitor.html
│       │   ├── ai/
│       │   │   └── AiAssistantPage.vue    ← ai_assistant.html
│       │   ├── dashboard/
│       │   │   └── DashboardPage.vue      ← index.html 首页
│       │   ├── auth/
│       │   │   ├── LoginView.vue          ← auth/login.html
│       │   │   ├── RegisterView.vue       ← auth/register.html
│       │   │   ├── ForgotPassword.vue     ← auth/forgot_password.html
│       │   │   └── ProfileView.vue        ← auth/profile.html
│       │   ├── admin/
│       │   │   ├── AdminDashboard.vue     ← admin/dashboard.html
│       │   │   ├── AdminUsers.vue         ← admin/users.html
│       │   │   ├── AdminData.vue          ← admin/data.html
│       │   │   ├── AdminLogs.vue          ← admin/logs.html
│       │   │   └── AdminUserDetail.vue    ← admin/user_detail.html
│       │   └── error/
│       │       ├── NotFound.vue           ← errors/404.html
│       │       ├── RateLimit.vue          ← errors/429.html
│       │       └── ServerError.vue        ← errors/500.html
│       │
│       ├── components/                    ← 可复用业务组件
│       │   ├── stock/
│       │   │   ├── StockInfoCard.vue      ← 个股信息卡片
│       │   │   ├── HistoryPanel.vue       ← 历史数据Tab面板
│       │   │   ├── FactorsPanel.vue       ← 技术因子Tab面板
│       │   │   ├── MoneyflowPanel.vue     ← 资金流向Tab面板
│       │   │   ├── CyqPanel.vue           ← 筹码分布Tab面板
│       │   │   └── WatchlistButton.vue    ← 自选股按钮
│       │   ├── chart/
│       │   │   ├── ChartCard.vue          ← 图表容器卡片
│       │   │   ├── KlineChart.vue         ← K线图组件
│       │   │   ├── FactorsChart.vue       ← 技术指标趋势图
│       │   │   ├── MoneyflowChart.vue     ← 资金流向对比图
│       │   │   ├── NetflowChart.vue       ← 净流入趋势图
│       │   │   ├── CostDistChart.vue      ← 成本分位曲线图
│       │   │   └── WinnerRateChart.vue    ← 胜率变化图
│       │   ├── common/
│       │   │   ├── DataTable.vue          ← 通用表格（带分页/排序/加载状态）
│       │   │   ├── PageHeader.vue         ← 页面标题栏
│       │   │   ├── EmptyState.vue         ← 空数据占位
│       │   │   └── LoadingSpinner.vue     ← 加载动画
│       │   └── admin/
│       │       └── AdminTable.vue         ← 管理端通用CRUD表格
│       │
│       ├── composables/                   ← 组合式函数（复用逻辑）
│       │   ├── useEcharts.ts              ← ECharts 实例管理（防内存泄漏）
│       │   ├── usePagination.ts           ← 分页逻辑封装
│       │   ├── useLoading.ts              ← 加载状态管理
│       │   ├── useForm.ts                 ← 表单验证封装
│       │   └── useSSE.ts                  ← SSE 流式连接封装
│       │
│       ├── stores/                         ← Pinia 状态管理
│       │   ├── user.ts                     ← 用户登录状态、权限、token
│       │   ├── watchlist.ts               ← 自选股列表缓存
│       │   └── app.ts                     ← 全局状态（侧栏折叠等）
│       │
│       ├── router/                         ← Vue Router
│       │   ├── index.ts                    ← 路由表定义
│       │   └── guards.ts                   ← 导航守卫（登录/权限检查）
│       │
│       ├── layouts/                        ← 布局组件
│       │   ├── DefaultLayout.vue           ← 默认布局（侧边栏+顶栏+内容区）
│       │   ├── AuthLayout.vue              ← 认证页布局（居中卡片，无侧栏）
│       │   └── ErrorLayout.vue             ← 错误页布局
│       │
│       ├── utils/                          ← 工具函数
│       │   ├── format.ts                   ← 数字/百分比/日期格式化
│       │   ├── request.ts                  ← 原有apiRequest的迁移版
│       │   └── constants.ts                ← 常量定义（市场类型、颜色映射等）
│       │
│       ├── styles/                          ← 全局样式
│       │   ├── variables.scss              ← SCSS 变量（主题色/间距）
│       │   ├── global.scss                 ← 全局样式
│       │   ├── element-overrides.scss      ← Element Plus 样式覆盖
│       │   └── transitions.scss            ← 过渡动画
│       │
│       └── types/                           ← TypeScript 类型定义
│           ├── stock.d.ts                   ← 股票数据类型
│           ├── api.d.ts                     ← API响应通用类型
│           └── user.d.ts                    ← 用户类型
│
├── quantitative_analysis/                 ← 【原有】Flask后端（基本不动）
│   ├── app/
│   │   ├── __init__.py                     ← 修改：CORS适配、移除模板路由
│   │   ├── api/                            ← 保留：所有API接口不动
│   │   ├── services/                       ← 保留：所有业务逻辑不动
│   │   └── templates/                      ← 保留：暂不删除（混合过渡期）
│   └── ...
│
├── deploy/
│   └── nginx.conf                          ← 【修改】SPA fallback + API代理
│
├── Dockerfile                             ← 【修改】多阶段构建
└── docker-compose.yml                     ← 【修改】加入前端构建+Nginx
```

---

## 三、详细任务清单

### ═══════════════════════════════════════
### 阶段1：环境搭建（预计 30 分钟）
### ═══════════════════════════════════════

#### 任务 1.1：初始化 Vue3 项目脚手架

**目标**: 创建 `frontend/` 目录并生成可运行的空壳 Vue 项目

**具体操作**:
```bash
cd quantitative_analysis-vue
npm create vue@latest frontend
```

**交互选择项**:
| 选项 | 选择 | 原因 |
|------|------|------|
| Project name | `frontend` | - |
| Add TypeScript? | **Yes** | 类型安全，IDE提示更好 |
| Support JSX? | No | Vue模板语法更直观 |
| Vue Router? | **Yes** | 多页面必需 |
| Pinia? | **Yes** | 状态管理 |
| Vitest? | No | 毕设可跳过测试 |
| E2E Testing? | No | 同上 |
| ESLint? | **Yes** (ESLint + Prettier) | 代码规范 |

**安装额外依赖**:
```bash
cd frontend
npm install element-plus @element-plus/icons-vue echarts vue-echarts axios marked dayjs sass

# 开发依赖（如果需要更好的类型支持）
npm install -D @types/marked unplugin-auto-import unplugin-vue-components
```

**产出文件**:
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/index.html`
- `frontend/src/main.ts`, `App.vue`, etc.

**验收标准**: `npm run dev` 能在 http://localhost:5173 显示 Vue 默认页面

---

#### 任务 1.2：配置 Vite 开发代理

**目标**: 让开发时前端 `/api/*` 和 `/auth/*` 自动转发到 Flask :5000

**修改文件**: `frontend/vite.config.ts`

**具体内容**:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),  // 支持 @/ 别名导入
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path,  // /api/xxx -> http://localhost:5000/api/xxx
      },
      '/auth': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // Flask 的非API页面（过渡期保留）
      '/static': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,  // 生产环境不生成sourcemap
    rollupOptions: {
      output: {
        manualChunks: {
          // 分包策略：第三方库单独打包
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          'echarts': ['echarts', 'vue-echarts'],
          'vendor': ['axios', 'marked', 'dayjs'],
        },
      },
    },
  },
})
```

**验收标准**: 
- 访问 `http://localhost:5173/api/stocks` 能返回 Flask 的 JSON 数据（跨域不报错）

---

#### 任务 1.3：注册 Element Plus + ECharts 全局组件

**目标**: 配置 UI 库和图表库的全局可用性

**修改文件**: `frontend/src/main.ts`

**具体内容**:
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'  // 中文语言包

import App from './App.vue'
import router from './router'
import '@/styles/global.scss'  // 全局样式

const app = createApp(App)

// 注册所有Element Plus图标（全局可用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })  // Element Plus中文模式

app.mount('#app')
```

**新建文件**: `frontend/src/styles/global.scss`
```scss
// 全局样式变量
$primary-color: #409eff;
$danger-color: #f56c6c;
$success-color: #67c23a;
$warning-color: #e6a23c;
$info-color: #909399;

// 涨跌颜色（股票专用）
$text-up: #f5222d;   // 涨-红色
$text-down: #52c41a; // 跌-绿色

* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }

.page-container { padding: 20px; }
.text-up { color: $text-up !important; }
.text-down { color: $text-down !important; }

// 表格固定高度滚动
.scroll-table { max-height: 500px; overflow-y: auto; }
```

**验收标准**: 页面中可以直接使用 `<el-button>` `<el-table>` 等 Element 组件

---

#### 任务 1.4：搭建完整目录结构骨架

**目标**: 创建所有空文件和基础骨架代码

**需创建的文件列表**:

| 文件 | 初始内容 |
|------|---------|
| `src/api/request.ts` | Axios 实例 + 拦截器框架 |
| `src/api/stock.ts` | 空 API 函数导出 |
| `src/api/analysis.ts` | 空 |
| `src/api/auth.ts` | 空 |
| `src/api/monitor.ts` | 空 |
| `src/api/ai.ts` | 空 |
| `src/api/admin.ts` | 空 |
| `src/stores/user.ts` | Pinia store 骨架 |
| `src/stores/watchlist.ts` | 空 |
| `src/stores/app.ts` | 空 |
| `src/router/index.ts` | 基础路由表（只有首页） |
| `src/router/guards.ts` | 导航守卫框架 |
| `src/layouts/DefaultLayout.vue` | 侧边栏+顶栏布局骨架 |
| `src/layouts/AuthLayout.vue` | 居中卡片布局骨架 |
| `src/utils/format.ts` | formatNumber / formatPercent 工具函数 |
| `src/utils/constants.ts` | 常量定义 |
| `src/composables/useEcharts.ts` | ECharts 实例管理 composable |
| `src/types/stock.d.ts` | 股票数据接口定义 |

**验收标准**: 所有文件存在，`npm run dev` 不报错

---

### ═══════════════════════════════════════
### 阶段2：基础设施层（预计 1 小时）
### ═══════════════════════════════════════

#### 任务 2.1：封装 Axios 请求模块

**源文件**: 原项目中每个 HTML 内嵌的 `apiRequest()` 函数（约 10 处重复实现）

**目标文件**: `frontend/src/api/request.ts`

**需要实现的功能**:

```typescript
// 功能清单：
// [x] 1. 创建 axios 实例，baseURL=/api, timeout=30000
// [x] 2. withCredentials=true（携带cookie保持session兼容）
// [x] 3. 请求拦截器：附加 Authorization header（如果有token）
// [x] 4. 响应拦截器：
//     - 成功：直接返回 response.data
//     - 401：清除用户状态→跳转/login → ElMessage.error('登录已过期')
//     - 403：ElMessage.error('没有权限')
//     - 429：ElMessage.warning('请求频繁')
//     - 500：ElMessage.error('服务器错误')
//     - 网络错误：ElMessage.error('网络异常')
// [x] 5. 导出 get/post/put/delete 便捷方法
// [x] 6. 支持上传进度回调（用于大文件上传场景）

// 对应原代码中的这些位置：
// - base.html 中 <script> 里的 apiRequest() 函数（~30行）
// - stock_detail.html 中的 fetch 调用（~15处）
// - 其他页面中的类似调用
```

**关键差异点**:
- 原代码：每次手动 `fetch()` + 手动检查 `response.code === 200`
- 新代码：拦截器统一处理，页面只需 `const data = await getStockInfo(code)` 即可拿到数据

---

#### 任务 2.2：封装全部 API 接口模块

**源文件**: `app/api/` 下所有 Python 路由文件

**目标**: 将以下接口全部映射为 TypeScript 函数：

| 模块 | 接口数量 | 对应原文件 | 示例函数签名 |
|------|---------|-----------|-------------|
| **stock.ts** | 9 | stock_api.py | `getStockInfo(tsCode)` `getStockHistory(tsCode, limit)` `getStockFactors(tsCode, limit)` `getStockMoneyflow(tsCode, limit)` `getStockCyq(tsCode, limit)` `getStockList(params)` `screenStocks(params)` `addToWatchlist(tsCode)` `removeFromWatchlist(tsCode)` |
| **analysis.ts** | 4 | analysis_api.py | `runAnalysis(stock, params)` `getAnalysisResult(taskId)` `runBacktest(stock, strategy, params)` `getBacktestResult(taskId)` |
| **auth.ts** | 5 | auth_routes.py | `login(username, password)` `register(data)` `logout()` `forgotPassword(email)` `updateProfile(data)` `changePassword(oldPwd, newPwd)` |
| **monitor.ts** | 2 | realtime_monitor_api.py | `getMonitorList()` `subscribeMonitor(tsCode)` |
| **ai.ts** | 1 (SSE) | ai_assistant_api.py | `chatStream(message, onMessage, onError)` — 特殊：SSE流式 |
| **admin.ts** | 6 | admin_routes.py | `getDashboardStats()` `getUserList(params)` `getUserDetail(id)` `updateUserStatus(id, status)` `getDataStats()` `getLogs(params)` |

**每个函数的规范**:
```typescript
// 以 getStockHistory 为例
export interface HistoryParams {
  ts_code: string
  limit?: number  // 默认60
  start_date?: string
  end_date?: string
}

export interface StockDailyRecord {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
  pct_chg: number
}

export function getStockHistory(
  tsCode: string, 
  limit: number = 60
): Promise<ApiResponse<StockDailyRecord[]>>
```

---

#### 任务 2.3：实现 Pinia 状态管理

**目标文件**:
- `src/stores/user.ts` — 用户状态
- `src/stores/watchlist.ts` — 自选股缓存
- `src/stores/app.ts` — 全局UI状态

**stores/user.ts 详细设计**:
```typescript
interface UserState {
  isLoggedIn: boolean
  userId: number | null
  username: string | null
  isAdmin: boolean
  token: string | null
  userInfo: UserInfo | null
}

// Actions:
// - login(credentials) → 调用API → 存状态 → 跳转首页
// - logout() → 清除状态 → 跳转登录页
// - fetchUserInfo() → 获取当前用户详情
// - checkAuth() → 启动时从cookie/session恢复登录态

// Getters:
// - isLoggedIn: boolean
// - isAdmin: boolean
// - displayName: computed username 或 '未登录'
```

**stores/watchlist.ts**:
```typescript
// 缓存自选股列表，避免每次进入页面都重新请求
// Actions:
// - fetchWatchlist() → GET /api/watchlist/
// - toggleWatchlist(tsCode) → POST/DELETE 切换状态
// - isInWatchlist(tsCode): boolean
```

**stores/app.ts**:
```typescript
// - sidebarCollapsed: boolean（侧栏折叠状态）
// - loadingCount: number（全局loading计数）
// - pageTitle: string（当前页面标题）
```

---

#### 任务 2.4：配置 Vue Router 路由表

**目标文件**: `src/router/index.ts`

**完整路由表**:

```typescript
const routes = [
  {
    path: '/',
    component: DefaultLayout,
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/dashboard/DashboardPage.vue'), meta: { title: '首页', requiresAuth: false } },
      { path: 'stocks', name: 'stock-list', component: () => import('@/views/stock/StockList.vue'), meta: { title: '股票列表', requiresAuth: true } },
      { path: 'stock/:tsCode', name: 'stock-detail', component: () => import('@/views/stock/StockDetail.vue'), meta: { title: '股票详情', requiresAuth: true } },
      { path: 'analysis', name: 'analysis', component: () => import('@/views/analysis/AnalysisPage.vue'), meta: { title: '技术分析', requiresAuth: true } },
      { path: 'backtest', name: 'backtest', component: () => import('@/views/backtest/BacktestPage.vue'), meta: { title: '策略回测', requiresAuth: true } },
      { path: 'screen', name: 'screen', component: () => import('@/views/screen/ScreenPage.vue'), meta: { title: '智能选股', requiresAuth: true } },
      { path: 'monitor', name: 'monitor', component: () => import('@/views/monitor/MonitorPage.vue'), meta: { title: '实时监控', requiresAuth: true } },
      { path: 'ai-assistant', name: 'ai-assistant', component: () => import('@/views/ai/AiAssistantPage.vue'), meta: { title: 'AI 助手', requiresAuth: true } },

      // 管理端路由
      { path: 'admin', redirect: '/admin/dashboard' },
      { path: 'admin/dashboard', name: 'admin-dashboard', component: () => import('@/views/admin/AdminDashboard.vue'), meta: { title: '管理仪表盘', requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/users', name: 'admin-users', component: () => import('@/views/admin/AdminUsers.vue'), meta: { title: '用户管理', requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/users/:id', name: 'admin-user-detail', component: () => import('@/views/admin/AdminUserDetail.vue'), meta: { title: '用户详情', requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/data', name: 'admin-data', component: () => import('@/views/admin/AdminData.vue'), meta: { title: '数据管理', requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/logs', name: 'admin-logs', component: () => import('@/views/admin/AdminLogs.vue'), meta: { title: '操作日志', requiresAuth: true, requiresAdmin: true } },
    ],
  },
  {
    path: '/auth',
    component: AuthLayout,
    children: [
      { path: 'login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { title: '登录' } },
      { path: 'register', name: 'register', component: () => import('@/views/auth/RegisterView.vue'), meta: { title: '注册' } },
      { path: 'forgot-password', name: 'forgot-password', component: () => import('@/views/auth/ForgotPassword.vue'), meta: { title: '找回密码' } },
      { path: 'profile', name: 'profile', component: () => import('@/views/auth/ProfileView.vue'), meta: { title: '个人中心', requiresAuth: true } },
    ],
  },
  {
    // 错误页面
    path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/error/NotFound.vue') },
]
```

**导航守卫** (`router/guards.ts`):
```typescript
// beforeEach 守卫逻辑：
// 1. 目标路由 requiresAuth=true 且 未登录 → 重定向到 /auth/login?redirect=当前路径
// 2. 目标路由 requiresAdmin=true 且 非管理员 → 重定向到首页 + ElMessage.warning('无权限')
// 3. 已登录用户访问 /auth/login → 重定向到 /
// 4. 设置 document.title = route.meta.title + ' - 股票分析系统'
```

---

#### 任务 2.5：创建全局布局组件

**目标文件**: `layouts/DefaultLayout.vue`

**UI 结构**（对应原 base.html）:
```
┌─────────────────────────────────────────────────────┐
│ [📈 Logo]  股票量化分析系统          [头像] [退出]   │  ← el-header
├────────┬────────────────────────────────────────────┤
│        │  首页 > 股票详情                            │  ← el-breadcrumb
│ 📊首页 │                                             │
│ 📈股票 ├────────────────────────────────────────────┤
│ 📉分析 │                                             │
│ 🔬回测 │            <router-view />                 │  ← 主内容区
│ 🔍选股 │            （页面内容在这里渲染）              │
│ 👁监控 │                                             │
│ 🤖AI   │                                             │
│        │                                             │
│ ⚙️ 管理│  (仅管理员可见)                             │
│  ├仪表│                                             │
│  ├用户│                                             │
│  ├数据│                                             │
│  └日志│                                             │
└────────┴────────────────────────────────────────────┘
```

**功能细节**:
- 左侧菜单根据 `userStore.isLoggedIn` 决定显示哪些项
- 管理子菜单根据 `userStore.isAdmin` 条件显示
- 顶栏右侧显示当前用户名 + 退出按钮
- 面包屑自动读取 `route.meta.title`
- 侧栏支持折叠（点击按钮切换宽度 220px ↔ 64px）

**目标文件**: `layouts/AuthLayout.vue`
- 居中白色卡片 + 蓝色背景
- 用于登录/注册/找回密码页面

---

### ═══════════════════════════════════════
### 阶段3：核心页面迁移（预计 8-12 小时）
### ═══════════════════════════════════════

#### ⭐ 任务 3.1：迁移 stock_detail.html → StockDetail.vue

**这是最复杂的单个页面，原文件 1200 行**

**源文件**: `app/templates/stock_detail.html`

**拆分策略**:

```
StockDetail.vue (主容器，~150行)
│
├── components/stock/StockInfoCard.vue (~120行)
│   ┌──────────────────────────────────────┐
│   │ 股票名称 (000001 平安银行)           │
│   │ 代码 | 行业 | 地域 | 上市日期 | 市场 │
│   └──────────────────────────────────────┘
│   ┌────────────────┐
│   │ [➕ 加入自选]   │
│   │ [📊 技术分析]  │
│   │ [📈 策略回测]  │
│   └────────────────┘
│
├── <el-tabs>
│   ├── components/stock/HistoryPanel.vue (~200行)
│   │   [30天] [60天] [120天] [500天]  ← el-radio-group (v-model)
│   │   ┌─────────────────────────────┐
│   │   │ el-table (日期/开/高/低/收/量/额/涨跌幅) │
│   │   │  el-pagination (分页)       │
│   │   └─────────────────────────────┘
│   │   ┌─────────────────────────────┐
│   │   │ ECharts K线图 (vue-echarts) │
│   │   └─────────────────────────────┘
│   │
│   ├── components/stock/FactorsPanel.vue (~180行)
│   │   ┌───────────────────────────────┐
│   │   │ ECharts 多指标折线图           │
│   │   │ MACD DIF/DEA/MACD/RSI/KDJ     │
│   │   └───────────────────────────────┘
│   │   ┌───────────────────────────────┐
│   │   │ el-table 技术因子详细数据       │
│   │   │ (MACD/KDJ/RSI/BOLL/CCI)      │
│   │   └───────────────────────────────┘
│   │
│   ├── components/stock/MoneyflowPanel.vue (~160行)
│   │   ├── ECharts 分单资金买卖对比柱状图
│   │   ├── ECharts 净流入趋势面积图
│   │   └── 资金形态指标卡片(4个数值)
│   │   └── 详细数据表格
│   │
│   └── components/stock/CyqPanel.vue (~160行)
│       ├── ECharts 成本分位曲线图(6条线)
│       ├── ECharts 胜率变化面积图(+50%基准线)
│       ├── 筹码分析指标卡片(4个)
│       └── 详细数据表格
```

**逐块迁移对照**:

| 原代码位置 | 原实现 | 迁移后实现 |
|-----------|--------|-----------|
| 第178-192行 `loadStockInfo()` | async/await fetch + innerHTML | `onMounted` → `getStockInfo(tsCode)` → `stockInfo.value = res.data` |
| 第195-256行 `renderStockInfo()` | 模板字符串拼HTML | `StockInfoCard.vue` template 区域声明式绑定 |
| 第259-273行 `loadHistoryData(days)` | fetch + onclick参数传递 | `watch(days)` 自动触发重新请求 |
| 第276-319行 `renderHistoryData()` | `` `${data.map(...)}` `` 拼 table | `<el-table :data="displayData">` 声明式 |
| 第54-58行 天数按钮组 | `onclick="loadHistoryData(N)"` | `<el-radio-group v-model="days">` 双向绑定 |
| **按钮active状态** | JS 操作 DOM class（之前修过的bug） | `v-model` 自动处理选中态，无需手动JS |
| 第300行 `.slice(0,50)` | 手动截取 | `computed` 分页属性自动计算 |
| 第315行 "显示全部"展开按钮 | innerHTML 追加全量DOM | `el-pagination` 内置分页组件 |
| 第126-136行 `_chartInstances` | 手动管理字典 | `useEcharts()` composable 封装 |
| 第141-146行 resize监听 | window.addEventListener | composable 内部统一处理 |
| 第1178-1220行 自选股按钮 | alert() + 手动切换 | ElMessage + watchlistStore.toggleWatchlist() |

**关键迁移注意点**:
1. ECharts option 配置 **几乎可以原样复制**，只是从 JS 字符串变成 TypeScript 对象
2. `formatNumber()` / `formatPercent()` 工具函数提取到 `utils/format.ts` 全局复用
3. 表格列的颜色条件渲染：`:class="{ 'text-danger': row.pct_chg >= 0 }"` 替代模板字符串里的三元表达式

---

#### 任务 3.2：迁移 analysis.html → AnalysisPage.vue

**源文件**: `app/templates/analysis.html` (52KB)

**功能模块**:

| 模块 | 原实现 | 迁移要点 |
|------|--------|---------|
| 股票选择输入框 | input + 搜索建议下拉 | `el-autocomplete` 组件 |
| 策略选择（下拉） | select | `el-select` |
| 参数设置区域 | 动态生成的表单字段 | `el-form` + 动态 `el-form-item` |
| "开始分析"按钮 | onclick → fetch | `@click` → `runAnalysis()` → loading状态 |
| 结果展示区（多图表） | ECharts 渲染 | `vue-echarts` 组件化 |
| 技术指标信号标注 | 在K线上叠加标记 | ECharts markPoint/markLine 配置 |

---

#### 任务 3.3：迁移 backtest.html → BacktestPage.vue

**源文件**: `app/templates/backtest.html` (26KB)

**功能模块**:
- 策略选择（布林带/均线/RSI等多策略）
- 回测参数（时间范围、初始资金、手续费率）
- 回测执行按钮 + 进度展示
- 结果可视化：
  - 收益曲线（ECharts line）
  - 最大回撤（ECharts area）
  - 交易记录表格（买卖点位）
  - 统计摘要卡片（年化收益/夏普比率/胜率等）

---

#### 任务 3.4：迁移 screen.html → ScreenPage.vue

**源文件**: `app/templates/screen.html` (22KB)

**功能模块**:
- 动态筛选条件（行业/地域/市值/PE/PB等，多条件组合）
- el-form 动态字段渲染
- el-table 结果展示 + 排序 + 分页
- 导出Excel功能（`export xlsx` 按钮）

---

#### 任务 3.5：迁移 realtime_monitor.html → MonitorPage.vue

**源文件**: `app/templates/realtime_monitor.html` (31KB)

**特殊之处**: **SSE（Server-Sent Events）实时推送**

**迁移要点**:
```typescript
// composables/useSSE.ts
export function useSSE(url: string, onMessage: (data: any) => void) {
  let eventSource: EventSource | null = null
  
  function connect() {
    eventSource = new EventSource(url)
    eventSource.onmessage = (event) => {
      onMessage(JSON.parse(event.data))
    }
    eventSource.onerror = () => {
      // 断线重连逻辑
      setTimeout(connect, 3000)
    }
  }
  
  function disconnect() {
    eventSource?.close()
  }
  
  onUnmounted(() => disconnect())
  
  return { connect, disconnect }
}
```

- 数据实时更新表格行（高亮变化的单元格）
- 涨跌闪烁动画（CSS transition）

---

#### 任务 3.6：迁移 ai_assistant.html → AiAssistantPage.vue

**源文件**: `app/templates/ai_assistant.html` (40KB)

**特殊之处**: **SSE 流式对话**

**迁移要点**:
```vue
<template>
  <div class="ai-chat">
    <!-- 对话消息列表 -->
    <div class="messages" ref="messagesRef">
      <div v-for="msg in messages" :key="msg.id" :class="['msg', msg.role]">
        <!-- 用户消息 -->
        <template v-if="msg.role === 'user'">
          <div class="bubble">{{ msg.content }}</div>
        </template>
        <!-- AI回复：Markdown渲染 -->
        <template v-else>
          <div class="bubble markdown-body" v-html="renderMarkdown(msg.content)" />
        </template>
      </div>
      <!-- 打字机效果指示器 -->
      <div v-if="isStreaming" class="msg assistant typing">
        <span class="dots"><span>.</span><span>.</span><span>.</span></span>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <el-input v-model="inputText" type="textarea" @keyup.enter.exact="sendMessage" />
      <el-button type="primary" :loading="isStreaming" @click="sendMessage">发送</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'  // Markdown → HTML
import { ref, nextTick } from 'vue'

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isStreaming = ref(false)

async function sendMessage() {
  if (!inputText.value.trim() || isStreaming.value) return
  
  messages.value.push({ role: 'user', content: inputText.value })
  const question = inputText.value
  inputText.value = ''
  
  // AI占位消息（流式填充）
  const aiMsgId = Date.now()
  messages.value.push({ id: aiMsgId, role: 'assistant', content: '' })
  isStreaming.value = true
  
  // SSE流式接收
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: question }),
  })
  
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    // 找到对应的AI消息并追加内容
    const aiMsg = messages.value.find(m => m.id === aiMsgId)
    if (aiMsg) aiMsg.content += chunk
    // 自动滚动到底部
    await nextTick()
    scrollToBottom()
  }
  
  isStreaming.value = false
}
</script>
```

---

#### 任务 3.7：迁移 stocks.html + index.html

- **StockList.vue**: 搜索 + 分页表格 + 点击跳转详情
- **DashboardPage.vue**: 首页仪表盘（欢迎语 + 快捷入口 + 市场概览统计卡片）

---

### ═══════════════════════════════════════
### 阶段4：认证与用户系统（预计 2 小时）
### ═══════════════════════════════════════

#### 任务 4.1：迁移登录/注册/找回密码页面

| 原页面 | 新组件 | 关键要素 |
|--------|--------|---------|
| auth/login.html | LoginView.vue | el-form + 规则校验 + remember-me checkbox |
| auth/register.html | RegisterView.vue | el-form + 密码强度检测 + 用户协议勾选 |
| auth/forgot_password.html | ForgotPassword.vue | 邮箱输入 + 发送验证码倒计时 |

**表单校验规则**:
```typescript
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}
```

**登录流程**:
```
用户填写表单 → el-validate 校验通过 → 调用 auth.login()
  → 成功: userStore.login(res.data) → router.push(redirect || '/')
  → 失败: ElMessage.error(res.message)
```

---

#### 任务 4.2：迁移个人中心页面

**源文件**: `auth/profile.html` (16KB)

**功能模块**:
- 个人信息展示（头像/用户名/邮箱/注册时间/最后登录）
- 修改信息表单（昵称/邮箱）
- 修改密码弹窗（旧密码 + 新密码 + 确认新密码）

---

#### 任务 4.3：完善路由守卫逻辑

**文件**: `src/router/guards.ts`

```typescript
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const title = to.meta.title as string
  
  // 设置页面标题
  document.title = title ? `${title} - 股票分析系统` : '股票分析系统'
  
  // 需要登录但未登录 → 跳转登录页
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return next({ path: '/auth/login', query: { redirect: to.fullPath } })
  }
  
  // 需要管理员但不是管理员 → 回首页
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    ElMessage.warning('您没有访问此页面的权限')
    return next({ path: '/' })
  }
  
  // 已登录用户访问登录页 → 回首页
  if ((to.name === 'login' || to.name === 'register') && userStore.isLoggedIn) {
    return next({ path: '/' })
  }
  
  next()
})
```

---

### ═══════════════════════════════════════
### 阶段5：管理端迁移（预计 2-3 小时，可选降级）
### ═══════════════════════════════════════

> **降级方案**: 如果时间不够，管理端可以暂时保留在 Flask 模板渲染中，
> 通过 Nginx 把 `/admin/*` 路径继续代理到 Flask，后续再迁移。

#### 任务 5.1：迁移管理端页面

| 原页面 | 新组件 | 复杂度 | 核心功能 |
|--------|--------|--------|---------|
| admin/dashboard.html | AdminDashboard.vue | 低 | 统计卡片（用户数/活跃度/数据量） |
| admin/users.html | AdminUsers.vue | 中 | 用户列表 + 搜索 + 禁用/启用/删除 |
| admin/user_detail.html | AdminUserDetail.vue | 中 | 用户详情 + 操作日志 |
| admin/data.html | AdminData.vue | 低 | 数据同步状态展示 |
| admin/logs.html | AdminLogs.vue | 中 | 日志表格 + 时间筛选 + 级别过滤 |

#### 任务 5.2：实现按钮级权限控制

```typescript
// directives/permission.ts — 自定义指令 v-permission
// 用法：<el-button v-permission="'user:delete'">删除</el-button>
app.directive('permission', {
  mounted(el, binding) {
    const permission = binding.value as string
    const userStore = useUserStore()
    if (!userStore.hasPermission(permission)) {
      el.parentNode?.removeChild(el)  // 无权限则移除元素
    }
  }
})
```

---

### ═══════════════════════════════════════
### 阶段6：构建部署（预计 1 小时）
### ═══════════════════════════════════════

#### 任务 6.1：更新 Dockerfile 为多阶段构建

```dockerfile
# ========== 阶段1: Node.js 构建前端 ==========
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ========== 阶段2: Python 安装依赖 ==========
FROM python:3.11-slim AS python-builder
WORKDIR /app/quantitative_analysis
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target /deps

# ========== 阶段3: 最终运行镜像 ==========
FROM python:3.11-slim AS runtime

# 安装 Nginx（托管前端静态文件 + 反代API）
RUN apt-get update && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

# 复制Python依赖
COPY --from=python-builder /deps /usr/local/lib/python3.11/site-packages/

# 复制Flask应用
COPY quantitative_analysis/ /app/quantitative_analysis/
WORKDIR /app/quantitative_analysis

# 复制前端构建产物到Nginx
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html/dist/

# Nginx配置
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

# 启动脚本：同时运行Nginx + Flask
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
```

**docker-entrypoint.sh**:
```bash
#!/bin/bash
# 启动Nginx（前台运行前端静态资源 + API反代）
nginx -g 'daemon off;' &

# 启动Flask（后台运行API服务）
gunicorn -w 2 -b 0.0.0.0:5000 run_system:create_app() &

# 等待任意进程结束
wait
```

---

#### 任务 6.2：更新 nginx.conf

```nginx
server {
    listen 80;
    server_name _;

    # ====== 前端 SPA 路由（优先匹配最短路径）======
    location / {
        root /usr/share/nginx/html/dist;
        try_files $uri $uri/ /index.html;  # SPA fallback
        index index.html;
    }

    # ====== API 反向代理到 Flask ======
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE/AI流式响应需要关闭缓冲
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }

    # ====== 认证路由代理到 Flask（如果还没迁移完）=====
    location ~ ^/(auth/|admin/) {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120;
    }

    # ====== 静态资源长期缓存 ======
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root /usr/share/nginx/html/dist;
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Gzip压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;
}
```

---

#### 任务 6.3：Flask 后端调整

**最小改动**（确保API正常工作）:

| 改动 | 文件 | 内容 |
|------|------|------|
| CORS 更新 | `app/__init__.py` | 允许前端域名（生产环境）或保持开发模式全开 |
| 首页路由 | `app/main/main_bp.py` | 可选：移除模板渲染首页或保留作为fallback |
| Session Cookie | `config.py` | 设置 `SESSION_COOKIE_SAMESITE='Lax'`（跨域cookie安全） |

**不需要改动的部分** ✅:
- 所有 `/api/*` 路由 → **完全保留**
- 所有 Service 业务逻辑 → **完全保留**
- 所有 Model ORM 定义 → **完全保留**
- 数据库连接配置 → **完全保留**

---

## 四、执行顺序与依赖关系

```
阶段1 (环境搭建)
  ├── 1.1 初始化脚手架 ──────────────────┐
  ├── 1.2 Vite代理配置 ───────────────────┤
  ├── 1.3 Element Plus注册 ───────────────┤──→ 阶段完成：能跑起空壳Vue项目
  └── 1.4 目录结构骨架 ───────────────────┘
           │
           ▼
阶段2 (基础设施) ←── 依赖阶段1完成
  ├── 2.1 Axios封装 ────────────────────┐
  ├── 2.2 API接口模块 ───────────────────┤
  ├── 2.3 Pinia Store ──────────────────┤──→ 阶段完成：基础设施就绪
  ├── 2.4 Router + Guards ──────────────┤
  └── 2.5 Layout组件 ───────────────────┘
           │
           ▼
阶段3 (核心页面迁移) ←── 依赖阶段2完成
  ├── 3.7 stocks + index ────────────────┐ (先做简单的热身)
  ├── 3.1 stock_detail ⭐最难 ───────────┤
  ├── 3.2 analysis ──────────────────────┤
  ├── 3.3 backtest ──────────────────────┤
  ├── 3.4 screen ────────────────────────┤──→ 阶段完成：主要功能可使用
  ├── 3.5 monitor (SSE实时) ─────────────┤
  └── 3.6 ai_assistant (SSE流式) ────────┘
           │
           ▼
阶段4 (认证系统) ←── 可与阶段3并行
  ├── 4.1 登录/注册/找回密码 ────────────┐
  ├── 4.2 个人中心 ──────────────────────┤
  └── 4.3 路由守卫完善 ──────────────────┘
           │
           ▼
阶段5 (管理端) ←── 可选，时间不够可跳过
  ├── 5.1 管理端页面 ───────────────────┐
  └── 5.2 权限控制 ──────────────────────┘
           │
           ▼
阶段6 (部署) ←── 最后做
  ├── 6.1 Dockerfile多阶段构建 ──────────┐
  ├── 6.2 nginx.conf ────────────────────┤
  └── 6.3 Flask微调 ─────────────────────┘
```

---

## 五、工作量估算总表

| 阶段 | 任务数 | 预计工时 | 优先级 |
|------|-------|---------|--------|
| 阶段1：环境搭建 | 4 | 0.5h | P0 必须 |
| 阶段2：基础设施 | 5 | 1h | P0 必须 |
| 阶段3：核心页面 | 7 | 8-12h | P0 核心 |
| 阶段4：认证系统 | 3 | 2h | P0 必须 |
| 阶段5：管理端 | 2 | 2-3h | P1 可延后 |
| 阶段6：构建部署 | 3 | 1h | P1 最后做 |
| **总计** | **24** | **14.5-19.5h** | |

**如果只做 MVP（最小可行版本）**：阶段1+2+3(仅3.1+3.7)+4 ≈ **8-10小时**

---

## 六、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 时间不够无法全部迁移 | 管理端缺失 | 混合模式：管理端保留Flask模板 |
| ECharts 配置迁移出错 | 图表不显示 | Option对象可直接复用，改动很小 |
| SSE 流式连接跨域问题 | AI对话不可用 | Nginx proxy_buffering off + withCredentials |
| Session认证Cookie跨域 | 无法登录 | SameSite=Lax + Nginx同域代理解决 |
| Element Plus样式冲突 | 页面样式错乱 | scoped CSS + BEM命名隔离 |

---

## 七、验收标准（MVP完成标志）

- [ ] `npm run dev` 启动后能看到完整的侧边栏+顶栏布局
- [ ] 登录/注册功能正常（能调通 Flask `/auth/*` 接口）
- [ ] 股票列表页能搜索、分页、点击进入详情
- [ ] 个股详情页：基本信息 + 4个Tab（历史/因子/资金/筹码）都能正常展示数据和图表
- [ ] 天数切换按钮（30/60/120/500天）状态正确，数据刷新正常
- [ ] 表格分页正常（不卡顿）
- [ ] ECharts 图表渲染正常，窗口缩放自适应
- [ ] 自选股添加/移除功能正常
- [ ] `npm run build` 能成功打包
- [ ] Docker compose up 能一键启动整套服务
