# 当前工作区项目结构说明

本文基于当前工作区实际存在的文件整理，时间点为 `2026-04-27`。

说明口径：

- 以"当前工作区实际存在的文件"为主，不把 `.venv`、`.git`、`__pycache__`、`logs/`、`data/`、`.codebuddy/`、`.matplotlib/` 这类运行期目录混入主结构。
- 单独补充 "Git 已记录但当前工作区已删除的历史文件"，避免把历史残留误认为当前主链路。
- "有效代码行数"按非空行、去掉纯注释行的近似统计；Markdown、图片、模型、数据库、SQL 文件不计入代码量。

## 一、项目是怎么连起来的

当前主链路是一个典型的 Flask 分层应用：

```
run.py / quick_start.py / run_system.py
  → app.create_app()
    → 注册蓝图 app/api、app/main、app/routes
    → 初始化扩展 db / Redis(可选降级) / Mail(可选)
    → 页面模板 app/templates 和静态资源 app/static
    → 业务层 app/services（13个服务）
    → ORM 模型层 app/models（22个模型）
    → 基础能力与外部数据接口 app/utils（25个工具模块）
    → 外部数据：MySQL / Tushare Pro / AkShare(新浪) / DeepSeek(LLM)
```

更细的调用链路：

- 页面访问走 `app/main/views.py`，直接返回 Jinja2 模板。
- 模板里的 JS 统一通过 `base.html` 里的 `apiRequest()` 调用 `/api/...`。
- `/api/...` 请求由 `app/api/*.py` 接收（5个API模块），再转到 `app/services/*.py`。
- 服务层再去查 `app/models/*.py` 对应的数据表，或通过 `app/utils/*.py` 访问外部数据源。
- 用户登录、个人中心、后台管理走 `app/routes/auth_routes.py` 和 `app/routes/admin_routes.py`。
- `app/__init__.py` 是装配中心：负责蓝图注册、Session 鉴权、CORS、限流(Sentry/Prometheus 可选)、错误页、`/healthz` 端点。
- 新增模块：Celery 异步任务队列（`celery_app.py` + `tasks.py`，已配置预留）、邮件服务（`email_service.py`，Resend SMTP）。

## 二、顶层目录总览

| 目录/文件 | 用途 |
|-----------|------|
| `app/` | Flask 主应用核心（MVC 全套） |
| `config.py` | 配置中心（数据库/Redis/LLM/邮件/安全） |
| `run.py` | 标准 Flask 启动入口（端口 5001） |
| `quick_start.py` | 轻量本地启动器 |
| `run_system.py` | 交互式系统管理入口（菜单式） |
| `runtime_encoding.py` | Windows UTF-8 编码环境修复 |
| `requirements*.txt` | 依赖管理（7个变体文件） |
| `gunicorn.conf.py` | Gunicorn 生产服务器配置 |
| `deploy/` | Nginx 反向代理 + systemd 服务配置示例 |
| `Dockerfile` | 两阶段构建的应用镜像定义（Python 3.11-slim） |
| `docker-compose.yml` | 生产环境 Docker Compose 编排（4容器：web/nginx/mysql/redis） |
| `docker-compose.dev.yml` | 开发环境 Docker Compose 编排（代码热挂载） |
| `scripts/` | 工具脚本（数据同步/诊断/数据库查看/初始化/迁移） |
| `docs/` | 项目文档、分析记录、归档资料 |
| `models/` | 预训练 ML 模型文件（.pkl） |
| `Data Dictionary/` | 数据字典（实时行情接口/新闻资讯接口说明） |
| `论文_第4章_系统实现/` | 论文配图（Drawio 架构图/类图/流程图，7个 .drawio） |
| `init.sql/` | 数据库 SQL 初始化脚本 |
| `_dump_docker_empty.sql` | Docker 空数据库导出（600KB） |
| `_local_data_dump.sql` | 本地完整数据备份（2.73GB） |
| `ssl-certs/` | SSL 证书（HTTPS 可选） |
| `stock_analysis.db` | 本地 SQLite 开发用数据库（500KB） |
| `start.bat / start.sh` | 一键启动脚本（Windows/Linux） |
| `start-docker.bat / stop-docker.bat` | Docker 启停脚本（Windows） |

## 三、当前工作区逐文件说明

### 1. 根目录文件

