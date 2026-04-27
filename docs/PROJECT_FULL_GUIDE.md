# A 股量化分析系统完整指南

> 更新日期：`2026-04-28`
> 当前主线：Flask + Jinja2 + JSON API 的一体化 Web 应用

## 1. 项目定位

这个仓库当前承载的是一个面向 A 股场景的量化分析 Web 系统，重点不在“多因子研究平台”，而在“可直接访问和演示的股票分析产品”。

当前主线能力包括：

- 市场概览与指数看板
- 股票列表、搜索与详情分析
- 技术因子、资金流、筹码分布
- 条件选股
- 策略回测与结果留存
- 实时监控与异常波动
- AI 助手会话
- 用户中心与管理员后台

## 2. 当前架构

### 2.1 运行入口

项目提供三个常用入口：

- `run.py`：标准启动入口，默认监听 `0.0.0.0:5001`
- `quick_start.py`：本地快速启动器
- `run_system.py`：带菜单的开发维护入口

三者最终都会进入：

```text
app.create_app()
  -> 初始化 SQLAlchemy
  -> 初始化 Redis 或降级内存缓存
  -> 初始化邮件服务
  -> 注册 Blueprint
  -> 注册 /healthz 与错误处理
```

### 2.2 分层结构

```text
浏览器
  -> Jinja2 页面
  -> 页面内 JS 调用 /api/*

Flask 应用
  -> app/main      页面路由
  -> app/api       JSON API
  -> app/routes    认证与管理后台
  -> app/services  业务逻辑
  -> app/models    ORM 模型
  -> app/utils     数据接入、缓存、日志、同步辅助
```

### 2.3 Blueprint 划分

| Blueprint | 前缀 | 作用 |
|---|---|---|
| `main_bp` | `/` | 用户端页面渲染 |
| `api_bp` | `/api` | 股票、分析、AI、新闻、监控接口 |
| `auth_routes` | `/auth` | 登录、注册、找回密码、个人中心 |
| `admin_routes` | `/admin` | 管理后台、用户管理、日志、数据中心 |

## 3. 功能地图

### 3.1 用户端页面

当前有效页面一共 `9` 个：

| 页面 | 路径 | 说明 |
|---|---|---|
| 首页 | `/` | 市场概览、指数卡片、行业热度、成交额排行 |
| 股票列表 | `/stocks` | 搜索、行业/地域筛选、分页列表 |
| 股票详情 | `/stock/<ts_code>` | K 线、技术因子、资金流、筹码、分时 |
| 选股筛选 | `/screen` | 条件筛选与结果列表 |
| 回测 | `/backtest` | 五类策略回测 |
| AI 助手 | `/ai-assistant` | 会话列表、流式问答 |
| 新闻 | `/news` | 财经早餐与全球快讯聚合 |
| 实时监控 | `/monitor` | 看板、排行、分时、异动 |
| 分析页兼容入口 | `/analysis` | 已退役，当前重定向到 `/stocks` |

### 3.2 API 模块

当前 `app/api/` 有 `5` 个模块、`40` 条路由声明：

- `stock_api.py`
  - 股票列表、详情、实时行情、历史、技术因子、资金流、筹码、行业/地域、自选股
- `analysis_api.py`
  - 分析记录、回测历史、自选股编辑、选股、策略回测
- `news_api.py`
  - 新闻聚合、财经早餐、全球快讯
- `realtime_monitor_api.py`
  - 监控面板、涨跌排行、个股详情、分时、异动
- `ai_assistant_api.py`
  - 会话 CRUD、消息列表、流式聊天、AI 状态

### 3.3 认证与后台

`app/routes/` 当前是两块独立能力：

- `auth_routes.py`
  - 登录、注册、验证码、找回密码
  - 个人资料、密码、邮箱修改
  - 个人中心中的自选股、分析记录、聊天记录入口
- `admin_routes.py`
  - 后台登录
  - 用户分页列表、详情、状态切换、角色调整、删除
  - 日志列表
  - 数据中心与单股分钟线同步
  - 系统自检

## 4. 数据与模型

### 4.1 ORM 模型现状

当前 `app/models/__init__.py` 导出了 `24` 个模型：

- 用户体系：`User`、`UserWatchlist`、`UserAnalysisRecord`、`UserChatHistory`、`UserBacktestResult`
- AI 会话：`UserAiConversation`、`UserAiMessage`
- 行情与分析：`StockBasic`、`StockDailyHistory`、`StockDailyBasic`、`StockFactor`、`StockMaData`、`StockMoneyflow`、`StockCyqPerf`、`StockCyqChips`、`StockMinuteData`、`StockBusiness`、`StockShock`
- 财务预留：`StockIncomeStatement`、`StockBalanceSheet`
- 系统与扩展：`SystemLog`、`TradingSignals`、`PortfolioPositions`、`RiskAlerts`

### 4.2 活跃与预留边界

当前真正处于主链路中的主要是：

- 用户、会话、自选股、分析记录、回测记录
- 股票基础信息、日线、分钟线、因子、资金流、筹码、异动
- 系统日志

偏预留或非主链路的部分：

- `StockIncomeStatement`
- `StockBalanceSheet`
- `TradingSignals`
- `PortfolioPositions`
- `RiskAlerts`

另外，`app/utils/cash_flow.py` 会创建并写入 `stock_cash_flow`，但它目前不是 ORM 模型，也不在页面/API 主链路内。

## 5. 外部依赖与集成

### 5.1 基础依赖

- MySQL：主业务数据库
- Redis：可选缓存；失败时自动降级为进程内内存缓存
- Loguru：日志输出
- Flask-Limiter：生产限流
- 可选监控：Sentry、Prometheus

### 5.2 金融数据源

- Tushare Pro：股票基础数据、日线、指标、部分历史行情
- AkShare / 新浪快照：市场概览、实时排行、新闻资讯、部分分时/快照
- 本地数据库缓存：市场概览与指数 K 线的最终兜底来源

### 5.3 AI 与邮件

- LLM：`deepseek`、`openai`、`ollama` 三类兼容配置
- 邮件：Resend SMTP 风格配置，由 `email_service.py` 负责验证码流程

## 6. 当前文档应该怎样理解

为了避免继续把“历史材料”“当前实现”“未来规划”混在一起，建议按下面的方式阅读：

- 总体理解项目：看本文
- 看目录和工作区边界：看 `docs/guides/PROJECT_STRUCTURE.md`
- 看细化结构盘点：看 `docs/guides/CURRENT_WORKSPACE_STRUCTURE.md`
- 看数据库现状：看 `docs/guides/database.md`
- 看当前审查结论：看 `docs/analysis/CURRENT_PROJECT_REVIEW.md`
- 看现阶段 CRUD 现状：看 `docs/SYSTEM_CRUD_AUDIT_REPORT.md`
- 看未来前后端拆分方向：看 `docs/VUE_REFACTOR_PLAN.md`

## 7. 当前已确认的边界与限制

- 旧 `ml_factor` 文档不再代表当前系统，且空归档文件已清理。
- `/analysis` 页面不是独立分析页，而是兼容性重定向。
- AI 会话已经有结构化新表，但仍兼容写入 `user_chat_history`。
- 高级版 `app/services/backtest_engine.py` 仍是预留接口，实际回测执行器在 `app/api/analysis_api.py`。
- 金融三表脚本仍是脚本式数据工具，不是页面已上线功能。
