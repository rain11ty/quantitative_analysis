# Vue 重构执行计划与当前进度

> 更新时间：`2026-04-28`
> 文档状态：`执行版`
> 适用范围：`frontend/`、`app/templates/vue_shell.html`、`app/main/views.py`、`app/utils/vite.py`

## 1. 文档目的

这份文档不再只描述“是否要做 Vue 化”，而是直接回答三个问题：

1. 当前仓库里的 Vue 重构已经做到哪里了。
2. 接下来应该按什么模块推进，才能安全替换旧的 Flask + Jinja 页面。
3. 每个模块具体要做什么、先做什么、做到什么程度算完成。

本计划默认遵循以下原则：

- 不重写后端业务层，继续复用现有 Flask 路由和 `/api/*` 接口。
- 不一次性切换全部页面，先在 `/app` 下并行交付，再逐页验收。
- 不破坏当前登录态，继续沿用同源 Session/Cookie 模式。
- 先治理共享层和已落地大页面，再扩展新页面，避免继续堆大文件。

## 2. 当前现状总览

### 2.1 已经落地的内容

- 已建立独立前端工程：`frontend/`
- 技术栈已确定：`Vue 3 + Vite + TypeScript + Vue Router + Pinia + Axios + ECharts`
- Flask 已提供 Vue 壳路由：
  - `app/main/views.py` 中已有 `/app` 与 `/app/<path:route_path>`
  - `app/templates/vue_shell.html` 已能注入 `window.__QUANT_APP_CONTEXT__`
  - `app/utils/vite.py` 已支持开发态 Vite 和生产态 manifest 读取
- 构建产物路径已确定：`app/static/vue`
- Vue 路由已建立，采用 `createWebHistory('/app')`
- 已有共享基础代码：
  - `frontend/src/lib/http.ts`
  - `frontend/src/lib/format.ts`
  - `frontend/src/components/BaseEChart.vue`
  - `frontend/src/types/stock.ts`
  - `frontend/src/types/screen.ts`

### 2.2 已经进入“真实迁移”阶段的页面

- `frontend/src/pages/StockDetailPage.vue`
  - 已具备真实数据加载
  - 已接入行情、历史、技术分析、资金流、筹码分布
  - 已接入自选股、记录保存、路由 query tab 切换
  - 当前问题是页面文件过大、职责过多、逻辑与 UI 强耦合

- `frontend/src/pages/ScreenPage.vue`
  - 已具备真实筛选表单和结果表格
  - 已接入行业、地区、交易日、动态条件、筛选结果
  - 已兼容登录态判断和 `/api/analysis/screen`
  - 当前问题同样是页面文件过大、配置常量内联、缺少共享状态与复用组件

### 2.3 仍处于占位阶段的页面

- `Stocks`
- `Realtime Monitor`
- `AI Assistant`
- `Backtest`
- `News`

这些页面目前主要由 `MigrationPage.vue` 占位，用于标记旧模板、接口组和迁移优先级。

### 2.4 当前最明显的结构问题

- `Pinia` 已注册，但还没有真正落地业务 `store`
- 没有 `services/`、`composables/`、`stores/`、`modules/` 目录分层
- `StockDetailPage.vue` 和 `ScreenPage.vue` 已经是“功能可用但不可继续堆功能”的状态
- 图表、数据请求、错误处理、登录态判断还分散在页面内部
- 页面级样式大量写在单文件组件内，复用成本高
- 当前文档与实际代码有轻微脱节
  - 例如 `ScreenPage.vue` 已经是实装页面，不再只是规划项
- 开发态配置存在待核对项
  - `frontend/README.md` 中写的是代理到 `5000`
  - `frontend/vite.config.ts` 中实际代理目标是 `5001`
- 需要统一检查中文编码显示，避免文档、终端和源码出现乱码观感

## 3. 当前进度总表

下表中的进度为基于当前仓库状态的执行估算，用于排期，不作为交付验收结论。