| 文件 | 大小 | 用途 |
|------|------|------|
| `.env` | 1.1KB | 本地环境变量（含敏感信息，不入 Git） |
| `.env.example` | 1.84KB | 环境变量示例模板 |
| `.gitignore` | 1.57KB | Git 忽略规则 |
| `.dockerignore` | 2.08KB | Docker 构建忽略文件规则 |
| `config.py` | 5.8KB | 配置类：DevelopmentConfig / ProductionConfig，含 DB/Redis/LLM/Mail/安全 |
| `run.py` | 535B | 主入口，创建 app 并监听 0.0.0.0:5001 |
| `quick_start.py` | 1.09KB | 轻量启动脚本 |
| `run_system.py` | 5.29KB | 交互式菜单管理器（检查依赖/初始化DB/展示结构） |
| `runtime_encoding.py` | 1.52KB | Windows 控制台 UTF-8 修复 |
| `gunicorn.conf.py` | 2.68KB | Gunicorn 配置（workers=CPU*2+1, timeout=180s, max_requests=5000） |
| `gen_doc.py` | 1.3KB | 文档生成辅助脚本 |
| `gen_md.py` | 3.96KB | Markdown 文档生成辅助脚本 |
| `README.md` | 3.05KB | 项目简介、快速启动、目录结构概览 |
| `requirements.txt` | 1.46KB | 主依赖清单（~40个包） |
| `requirements-base.txt` | 654B | 基础依赖 |
| `requirements-dev.txt` | 566B | 开发依赖 |
| `requirements-ml.txt` | 604B | 机器学习依赖（scikit-learn/xgboost/lightgbm） |
| `requirements-prod.txt` | 597B | 生产部署额外依赖 |
| `requirements_minimal.txt` | 500B | 最小化依赖集 |

### 2. `app/` 应用装配层

| 文件 | 大小 | 用途 |
|------|------|------|
| `app/__init__.py` | 11.83KB | **核心**。create_app() 工厂函数 + before_request 鉴权中间件 + CORS + 限流(Limiter) + Sentry + Prometheus + 健康检查 /healthz + 全局异常处理(404/500/429) + UTF-8 charset 强制 |
| `app/extensions.py` | 2.3KB | SQLAlchemy db 实例 + Redis client(可 None 降级) + Mail(Resend SMTP) |
| `app/celery_app.py` | 2.19KB | Celery 异步任务队列配置（预留扩展） |
| `app/tasks.py` | 2.8KB | Celery 定时任务定义（预留） |

### 3. `app/api/` JSON API 层（5个模块）

| 文件 | 大小 | 用途 |
|------|------|------|
| `app/api/__init__.py` | 188B | api_bp 蓝图注册（url_prefix=/api） |
| `app/api/stock_api.py` | 9.76KB | 股票相关 API：列表/详情/实时行情/K线历史/技术因子/资金流/筹码/行业地域/指数K线/市场概览/健康检查（17个端点） |
| `app/api/analysis_api.py` | 25.91KB | **最大API模块**。选股筛选 + 策略回测（内置 BacktestEngine 类，5种策略：MA/MACD/KDJ/RSI/BOLL） |
| `app/api/news_api.py` | 3.45KB | 新闻资讯 API（4源聚合：东财早餐/全球快讯/财联社电报/同花顺直播） |
| `app/api/realtime_monitor_api.py` | 3.65KB | 实时监控 API：仪表盘/涨跌排行/个股详情/分时走势/异动数据（6个端点） |
| `app/api/ai_assistant_api.py` | 13.62KB | AI 助手 API：会话 CRUD / SSE 流式聊天 / LLM 状态检测 |

### 4. `app/main/` 页面入口层

| 文件 | 大小 | 用途 |
|------|------|------|
| `app/main/__init__.py` | 117B | main_bp 蓝图注册（无前缀） |
| `app/main/views.py` | 1.32KB | 9 个页面路由：首页/股票列表/详情/分析/选股/回测/AI助手/新闻/实时监控 |

### 5. `app/routes/` 认证与后台页面层

| 文件 | 大小 | 用途 |
|------|------|------|
| `app/routes/auth_routes.py` | 22.59KB | **大型路由**。用户认证全流程：登录/注册/邮箱验证码/忘记密码/个人中心(资料+密码+邮箱)/自选股/分析记录/聊天记录/退出（579行） |
| `app/routes/admin_routes.py` | 14.91KB | 管理员后台：仪表盘(11项KPI)/用户CRUD(列表搜索+详情+启用停用封禁升降级删除+禁止操作自身)/操作日志(300条筛选)/数据中心/手动分钟线同步/系统自检(MySQL+Redis+Tushare+AkShare 四组件) |

