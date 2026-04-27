# Vue 前端重构计划

> 文档日期：`2026-04-28`
> 状态：`规划中，未实施`

## 1. 先说明当前事实

当前仓库的正式前端仍然是：

- Flask 服务端渲染
- Jinja2 模板
- 页面内 JavaScript 调用 `/api/*`

也就是说，这份文档描述的是一个“未来可执行的拆分方案”，不是已经落地的现状。

## 2. 为什么还需要这份计划

尽管现在的 SSR 结构已经能跑，但前端继续增长时会遇到几个问题：

- `stock_detail.html`、`realtime_monitor.html`、`ai_assistant.html` 页面脚本都偏重
- 复杂交互逻辑分散在模板中，复用性有限
- 页面级状态管理、SSE 管理、图表生命周期管理越来越难维护

所以 Vue 化仍然是合理方向，只是应该建立在当前 Flask API 已经稳定的前提下进行。

## 3. 建议的拆分边界

### 第一阶段：先把 Flask 当纯后端能力中心

保留并继续稳定这些部分：

- `/api/*`
- `/auth/*`
- `/admin/api/*` 中的 JSON 类接口
- `/healthz`

同时把页面模板逐步替换成独立前端页面。

### 第二阶段：优先改造重交互页面

建议优先级：

1. `stock_detail.html`
2. `realtime_monitor.html`
3. `ai_assistant.html`
4. `backtest.html`
5. `screen.html`

这些页面最适合先做组件化和状态管理抽离。

### 第三阶段：再处理后台和认证页

后台页和认证页交互复杂度较低，可以晚于用户端核心分析页迁移。

## 4. Vue 化后建议保留的后端接口分组

### 股票与市场

- `/api/stocks`
- `/api/stocks/<ts_code>`
- `/api/stocks/<ts_code>/realtime`
- `/api/stocks/<ts_code>/history`
- `/api/stocks/<ts_code>/factors`
- `/api/stocks/<ts_code>/moneyflow`
- `/api/stocks/<ts_code>/cyq`
- `/api/stocks/<ts_code>/cyq_chips`
- `/api/market/overview`
- `/api/market/index/<ts_code>/kline`

### 分析与回测

- `/api/analysis/screen`
- `/api/analysis/backtest`
- `/api/user/records/analysis*`
- `/api/user/backtests*`

### AI

- `/api/ai/conversations*`
- `/api/ai/chat`
- `/api/ai/status`

### 监控与新闻

- `/api/monitor/*`
- `/api/news*`

## 5. 迁移前必须先做的准备

1. 为关键接口补充最小自动化测试，避免前端迁移时后端接口悄悄变形。
2. 整理统一响应结构和错误码约定。
3. 把页面内重复的格式化函数、请求封装、ECharts 初始化逻辑提取成公共模块。
4. 明确认证方式是否继续使用 Session Cookie，还是切换到显式 token。

## 6. 当前不建议做的事

- 不建议在还没整理接口契约时直接新建大型 Vue 仓库。
- 不建议把“旧 `ml_factor` 前端”当作当前 Vue 重构基础。
- 不建议同时做“前后端分离 + 后端业务重写 + 数据模型迁移”三件事。

## 7. 一句话结论

Vue 重构仍然值得做，但它应该被视为“当前 Flask 系统稳定后的下一阶段工程”，而不是对现有项目状态的描述。