| 模块 | 当前状态 | 估算进度 | 现状依据 | 下一步重点 |
| --- | --- | --- | --- | --- |
| Vue 基础设施 | 已落地 | 75% | `frontend/`、`vue_shell.html`、`vite.py` | 统一目录规范、补共享层、核对 dev/prod 配置 |
| 应用壳与路由 | 已落地 | 70% | `App.vue`、`router/index.ts` | 加入路由守卫、页面 meta、异常兜底 |
| 共享数据层 | 初步可用 | 25% | `http.ts`、`format.ts` | 拆出 API service、错误处理、通用 composable |
| Stock Detail | 已实装 | 60% | `StockDetailPage.vue` | 拆模块、抽组件、抽 composable/store |
| Screen | 已实装 | 55% | `ScreenPage.vue` | 拆筛选面板/结果表格/动态条件模块 |
| Stocks 列表 | 占位 | 10% | `MigrationPage.vue` | 实现列表、搜索、分页、筛选 |
| Realtime Monitor | 占位 | 5% | `MigrationPage.vue` | 设计轮询/SSE 策略和仪表板组件 |
| AI Assistant | 占位 | 5% | `MigrationPage.vue` | 设计会话、消息流、状态恢复 |
| Backtest | 占位 | 5% | `MigrationPage.vue` | 设计策略表单、结果视图、任务状态 |
| News | 占位 | 5% | `MigrationPage.vue` | 设计列表流、分类页、详情展开 |
| 认证与切流 | 基础具备 | 40% | `/app` 路由公开、上下文注入完成 | 补路由守卫、页面级验收和逐页切换 |
| 测试与发布 | 基础较弱 | 15% | 目前无前端测试体系 | 补 typecheck、页面验收、构建与回退流程 |

## 4. 目标目录结构

在不破坏现有运行的前提下，建议把 `frontend/src` 逐步整理为：

```text
frontend/src
  app/
    router/
    guards/
    providers/
  components/
    charts/
    common/
    forms/
    feedback/
    layout/
  composables/
    useAsyncState.ts
    useAuthContext.ts
    usePagination.ts
    useEChartTheme.ts
  modules/
    stock-detail/
      api.ts
      components/
      composables/
      constants.ts
      types.ts
    screen/
      api.ts
      components/
      composables/
      constants.ts
      types.ts
    stocks/
    monitor/
    ai-assistant/
    backtest/
    news/
  services/
    http/
    app-context/
  stores/
    auth.ts
    ui.ts
    watchlist.ts
  styles/
    tokens.css
    utilities.css
    main.css
  types/
```

说明：

- 当前不建议直接重写全部页面，只建议在现有文件可运行的基础上逐步搬迁。
- `modules/` 按业务分，`components/` 放真正跨页面复用的 UI。
- `services/` 负责请求与上下文，`composables/` 负责可复用状态逻辑，`stores/` 只保存跨页共享状态。

## 5. 模块化执行计划

### 5.1 模块 A：基础设施与目录治理

### 当前进度

- 已有 Vite、Vue、TypeScript、Vue Router、Pinia 基础脚手架
- 已接上 Flask 壳页面与静态资源读取
- 还没有完成真正可维护的前端目录治理

### 具体操作

1. 新建并稳定目录分层：`modules/`、`services/`、`stores/`、`composables/`
2. 把 `frontend/src/lib/http.ts` 拆成：
   - `services/http/client.ts`
   - `services/http/interceptors.ts`
   - `services/http/errors.ts`
3. 补统一响应解析工具，兼容现有 `{ code, data, message }` 结构
4. 建立统一的加载、空状态、错误状态组件
5. 建立统一的页面容器、卡片、按钮、表格、标签样式
6. 把全局设计变量抽到 `styles/tokens.css`
7. 核对并统一开发代理配置、README 说明、部署说明
8. 统一检查源码和文档编码，全部按 UTF-8 管理

### 交付物

- 可复用的共享目录结构
- 统一 HTTP 请求层
- 统一状态反馈组件
- 统一样式 Token
- 更新后的开发文档

### 验收标准

- 新页面不再直接在页面文件里手写 Axios 实例
- 新页面不再直接复制错误提示和加载骨架逻辑
- README、Vite 配置、Flask 集成说明保持一致

### 5.2 模块 B：应用壳、路由与应用上下文

### 当前进度

- `App.vue` 和 `router/index.ts` 已可运行
- `window.__QUANT_APP_CONTEXT__` 已注入登录状态和初始路径
- 还缺少正式的路由治理能力

### 具体操作