### 6. `app/services/` 业务服务层（13个服务）

| 文件 | 大小 | 用途 |
|------|------|------|
| `app/services/stock_service.py` | 37.59KB | **核心股票服务**。列表搜索/详情/日线历史/技术指标计算(13种因子)/资金流/筹码分布/条件选股/行业地域 |
| `app/services/realtime_monitor_service.py` | 69.69KB | **最大服务文件**。实时监控数据拼装：报价/K线/信号/自选联动/分时数据(1/5/15/30/60min)/排行/仪表盘 |
| `app/services/akshare_service.py` | 38.67KB | AkShare/Sina 新浪数据适配器。实时行情快照/分钟K线/新闻爬虫(4源)/指数数据/市场统计，带代理诊断和 no_proxy 包装 |
| `app/services/market_overview_service.py` | 23.6KB | 市场概览服务。指数点位/涨跌家数/成交额TOP10/热门行业，Akshare→Tushare→本地缓存三级降级 |
| `app/services/backtest_engine.py` | 22.34KB | 回测引擎（预留高级接口）。注意：实际运行的回测逻辑在 `analysis_api.py` 内部类中 |
| `app/services/llm_service.py` | 19.23KB | LLM 统一调用层。DeepSeek（推荐）/ OpenAI 兼容 / Ollama 本地，SSE 流式输出 |
| `app/services/minute_data_sync_service.py` | 16.71KB | 分钟线数据同步服务。通过 Baostock 同步到 StockMinuteData 表 |
| `app/services/news_service.py` | 7.29KB | 新闻聚合服务。4源数据抓取（东财/财联社/同花顺），统一格式化输出 |
| `app/services/email_service.py` | 10.4KB | 邮件发送服务。Resend SMTP，用于邮箱验证码发送 |
| `app/services/ai_conversation_service.py` | 12.48KB | AI 会话管理。多轮对话持久化/上下文裁剪(12条消息/12000字符)/SSE 流式状态管理 |
| `app/services/user_activity_service.py` | 3.23KB | 用户行为写入。自选股/分析记录/聊天记录 |
| `app/services/system_log_service.py` | 831B | 系统日志落库（自动写入 action_type/message/user/status） |

### 7. `app/models/` ORM 模型层（22个模型）

| 文件 | 大小 | 模型 | 用途 |
|------|------|------|------|
| `app/models/user.py` | 3.9KB | User | 用户账户（username/email/password_hash/role/status/disabled/banned） |
| `app/models/user_activity.py` | 5.2KB | UserWatchlist / AnalysisRecord / UserChatHistory | 自选股/分析记录/Legacy聊天记录 |
| `app/models/ai_conversation.py` | 2.77KB | UserAiConversation / UserAiMessage | AI 会话 + 消息（结构化多轮对话） |
| `app/models/stock_basic.py` | 1KB | StockBasic | 股票基础信息（ts_code/name/industry/area/list_date） |
| `app/models/stock_daily_history.py` | 1.8KB | StockDailyHistory | 日线 OHLCV 行情 |
| `app/models/stock_daily_basic.py` | 2.9KB | StockDailyBasic | 每日指标（PE/PB/市值/换手率） |
| `app/models/stock_factor.py` | 4.55KB | StockFactor | 技术因子（MACD/KDJ/RSI/CCI/BOLL/WR/DMI/PSY/MTM/EMV/ROC/OBV/VR 共13种） |
| `app/models/stock_ma_data.py` | 2.06KB | StockMaData | 均线数据（MA5/10/20/30） |
| `app/models/stock_moneyflow.py` | 3.74KB | StockMoneyflow | 资金流向（主力/超大单/大单/中单/小单） |
| `app/models/stock_minute_data.py` | 6.35KB | StockMinuteData | 分钟级行情数据 |
| `app/models/stock_cyq_perf.py` | 1.95KB | StockCyqPerf | 筹码性能（成本分位/胜率） |
| `app/models/stock_cyq_chips.py` | 1.02KB | StockCyqChips | 筹码分布明细（各价位占比） |
| `app/models/stock_business.py` | 11.58KB | StockBusiness | 主营业务构成（58字段宽表，选股筛选用） |
| `app/models/stock_income_statement.py` | 7.7KB | StockIncomeStatement | 利润表（89字段，预留给基本面分析） |
| `app/models/stock_balance_sheet.py` | 12.2KB | StockBalanceSheet | 资产负债表（158字段，预留给基本面分析） |
| `app/models/stock_shock.py` | 1.04KB | StockShock | 异动波动信息 |
| `app/models/trading_signals.py` | 1.3KB | TradingSignals | 交易信号（**已定义未使用**，预留） |
| `app/models/portfolio_positions.py` | 1.62KB | PortfolioPositions | 持仓组合（**已定义未使用**，预留） |
| `app/models/risk_alerts.py` | 1.19KB | RiskAlerts | 风险预警（**已定义未使用**，预留） |
| `app/models/system_log.py` | 1.3KB | SystemLog | 操作日志 |

