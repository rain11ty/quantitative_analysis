# 数据库说明

> 更新日期：`2026-04-28`
> 说明口径：以 `app/models/` 中的 ORM 模型和当前脚本路径为准

## 1. 当前数据库角色

项目当前主要依赖 MySQL 作为业务主库，承担：

- 用户与管理员数据
- AI 会话数据
- 股票基础信息与历史行情
- 技术因子、资金流、筹码、分钟线
- 回测结果、系统日志

Redis 只承担缓存，不作为业务真源。

## 2. 连接配置

连接参数来自 `.env`：

- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `DB_CHARSET`

ORM 由 `Flask-SQLAlchemy` 统一装配，应用入口在 `app/extensions.py` 和 `config.py`。

## 3. ORM 表总览

当前导出的 `24` 个 ORM 模型及其表名如下。

### 3.1 用户与行为

| 模型 | 表名 | 说明 |
|---|---|---|
| `User` | `user_account` | 用户账号 |
| `UserWatchlist` | `user_watchlist` | 自选股 |
| `UserAnalysisRecord` | `user_analysis_record` | 分析记录 |
| `UserChatHistory` | `user_chat_history` | Legacy 聊天记录 |
| `UserBacktestResult` | `user_backtest_result` | 回测结果 |

### 3.2 AI 会话

| 模型 | 表名 | 说明 |
|---|---|---|
| `UserAiConversation` | `user_ai_conversation` | 会话头信息 |
| `UserAiMessage` | `user_ai_message` | 会话消息 |

### 3.3 股票基础与行情

| 模型 | 表名 | 说明 |
|---|---|---|
| `StockBasic` | `stock_basic` | 股票基础信息 |
| `StockDailyHistory` | `stock_daily_history` | 日线行情 |
| `StockDailyBasic` | `stock_daily_basic` | 每日估值/换手等 |
| `StockMinuteData` | `stock_minute_data` | 分钟线行情 |
| `StockBusiness` | `stock_business` | 主营业务宽表 |
| `StockShock` | `stock_shock` | 异动数据 |

### 3.4 技术分析与衍生数据

| 模型 | 表名 | 说明 |
|---|---|---|
| `StockFactor` | `stock_factor` | 技术因子 |
| `StockMaData` | `stock_ma_data` | 均线数据 |
| `StockMoneyflow` | `stock_moneyflow` | 资金流向 |
| `StockCyqPerf` | `stock_cyq_perf` | 筹码性能 |
| `StockCyqChips` | `stock_cyq_chips` | 筹码分布明细 |

### 3.5 财务与预留扩展

| 模型 | 表名 | 当前状态 |
|---|---|---|
| `StockIncomeStatement` | `stock_income_statement` | 数据层预留，未进入页面/API 主链路 |
| `StockBalanceSheet` | `stock_balance_sheet` | 数据层预留，未进入页面/API 主链路 |
| `TradingSignals` | `trading_signals` | 预留扩展 |
| `PortfolioPositions` | `portfolio_positions` | 预留扩展 |
| `RiskAlerts` | `risk_alerts` | 预留扩展 |

### 3.6 系统表

| 模型 | 表名 | 说明 |
|---|---|---|
| `SystemLog` | `system_log` | 系统操作日志 |

## 4. 一个容易混淆的点

仓库里还有一个脚本式数据表：

- `stock_cash_flow`

它来自 `app/utils/cash_flow.py`，当前：

- 不是 ORM 模型
- 不在 `app/models/__init__.py` 中导出
- 不在页面或 API 主链路中使用

因此，它属于“脚本生成的辅助数据表”，不属于当前正式 ORM 体系。

## 5. 当前主链路实际会频繁读写哪些表

### 高频读取

- `stock_basic`
- `stock_daily_history`
- `stock_daily_basic`
- `stock_factor`
- `stock_moneyflow`
- `stock_cyq_perf`
- `stock_cyq_chips`
- `stock_minute_data`
- `stock_shock`

### 业务写入

- `user_account`
- `user_watchlist`
- `user_analysis_record`
- `user_backtest_result`
- `user_ai_conversation`
- `user_ai_message`
- `user_chat_history`
- `system_log`

## 6. 对维护者的建议

1. 如果是 Web 功能开发，优先关注 `user_*`、`stock_*`、`system_log` 这些主链路表。
2. 如果是财务数据整理，不要默认它已经纳入主站功能。
3. 如果需要查库排障，优先使用 `scripts/db_tools/` 中的工具，而不是直接在业务代码里临时打印 SQL。