1. 抽出 `useAuthContext()`，统一读取登录态、管理员态、用户名
2. 给路由补 `meta.requiresAuth`、`meta.pageKey`、`meta.legacyPath`
3. 增加基础路由守卫：
   - 未登录但需要登录的页面跳转登录页
   - 已登录页面保留 `next` 参数
4. 补统一的 `document.title` 更新逻辑
5. 为未来切流预留 `legacyPath -> appPath` 映射表
6. 给 404 和异常页增加更明确的回退提示

### 交付物

- 路由守卫
- 应用上下文 composable
- 页面元信息规范

### 验收标准

- 页面不再各自重复判断登录态
- 所有迁移页面都有明确的旧路由映射

### 5.3 模块 C：共享数据层与状态管理

### 当前进度

- 目前只有 `http.ts` 和部分 `types`
- `Pinia` 已接入但没有实际业务 store

### 具体操作

1. 建立最小共享 store：
   - `auth store`
   - `ui store`
   - `watchlist store`
2. 建立共享 composable：
   - `useRequestState`
   - `usePagedTable`
   - `useDateRange`
   - `useChartResize`
3. 建立模块 API 文件，禁止页面组件直接拼接所有接口
4. 为常用错误码建立统一处理规则：
   - `401` 登录失效
   - `403` 权限不足
   - `404` 数据缺失
   - `5xx` 服务异常
5. 建立 `toast/notice` 或 `banner` 的统一调用方式

### 交付物

- 共享 store
- 共享 composable
- 各业务模块 `api.ts`

### 验收标准

- 页面中的请求函数数量显著下降
- 登录失效、权限不足、服务异常的反馈方式统一

### 5.4 模块 D：Stock Detail 重构

### 当前进度

- 已是当前最完整的 Vue 页面
- 功能覆盖度高，但文件体量大，耦合严重
- 当前文件：`frontend/src/pages/StockDetailPage.vue`

### 当前页面建议拆分

- `StockDetailHeader`
- `StockOverviewMetrics`
- `RealtimeQuotePanel`
- `RealtimeKLineChart`
- `HistoryToolbar`
- `HistoryTable`
- `TechAnalysisSummary`
- `IndicatorChartPanel`
- `MoneyflowOverview`
- `MoneyflowTable`
- `CyqOverview`
- `CyqCharts`

### 具体操作

1. 先把所有接口请求移入 `modules/stock-detail/api.ts`
2. 再把页面状态拆到 composable：
   - `useStockDetailBase`
   - `useStockHistory`
   - `useStockTechAnalysis`
   - `useStockMoneyflow`
   - `useStockCyq`
3. 把 tab 切换逻辑与 query 参数同步逻辑独立出去
4. 把图表 option 生成逻辑从页面中移出，变成纯函数
5. 把自选股操作与分析记录保存封装为独立 action
6. 给每个 tab 建独立错误态、空状态、加载态组件
7. 统一历史数据、技术指标、资金流、筹码分布的表格列配置
8. 最后再做样式拆分，避免逻辑和样式同时改太多

### 建议执行顺序

1. 先抽 API
2. 再抽 composable
3. 再拆子组件
4. 最后调样式与交互细节

### 验收标准

- 页面功能与旧 `stock_detail.html` 对齐
- 拆分后主页面文件控制在可维护范围内
- 切换 tab 不丢状态或重复无意义请求
- 图表切换和卸载时不泄漏实例

### 5.5 模块 E：Screen 重构

### 当前进度

- 已有真实筛选能力
- 页面文件已较大，且筛选项配置与 UI 混在一起
- 当前文件：`frontend/src/pages/ScreenPage.vue`

### 当前页面建议拆分

- `ScreenHero`
- `ScreenFilterBasic`
- `ScreenFilterValuation`
- `ScreenFilterTechnical`
- `ScreenFilterMoneyflow`
- `DynamicConditionBuilder`
- `ScreenResultSummary`
- `ScreenResultTable`

### 具体操作

1. 将字段配置抽到 `modules/screen/constants.ts`
2. 将请求逻辑抽到 `modules/screen/api.ts`
3. 将表单与提交逻辑抽到 `useScreenForm()`
4. 将动态条件构建逻辑抽到 `useDynamicConditions()`
5. 将筛选结果规范化逻辑抽到 `normalizeScreenResult()`
6. 将结果表格列定义抽成配置，便于后续支持列裁剪与导出
7. 把登录校验和最新交易日加载统一接入共享 auth/request 层
8. 为筛选页加入基础结果缓存，避免同条件重复请求