> 注：22 个模型中，17 个有实际的 API/页面读写调用，5 个（TradingSignals/PortfolioPositions/RiskAlerts/StockIncomeStatement/StockBalanceSheet）为预留扩展模型。

### 8. `app/utils/` 基础工具与数据同步辅助层（25个模块）

| 文件 | 用途 |
|------|------|
| `app/utils/logger.py` | Loguru 日志配置（文件+控制台双输出） |
| `app/utils/cache_utils.py` | Redis/内存双层缓存封装 |
| `app/utils/auth.py` | login_required / admin_required 装饰器 |
| `app/utils/api_helpers.py` | API 统一异常包装、统一响应结构（success/error） |
| `app/utils/db_utils.py` | MySQL 和 Tushare 初始化工具（含代理设置） |
| `app/utils/ma_calculator.py` | EMA/均线计算辅助函数 |
| `app/utils/baostock_daily.py` | Baostock 日线/分钟数据获取辅助 |
| `app/utils/stock_basic.py` | 股票基础信息抓取（Tushare→MySQL） |
| `app/utils/daily_basic.py` | 每日基础指标抓取 |
| `app/utils/daily_history_by_code.py` | 按股票代码抓取日线历史 |
| `app/utils/daily_history_by_date.py` | 按日期抓取日线历史 |
| `app/utils/stk_factor.py` | 技术因子抓取/计算 |
| `app/utils/moneyflow.py` | 资金流向抓取（Tushare） |
| `app/utils/moneyflow_ths.py` | 同花顺口径资金流 |
| `app/utils/cyq_perf.py` | 筹码分布数据处理 |
| `app/utils/min5.py` | 5 分钟线抓取 |
| `app/utils/min15.py` | 15 分钟线抓取 |
| `app/utils/min30.py` | 30 分钟线抓取 |
| `app/utils/min60.py` | 60 分钟线抓取 |
| `app/utils/income_statement.py` | 利润表数据抓取/写入 |
| `app/utils/balance_sheet.py` | 资产负债表数据抓取/写入 |
| `app/utils/cash_flow.py` | 现金流量表数据抓取/写入 |
| `app/utils/stock_company.py` | 公司信息抓取 |
| `app/utils/trade_calendar.py` | 交易日历抓取 |

### 9. `app/templates/` Jinja2 HTML 模板（24个文件）

#### 用户端页面（9个）

| 文件 | 大小 | 说明 |
|------|------|------|
| `app/templates/base.html` | 11.98KB | **全局基础模板**。导航栏/页脚/CSS/JS 引入/apiRequest() 函数/Bootstrap 主题 |
| `app/templates/index.html` | 35.91KB | 首页。市场情绪（三大指数卡片）/涨跌统计/行业板块热力图/成交额TOP10/快捷入口 |
| `app/templates/stocks.html` | 6.3KB | 股票列表。关键字搜索+行业/地域下拉筛选+分页表格 |
| `app/templates/stock_detail.html` | 73.65KB | **最复杂页面**。个股详情：行情概览/日K线图(ECharts蜡烛图+MA均线)/技术指标(13种切换)/资金流向(分层柱状图)/筹码分布/分时走势(1/5/15/30/60min)，共 6 个 Tab |
| `app/templates/screen.html` | 22.54KB | 条件选股。价格区间/涨跌幅/成交量/PE-PB/市值/行业地域多维组合筛选 |
| `app/templates/backtest.html` | 34.62KB | 策略回测。5种策略选择(MA/MACD/KDJ/RSI/BOLL)+参数设置+ECharts 收益曲线+绩效统计卡片 |
| `app/templates/ai_assistant.html` | 39.94KB | AI 助手。左侧会话列表+右侧对话流+SSE 打字机效果+预设快捷问题 |
| `app/templates/news.html` | 9.99KB | 新闻资讯。4源Tab切换（财经早餐/全球快讯/财联社电报/同花顺直播） |
| `app/templates/realtime_monitor.html` | 62.77KB | **第二大页面**。实时监控看板：自选股矩阵/涨跌排行/分时走势嵌入/成交量预警 |
| `app/templates/analysis.html` | 52.79KB | 分析页（已重定向到 stocks，保留兼容） |

#### 认证页面（4个）

| 文件 | 大小 | 说明 |
|------|------|------|
| `app/templates/auth/login.html` | 2.78KB | 登录页（用户名/邮箱+密码+记住我） |
| `app/templates/auth/register.html` | 5.3KB | 注册页（用户名+邮箱+密码+确认密码+验证码） |
| `app/templates/auth/forgot_password.html` | 6.04KB | 找回密码（邮箱→验证码→新密码三步流程） |
| `app/templates/auth/profile.html` | 20.4KB | 个人中心（基本信息/密码修改/邮箱变更/自选股管理/分析记录/聊天记录，4个 Tab） |

#### 管理后台页面（7个）

| 文件 | 大小 | 说明 |
|------|------|------|
| `app/templates/admin/login.html` | 1.57KB | 管理员独立登录页 |
| `app/templates/admin/dashboard.html` | 10.59KB | 仪表盘（11项 KPI 卡片+最近 12 条日志时间线） |
| `app/templates/admin/users.html` | 8.69KB | 用户列表（表格+搜索+启用/停用/封禁/升降级/删除按钮） |
| `app/templates/admin/user_detail.html` | 5.26KB | 用户详情（基本信息+3个子Tab：自选股/分析记录/聊天记录） |
| `app/templates/admin/logs.html` | 4.97KB | 操作日志（类型+状态筛选，最新300条） |
| `app/templates/admin/data.html` | 3.78KB | 数据中心（数据统计+手动同步表单） |
| `app/templates/admin/health_check.html` | 10.96KB | 系统自检（MySQL/Redis/Tushare/AkShare 四组件连通性一键检测） |

#### 错误页面（3个）

| 文件 | 说明 |
|------|------|
| `app/templates/errors/404.html` | 404 Not Found |
| `app/templates/errors/500.html` | 500 Internal Error |
| `app/templates/errors/429.html` | 429 Rate Limited |

### 10. `app/static/` 静态资源

| 文件 | 大小 | 说明 |
|------|------|------|
| `app/static/css/financial-theme.css` | 13.91KB | 全站金融主题样式（深色导航/涨跌色/卡片阴影） |
| `app/static/css/responsive-financial.css` | 17.41KB | 响应式布局适配（平板/手机断点） |
| `app/static/css/account-admin.css` | 22.83KB | 个人中心与管理后台专用样式 |
| `app/static/css/mobile.css` | 12.27KB | 移动端专用样式覆盖 |
| `app/static/js/mobile.js` | 18.4KB | 移动端交互逻辑（侧栏折叠/触摸优化） |
| `app/static/logo.png` | 516KB | 系统 Logo 图片 |
| `app/static/vendor/echarts.min.js` | 1MB | ECharts 图表库（本地托管） |
| `app/static/vendor/axios.min.js` | 31.2KB | Axios HTTP 客户端（本地托管） |

### 11. `scripts/` 工具脚本