### 验收标准

- 页面不再包含大段字段枚举和请求实现
- 动态条件构建可复用到 Backtest 或其他量化策略页面
- 表单重置、登录跳转、结果表格行为保持稳定

### 5.6 模块 F：Stocks 列表页

### 当前进度

- 仍是占位页
- 旧模板：`app/templates/stocks.html`

### 具体操作

1. 先梳理旧页面功能：
   - 搜索
   - 列表分页
   - 板块/地区筛选
   - 市场概览
2. 建立 `modules/stocks/api.ts`
3. 拆出 `StocksToolbar`、`StocksFilterPanel`、`StocksTable`、`MarketOverviewCards`
4. 实现 URL 与筛选条件双向同步
5. 支持跳转到：
   - Vue 详情页 `/app/stock/:tsCode`
   - 旧详情页 `/stock/:ts_code`
6. 把接口节流、搜索防抖、分页状态统一到 composable

### 验收标准

- 支持原有主要筛选与搜索链路
- 能稳定作为用户进入 `StockDetail` 的主入口

### 5.7 模块 G：Realtime Monitor 页面

### 当前进度

- 仍是占位页
- 旧模板：`app/templates/realtime_monitor.html`

### 具体操作

1. 先梳理旧页面数据源：
   - `/api/monitor/dashboard`
   - `/api/monitor/ranking`
   - `/api/monitor/stocks/:tsCode`
   - `/api/monitor/intraday/:tsCode`
   - `/api/monitor/shock`
2. 明确数据刷新策略：
   - 哪些接口轮询
   - 哪些接口按需刷新
   - 切换页面时如何清理定时器
3. 建立监控页模块结构：
   - `MonitorDashboardCards`
   - `RankingBoard`
   - `IntradayChart`
   - `ShockTable`
4. 抽 `usePollingTask()` 或 `useAutoRefresh()`，统一轮询生命周期
5. 给监控页做性能约束：
   - 限制同时请求数
   - 可见性切换时暂停刷新

### 验收标准

- 页面切换后不残留轮询
- 多图表场景下不会明显卡顿
- 数据刷新频率可配置、可暂停

### 5.8 模块 H：AI Assistant 页面

### 当前进度

- 仍是占位页
- 旧模板：`app/templates/ai_assistant.html`

### 具体操作

1. 明确接口契约：
   - 会话列表
   - 历史消息
   - 发消息
   - AI 状态
2. 设计模块组件：
   - `ConversationSidebar`
   - `MessageList`
   - `MessageComposer`
   - `AssistantStatusPanel`
3. 为消息流建立状态层：
   - 当前会话
   - 加载中
   - 发送中
   - 失败重试
   - 历史回放
4. 如果后端支持流式返回，单独封装流式处理 composable
5. 解决消息滚动、打字态、断线重连、会话切换恢复

### 验收标准

- 刷新页面后能恢复到最近会话
- 会话切换和消息发送不会互相打断
- 失败状态可重试且不丢输入

### 5.9 模块 I：Backtest 页面

### 当前进度

- 仍是占位页
- 旧模板：`app/templates/backtest.html`

### 具体操作

1. 梳理旧页面核心流程：
   - 策略参数填写
   - 回测发起
   - 结果展示
   - 历史记录查看
2. 拆出页面区域：
   - `BacktestStrategyForm`
   - `BacktestResultSummary`
   - `BacktestEquityChart`
   - `BacktestTradeTable`
   - `BacktestHistoryDrawer`
3. 建立 `useBacktestTask()` 管理提交、等待、结果读取
4. 复用 Screen 页已有动态条件模块，减少重复实现
5. 明确同步/异步任务模式，避免用户重复提交

### 验收标准

- 表单提交、结果展示、历史回测三条链路清晰分离
- 能和 `Screen` 共用部分条件构建逻辑

### 5.10 模块 J：News 页面

### 当前进度

- 仍是占位页
- 旧模板：`app/templates/news.html`

### 具体操作

1. 梳理新闻源与分类：
   - `/api/news`
   - `/api/news/cjzc`
   - `/api/news/global`
2. 拆出组件：
   - `NewsCategoryTabs`
   - `NewsList`
   - `NewsFilterBar`
   - `NewsDetailPanel`