| 文件 | 大小 | 说明 |
|------|------|------|
| `scripts/sync_tushare_data.py` | 43.48KB | **最大脚本**。大批量 Tushare 数据同步主脚本（全量股票/日线/基本面/财务/资金流等） |
| `scripts/daily_auto_update.py` | 17.47KB | 每日自动更新任务（日线/因子/资金流/宽表的增量同步调度） |
| `scripts/backfill_factors_v2.py` | 16.92KB | V2 版技术因子补算脚本（基于日线历史补算并回填 stock_factor 表） |
| `scripts/backfill_factors.py` | 10.68KB | V1 版技术因子补算（被 v2 替代但保留参考） |
| `scripts/data_health_check.py` | 13.56KB | 数据健康度巡检（各表数据完整性/最新日期/异常检测） |
| `scripts/migrate_v20260427_crud_fix.py` | 5.72KB | CRUD 修复迁移脚本（2026-04-27 审计后修复） |
| `scripts/add_db_indexes.py` | 5.13KB | 数据库索引优化脚本 |
| `scripts/db_tools/database_explorer.py` | 23.31KB | 数据库探索工具（交互式查看表结构和样例数据） |
| `scripts/db_tools/db_viewer.py` | 12.85KB | 数据库查看器（Web UI 形式的 DB 浏览器） |
| `scripts/setup/create_risk_tables.py` | 5.11KB | 创建风险预警相关表及示例数据 |
| `scripts/setup/create_simple_demo_model.py` | 7.05KB | 生成简单演示模型文件 |
| `scripts/setup/create_simple_prediction_service.py` | 4.94KB | 生成简单预测服务原型 |
| `scripts/setup/create_working_model.py` | 2.55KB | 生成可工作的模型示例 |
| `scripts/diagnostics/tushare_connection_check.py` | 3.42KB | Tushare 连接诊断脚本 |
| `scripts/diagnostics/market_overview_smoke.py` | 185B | 市场概览快速烟雾检查 |
| `scripts/diagnostics/market_overview_item_errors.py` | 282B | 市场概览返回项错误检查 |

### 12. `deploy/` 部署文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `deploy/nginx.conf` | 2.48KB | Nginx 反向代理配置（SSE 关闭缓冲/静态资源 30 天缓存/安全头/HTTPS 预留） |
| `deploy/stock-analysis.service` | 1.8KB | systemd 服务单元配置示例 |

### 13. `docs/` 文档总览

| 文件/目录 | 说明 | 更新状态 |
|----------|------|---------|
| `docs/guides/CURRENT_WORKSPACE_STRUCTURE.md` | 当前这份文档 | **本次更新** |
| `docs/guides/PROJECT_STRUCTURE.md` | 项目结构简要说明 | 需要更新 |
| `docs/guides/DATABASE_TOOLS_README.md` | 数据库工具使用说明 | 当前有效 |
| `docs/guides/database.md` | 数据库建表脚本 | 较旧（仅包含部分表 DDL） |
| `docs/PROJECT_FULL_GUIDE.md` | **项目完整指南**（~1060行） | ✅ 2026-04-27 最新 |
| `docs/SYSTEM_CRUD_AUDIT_REPORT.md` | CRUD 审计报告（~507行） | ✅ 2026-04-27 最新 |
| `docs/VUE_REFACTOR_PLAN.md` | Vue3 前端重构计划（~1184行） | 概念性文档，仍然有效 |
| `docs/README_balance_sheet.md` | 资产负债表工具说明 | ⚠️ 路径过时 |
| `docs/README_cash_flow.md` | 现金流量表工具说明 | ⚠️ 路径过时 |
| `docs/README_income_statement.md` | 利润表工具说明 | ⚠️ 路径过时 |
| `docs/analysis/CURRENT_PROJECT_REVIEW.md` | 项目审查记录 | 历史参考 |
| `docs/analysis/DEVELOPMENT_SUMMARY.md` | 开发总结 | ⚠️ 内容严重过时（仍描述早期版本） |
| `docs/reports/operation_log.md` | 操作日志 | 仅到 2025-01 |
| `docs/archive/ml_factor/` | 旧版多因子归档（7个文件） | 历史资料，不再代表当前实现 |

### 14. 其他重要目录

| 目录 | 说明 |
|------|------|
| `Data Dictionary/` | 数据字典（实时行情接口说明 24KB + 新闻资讯接口说明 20KB） |
| `论文_第4章_系统实现/diagrams/` | 论文配图（7个 .drawio 文件：总体框架/类图/登录时序/注册时序/AI时序/回测流程/管理架构） |
| `models/` | ML 模型资产（demo_model_v2.pkl 3.9MB + scaler.pkl） |
| `init.sql/` | 数据库初始化 SQL 脚本目录 |
| `ssl-certs/` | SSL 证书存放目录 |

## 四、关键运行链路节点

以下文件是系统运行的核心枢纽（按重要性排序）：

| 优先级 | 文件 | 角色 |
|--------|------|------|
| P0 | `app/__init__.py` | 应用工厂 + 全部中间件（343行） |
| P0 | `config.py` | 所有配置的中心来源 |
| P0 | `run.py` | 启动入口 |
| P0 | `app/main/views.py` | 页面路由分发 |
| P0 | `app/api/analysis_api.py` | 选股+回测核心逻辑（含内置 BacktestEngine） |
| P0 | `app/services/stock_service.py` | 股票数据主服务（技术因子计算在此） |
| P0 | `app/services/realtime_monitor_service.py` | 实时监控主服务（最大服务文件） |
| P0 | `app/services/akshare_service.py` | 外部数据适配主入口 |
| P0 | `app/services/llm_service.py` | AI 能力核心 |
| P0 | `app/templates/base.html` | 全局前端壳 + apiRequest() |
| P0 | `app/templates/stock_detail.html` | 最复杂页面（核心功能展示窗口） |
| P1 | `app/routes/auth_routes.py` | 用户认证全流程 |
| P1 | `app/routes/admin_routes.py` | 管理后台全部功能 |
| P1 | `app/services/ai_conversation_service.py` | AI 多轮对话管理 |
| P1 | `app/extensions.py` | db/redis/mail 三大扩展 |
| P2 | `app/models/__init__.py` | 22 个模型的统一导入 |
| P2 | `app/services/news_service.py` | 新闻聚合服务 |
| P2 | `app/services/email_service.py` | 验证码邮件发送 |
| P2 | `scripts/daily_auto_update.py` | 每日数据自动更新调度 |

## 五、Git 中存在但工作区已删除的历史文件

根据 git status，以下内容仍在 Git 记录中但工作区已清理：

- `docs/guides/data_requirements_for_real_training.md` — 已从工作区删除
- `Microsoft/Windows/PowerShell/ModuleAnalysisCache` — PowerShell 缓存，不属于业务代码
- 历史残留：旧的一次性脚本、测试脚本、编辑器恢复文件等已在之前的整理中清除

这些不应再视为当前运行主线的一部分。

## 六、有效代码行数统计

统计口径：仅统计当前工作区实际存在的代码/配置文件，按非空行、去掉纯注释行近似计算。

### 总体统计

| 语言 | 文件数 | 近似行数 | 说明 |
|------|-------|---------|------|
| Python (.py) | 98 | ~14,500 | 含 app/ + scripts/ + 根目录 |
| HTML (.html) | 24 | ~4,800 | 含 24 个模板文件 |
| CSS (.css) | 4 | ~670 | 4 个样式文件 |
| JavaScript (.js) | 3 | ~480 | mobile.js + vendor 库不计自定义代码 |
| SQL (.sql) | 3 | 变化大 | _local_data_dump.sql 2.73GB 为数据备份 |
| Markdown (.md) | 24 | ~2,200 | 文档文件 |
| 配置/其他 | ~15 | ~600 | yml/conf/bat/sh 等 |
| **合计** | **~171** | **~23,250** | 不含 vendor 库和 SQL 备份数据 |

### 代码量 Top 10 文件

| 排名 | 文件 | 大小 | 说明 |
|------|------|------|------|
| 1 | `app/services/realtime_monitor_service.py` | 69.69KB | 实时监控（最重服务） |
| 2 | `app/templates/stock_detail.html` | 73.65KB | 个股详情（最重页面） |
| 3 | `app/templates/realtime_monitor.html` | 62.77KB | 实时监控页 |
| 4 | `app/services/akshare_service.py` | 38.67KB | 数据适配器 |
| 5 | `app/services/stock_service.py` | 37.59KB | 股票主服务 |
| 6 | `app/templates/analysis.html` | 52.79KB | 分析页 |
| 7 | `app/templates/ai_assistant.html` | 39.94KB | AI 助手页 |
| 8 | `app/templates/backtest.html` | 34.62KB | 回测页 |
| 9 | `app/api/analysis_api.py` | 25.91KB | 选股回测 API（最重 API） |
| 10 | `scripts/sync_tushare_data.py` | 43.48KB | 数据同步主脚本 |

### 一个有用的结论

项目的"重心"非常明确：

- **后端主逻辑**集中在 `app/services/`，尤其是 `realtime_monitor_service`(69KB)、`akshare_service`(38KB)、`stock_service`(37KB)
- **前端复杂度**主要集中在几个大模板：`stock_detail`(73KB)、`realtime_monitor`(62KB)、`analysis`(52KB)、`ai_assistant`(39KB)
- 如果后续要做重构，优先拆分"重模板 + 重服务文件"收益最大