3. 统一时间格式、来源标签、已读样式
4. 加入分页或无限加载，但只选一种，避免复杂度失控
5. 支持从新闻直接跳股票、行情或详情页

### 验收标准

- 新闻浏览路径比旧模板更清晰
- 不引入过重状态管理

### 5.11 模块 K：认证、权限与切流

### 当前进度

- `/app` 已被列为公开前缀，壳页面可直接进入
- Vue 页面内部已零散读取登录状态
- 还没有正式的页面级鉴权和逐页切换方案

### 具体操作

1. 给需要登录的页面补 `requiresAuth`
2. 统一登录跳转 URL 生成逻辑
3. 保留旧页面入口，直到新页面验收通过
4. 设计逐页切流表：
   - 旧路由
   - 新路由
   - 当前状态
   - 回退方式
5. 当页面验收完成后，再决定是否：
   - 旧路由直接重定向到 `/app/...`
   - 或保留“双入口”一段时间

### 验收标准

- 页面切流不影响登录态
- 任一页面都可快速回退到旧模板

### 5.12 模块 L：测试、验收与发布

### 当前进度

- 当前以前端人工验收为主
- 还没有前端测试体系和页面级验收清单固化

### 具体操作

1. 固定每次变更至少执行：
   - `npm run build`
   - `npm exec vue-tsc -- --noEmit -p tsconfig.json`
2. 为每个页面建立最小验收清单：
   - 数据能加载
   - 错误能显示
   - 登录态行为正确
   - 移动端可用
   - 旧页面仍可访问
3. 记录每个迁移页的接口清单与差异
4. 在切流前做一次并排验收：
   - 旧模板
   - `/app` 新页面
5. 约定回退方案：
   - 前端资源回退
   - 路由切回旧模板
   - 关闭新页面入口

### 验收标准

- 每个页面都有明确“通过/不通过”结论
- 发布失败时可在最短路径回退

## 6. 推荐实施顺序

建议按“先治理已落地页面，再扩展新页面”的顺序推进：

### 第 0 阶段：整理基础设施

- 完成目录治理
- 补共享数据层
- 统一配置与文档

### 第 1 阶段：重构已落地大页面

- 拆 `StockDetailPage.vue`
- 拆 `ScreenPage.vue`
- 把共用逻辑真正沉淀出来

### 第 2 阶段：补主入口页面

- 实现 `Stocks`
- 实现 `Realtime Monitor`

### 第 3 阶段：补复杂交互页面

- 实现 `AI Assistant`
- 实现 `Backtest`

### 第 4 阶段：补低风险页面与切流

- 实现 `News`
- 做逐页验收和路由切换

## 7. 建议周计划

如果按当前代码基础推进，建议用 5 周执行：

### 第 1 周

- 完成目录治理
- 抽共享 HTTP/service/composable
- 统一样式 token
- 核对开发代理和 README

### 第 2 周

- 拆 `StockDetail` 的 API、状态和子组件
- 完成历史、技术分析、资金流、筹码 tab 的结构化重构

### 第 3 周

- 拆 `Screen`
- 补 `Stocks` 列表页
- 复用筛选与表格基础设施

### 第 4 周

- 实现 `Realtime Monitor`
- 实现 `AI Assistant` 的最小可用版本

### 第 5 周

- 实现 `Backtest` 与 `News`
- 做逐页验收
- 准备第一批切流

## 8. 不建议现在做的事

- 不建议现在同时重写 Flask 后端业务层
- 不建议现在引入前后端完全跨域分离部署
- 不建议在共享层未稳定前继续把功能直接堆进 `StockDetailPage.vue` 或 `ScreenPage.vue`
- 不建议在没有回退方案的情况下直接把旧模板路由切到 Vue

## 9. 本次结论

当前仓库已经不是“要不要做 Vue 重构”的阶段，而是“基础设施已起好，两个核心页面已落地，但必须马上进入模块化治理”的阶段。

最优执行路线不是继续快速铺新页面，而是先把现有 `StockDetail` 和 `Screen` 拆成真正可复用的模块，再利用这些模块去做 `Stocks`、`Monitor`、`AI Assistant`、`Backtest` 和 `News`。这样计划最稳、复用率最高、回退成本也最低。
