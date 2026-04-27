# A股量化分析系统 — 项目完整说明文档

> **项目名称**：基于大语言模型与Flask的A股量化分析系统  
> **版本**：v1.0.0 | **最后更新**：2026-04-27  
> **技术栈**：Flask + SQLAlchemy + MySQL + Redis + ECharts + DeepSeek(LLM) + Tushare/AkShare  

---

## 一、项目目的与背景

### 1.1 解决的问题

针对**股票投资新手**在量化分析过程中面临的三大核心痛点：

| 痛点 | 具体表现 |
|------|---------|
| **专业知识不足** | 不懂K线形态、技术指标含义、量化策略原理 |
| **工具操作复杂** | 专业终端（Wind/Choice）价格昂贵且学习曲线陡峭 |
| **信息获取渠道分散** | 行情数据、新闻资讯、财务指标散落在不同平台，难以整合 |

### 1.2 建设目标

构建一个 **"一站式、低门槛、智能化"** 的A股量化分析平台：
- **零基础友好**：图形化界面，无需编程即可使用专业级分析工具
- **数据驱动**：集成多源金融数据（Tushare Pro + AkShare），覆盖历史行情/实时快照/财务数据
- **AI赋能**：接入DeepSeek大语言模型，支持自然语言问答，降低专业知识壁垒
- **可验证性**：内置5种经典量化策略回测引擎，用户可自定义参数验证策略有效性
- **工程规范**：完整的用户体系 + 后台管理 + 容器化部署，具备生产级代码质量

---

## 二、系统总体架构

### 2.1 架构模式

采用 **B/S（浏览器/服务器）架构** + **MVC（Model-View-Controller）设计模式**，前后端**不分离**（服务端渲染Jinja2模板）。

```
┌─────────────────────────────────────────────────────────────────┐
│                        浏览器 (Browser)                          │
│              Jinja2渲染HTML + ECharts图表 + Bootstrap UI         │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Web Server                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               控制层 (Controller / Routes)                 │   │
│  │  main_bp(页面) │ api_bp(数据接口) │ auth_bp(认证) │ admin_bp  │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │                  业务服务层 (Service Layer)                 │   │
│  │  stock │ akshare │ backtest │ llm │ news │ realtime_monitor │   │
│  │  email │ market_overview │ minute_sync │ system_log │ user   │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │                数据访问层 (Data Access / ORM)               │   │
│  │              SQLAlchemy — 22个业务模型                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌────────────┐  ┌────────────┐  ┌────────────┐
       │   MySQL    │  │   Redis    │  │  外部API   │
       │  (主数据库) │  │ (缓存层)   │  │Tushare/AkS │
       │  22张表     │  │(可选降级)  │  │hare/DeepSeek│
       └────────────┘  └────────────┘  └────────────┘
```

### 2.2 蓝图(Blueprint)划分

系统通过4个Blueprint实现功能隔离和权限控制：

| Blueprint | URL前缀 | 职责 | 目标用户 |
|-----------|---------|------|---------|
| **main_bp** | `/`（无前缀） | 页面路由渲染 | 所有用户（含未登录访客） |
| **api_bp** | `/api/*` | JSON数据接口 | 前端AJAX调用 / 公开白名单接口 |
| **auth_bp** | `/auth/*` | 登录/注册/个人中心 | 注册用户 |
| **admin_bp** | `/admin/*` | 后台管理面板 | 仅管理员(`role='admin'`) |

### 2.3 权限控制机制

采用 **Session + RBAC（基于角色的访问控制）** 双重机制：

```
请求进入 → before_request 中间件
    │
    ├─ OPTIONS预检? → 直接放行
    ├─ Session有user_id? → 加载User到g.current_user
    │   └─ 用户disabled/banned? → 清除session, 拦截返回403
    │
    ├─ 在PUBLIC_ENDPOINTS白名单中? → 放行（含大部分行情API）
    │
    ├─ 未登录? → 401 重定向到登录页
    │
    └─ 是/admin/*路径 且 非管理员? → 403 拒绝/重定向首页
```

**公开白名单**涵盖：首页、股票列表、个股详情、K线/技术指标/资金流/筹码分布API、实时监控、新闻列表等——**大部分核心功能对未登录访客开放**。

---

## 三、功能模块详解

### 3.1 用户端功能（8大模块）

#### 模块1：首页与市场概览

| 功能 | 说明 |
|------|------|
| 市场大盘指数 | 上证/深证/创业板指实时点位、涨跌幅 |
| 涨跌统计 | 今日上涨/下跌/平盘家数 |
| 成交额排行 | 成交量TOP10股票 |
| 热门行业 | 行业板块涨跌幅排名 |
| 市场健康检查 | 数据源连通性状态（Tushare/AkShare/MySQL/Redis） |

**路由**：`GET /` → `templates/index.html`

---

#### 模块2：股票列表与搜索

| 功能 | 说明 |
|------|------|
| A股全量列表 | 展示5000+只A股基础信息（代码/名称/行业/上市日期） |
| 关键字搜索 | 支持股票代码、名称模糊匹配 |
| 行业筛选 | 按一级行业分类过滤 |
| 地域筛选 | 按省份/城市过滤 |
| 分页加载 | 默认20条/页，最大100条 |

**路由**：`GET /stocks` → `templates/stocks.html`  
**API**：`GET /api/stocks?page=&keyword=&industry=&area=`

---

#### 模块3：个股详情分析（核心模块）

这是系统的**最核心页面**，单个页面聚合了多维度的股票数据分析能力：

| 子功能 | 数据来源 | 可视化方式 |
|--------|---------|-----------|
| **基本行情** | Tushare Pro | 实时价格/涨跌幅/成交量/市值/PE/PB |
| **日K线图** | StockDailyHistory | ECharts Candlestick（支持MA均线叠加） |
| **技术指标** | StockFactor（13种指标） | ECharts折线图，支持MACD/KDJ/RSI/CCI/BOLL/WR/DMI/PSY/MTM/EMV/ROC/OBV/VR |
| **资金流向** | StockMoneyflow | 主力/超大单/大单/中单/小单资金流入流出柱状图 |
| **筹码分布** | StockCyqPerf + StockCyqChips | 成本分布柱状图 +获利盘比例 |
| **分时走势** | AkShare 新浪分钟线 | 价格线+均价线+昨收基准线+成交量柱状图（支持1/5/15/30/60分钟粒度） |

**路由**：`GET /stock/<ts_code>` → `templates/stock_detail.html`  
**关键API集合**：
- `GET /api/stock/detail/<ts_code>`
- `GET /api/stock/history/<ts_code>`
- `GET /api/stock/factors/<ts_code>`
- `GET /api/stock/moneyflow/<ts_code>`
- `GET /api/stock/cyq/<ts_code>`
- `GET /api/monitor/intraday/<ts_code>?granularity=`

---

#### 模块4：选股筛选

| 功能 | 说明 |
|------|------|
| 多条件组合筛选 | 价格区间、涨跌幅范围、成交量阈值、换手率范围、PE/PB区间、市值范围、行业/地域交叉筛选 |
| 实时结果展示 | 筛选结果以表格形式展示，点击可进入详情页 |

**路由**：`GET /screen` → `templates/screen.html`

---

#### 模块5：策略回测

内置 **5种经典量化策略** 的回测引擎：

| # | 策略名称 | 核心逻辑 |
|---|---------|---------|
| 1 | **均线交叉(MA)** | 短期均线上穿/下穿长期均线产生买卖信号 |
| 2 | **MACD** | DIF与DEA金叉/死叉 + 柱状图方向判断 |
| 3 | **KDJ** | K值与D值的超买超卖区域交叉信号 |
| 4 | **RSI** | RSI指标的超买(>70)/超卖(<30)反转信号 |
| 5 | **布林带(BOLL)** | 价格突破上轨/下轨的回归交易信号 |

每个回测报告包含：
- 累计收益曲线（ECharts）
- 最大回撤、夏普比率、胜率
- 买卖信号标注在K线图上
- 年化收益率、盈亏比

**路由**：`GET /backtest` → `templates/backtest.html`

---

#### 模块6：实时行情监控

| 功能 | 说明 |
|------|------|
| 监控仪表盘 | 自选股票池的实时价格变动矩阵 |
| 涨跌榜排行 | 涨幅TOP10 / 跌幅TOP10 实时刷新 |
| 分时数据 | 单只股票当日分钟级行情走势 |
| 成交量预警 | 异常放量提醒 |

**路由**：`GET /monitor` → `templates/realtime_monitor.html`  
**数据源**：新浪财经HTTP API（直连，绕过代理，延迟约0.5秒）

---

#### 模块7：AI智能助手

| 功能 | 说明 |
|------|------|
| 自然语言问答 | 用户用中文提问股票相关问题 |
| SSE流式输出 | DeepSeek API流式响应，打字机效果逐字显示 |
| 多轮对话记忆 | 基于会话ID维护上下文连续性 |
| 金融知识库 | 内置A股市场规则、技术指标解释、量化策略原理等Prompt上下文 |

**支持的提问示例**：
- "什么是MACD指标？怎么用它来判断买卖点？"
- "帮我分析一下贵州茅台最近的技术面"
- "均线交叉策略的优缺点是什么？"

**路由**：`GET /ai-assistant` → `templates/ai_assistant.html`  
**API**：`POST /api/ai/chat`（SSE流式响应）

**LLM配置**（支持三选一）：
- **DeepSeek**（推荐）：`deepseek-chat` 模型，通过官方API
- **OpenAI**：兼容OpenAI接口格式
- **Ollama**：本地部署的大模型（离线可用）

---

#### 模块8：新闻资讯聚合

| 数据源 | 内容类型 |
|--------|---------|
| 东方财富·财经早餐 | 每日市场综述要点 |
| 东方财富·全球快讯 | 24小时全球财经新闻滚动 |
| 财联社·电报 | A股实时快讯（速度最快） |
| 同花顺·财经直播 | 专业机构观点解读 |

**路由**：`GET /news` → `templates/news.html`  
**API**：`GET /api/news?type=`（支持按来源筛选）

---

### 3.2 用户认证模块

| 功能 | 路由 | 说明 |
|------|------|------|
| 登录 | `GET/POST /auth/login` | 用户名/邮箱 + 密码 |
| 注册 | `GET/POST /auth/register` | 用户名 + 邮箱 + 密码 + 邮箱验证码 |
| 邮箱验证码 | `POST /auth/send-verify-code` | 通过Resend SMTP发送（5分钟有效） |
| 忘记密码 | `GET/POST /auth/forgot-password` | 验证码校验后重置密码 |
| 个人中心 | `GET /auth/profile` | 查看/修改资料、修改密码、更换邮箱 |
| 自选股管理 | `GET/POST /auth/watchlist` | 添加/删除自选股 |
| 分析记录 | `GET /auth/analysis-history` | 查看历史分析操作记录 |
| 聊天记录 | `GET /auth/chat-history` | 查看AI对话历史 |
| 退出登录 | `GET /auth/logout` | 清除Session并重定向 |

---

### 3.3 管理员后台（7大功能）

> **权限守卫**：所有 `/admin/*` 路径强制校验 `user.is_admin`，非管理员返回403。

| # | 功能 | 路由 | 说明 |
|---|------|------|------|
| 1 | **仪表盘** | `GET /admin/` | 用户数/自选股数/分析记录/聊天记录/股票数/分钟数据量/日志统计卡片 |
| 2 | **用户管理** | `GET /admin/users` | 列表搜索、查看详情、启用/停用/封禁、角色升降级(user↔admin)、删除 |
| 3 | **用户详情** | `GET /admin/users/<id>` | 含该用户的自选股列表、分析记录、聊天记录 |
| 4 | **操作日志** | `GET /admin/logs` | 按类型(admin_login/user_login/data_sync等)+状态筛选，最新300条 |
| 5 | **数据中心** | `GET /admin/data` | 股票基础数量、分钟数据量统计、数据健康度 |
| 6 | **手动数据同步** | `POST /admin/data/sync-one` | 按股票代码触发分钟线数据同步 |
| 7 | **系统自检** | `GET /admin/system-check` | MySQL/Redis/Tushare/AkShare 连通性一键检测 |

**管理后台页面清单**（`templates/admin/`）：
- `login.html` — 管理员独立登录页
- `dashboard.html` — 仪表盘
- `users.html` — 用户列表CRUD
- `user_detail.html` — 用户详情
- `logs.html` — 操作日志
- `data.html` — 数据中心
- `health_check.html` — 系统自检

---

## 四、项目目录结构

```
quantitative_analysis/                    # 项目根目录
│
├── app/                                  # Flask 应用主体
│   ├── __init__.py                       # 应用工厂 create_app() + 中间件 + 全局异常处理
│   ├── extensions.py                     # db/redis/mail 扩展实例初始化
│   ├── celery_app.py                     # Celery 配置（预留异步任务队列）
│   ├── tasks.py                          # Celery 任务定义（预留）
│   │
│   ├── api/                              # API 数据接口蓝图 (url_prefix=/api)
│   │   ├── __init__.py                   # api_bp 注册
│   │   ├── stock_api.py                  # 股票相关API（行情/K线/因子/资金流/筹码/分时）
│   │   ├── analysis_api.py               # 选股筛选 + 回测执行API
│   │   ├── news_api.py                   # 新闻资讯API
│   │   ├── realtime_monitor_api.py       # 实时监控API（排行榜/分时/仪表盘）
│   │   └── ai_assistant_api.py           # AI对话API（SSE流式）
│   │
│   ├── main/                             # 页面路由蓝图（无前缀）
│   │   ├── __init__.py                   # main_bp 注册
│   │   └── views.py                      # 9个页面路由定义
│   │
│   ├── routes/                           # 认证 & 后台管理蓝图
│   │   ├── auth_routes.py                # 用户认证（登录/注册/个人中心/自选股/记录）
│   │   └── admin_routes.py               # 管理后台（仪表盘/用户CRUD/日志/数据/自检）
│   │
│   ├── services/                         # 业务逻辑层（13个服务）
│   │   ├── stock_service.py              # 核心股票服务（行情/详情/技术指标计算）
│   │   ├── akshare_service.py            # AkShare数据适配器（实时行情/分钟K线/新闻）
│   │   ├── backtest_engine.py            # 回测引擎（5种策略 + 绩效计算）
│   │   ├── llm_service.py               # 大模型服务（DeepSeek/Ollama/OpenAI + SSE）
│   │   ├── ai_conversation_service.py    # AI会话管理（多轮对话持久化）
│   │   ├── news_service.py              # 新闻聚合服务（4源数据抓取）
│   │   ├── realtime_monitor_service.py   # 实时监控服务（分时数据/排行/仪表盘）
│   │   ├── market_overview_service.py    # 市场概览服务（指数/涨跌统计/健康检查）
│   │   ├── minute_data_sync_service.py   # 分钟数据同步服务
│   │   ├── email_service.py             # 邮件发送服务（Resend SMTP验证码）
│   │   ├── system_log_service.py         # 系统日志写入服务
│   │   └── user_activity_service.py      # 用户行为服务（自选股/分析记录/聊天记录）
│   │
│   ├── models/                           # SQLAlchemy ORM 模型（22个）
│   │   ├── user.py                       # User（用户账号/角色/状态）
│   │   ├── user_activity.py              # UserWatchlist / UserAnalysisRecord / UserChatHistory
│   │   ├── ai_conversation.py            # UserAiConversation / UserAiMessage
│   │   ├── stock_basic.py                # StockBasic（股票基础信息）
│   │   ├── stock_daily_history.py        # StockDailyHistory（日线行情OHLCV）
│   │   ├── stock_daily_basic.py          # StockDailyBasic（每日指标PE/PB/市值）
│   │   ├── stock_factor.py               # StockFactor（13种技术因子）
│   │   ├── stock_ma_data.py              # StockMaData（均线数据）
│   │   ├── stock_moneyflow.py            # StockMoneyflow（资金流向）
│   │   ├── stock_minute_data.py          # StockMinuteData（分钟线数据）
│   │   ├── stock_cyq_perf.py             # StockCyqPerf（筹码性能）
│   │   ├── stock_cyq_chips.py            # StockCyqChips（筹码分布明细）
│   │   ├── stock_business.py             # StockBusiness（主营业务）
│   │   ├── stock_income_statement.py     # StockIncomeStatement（利润表）
│   │   ├── stock_balance_sheet.py        # StockBalanceSheet（资产负债表）
│   │   ├── stock_shock.py               # StockShock（异动信息）
│   │   ├── trading_signals.py            # TradingSignals（交易信号）
│   │   ├── portfolio_positions.py        # PortfolioPositions（持仓组合）
│   │   ├── risk_alerts.py               # RiskAlerts（风险预警）
│   │   └── system_log.py                 # SystemLog（操作日志）
│   │
│   ├── templates/                        # Jinja2 HTML模板（24个）
│   │   ├── base.html                     # 基础布局模板（导航栏/页脚/CSS/JS引入）
│   │   ├── index.html                    # 首页
│   │   ├── stocks.html                   # 股票列表
│   │   ├── stock_detail.html             # 个股详情（核心页面）
│   │   ├── screen.html                   # 选股筛选
│   │   ├── backtest.html                 # 策略回测
│   │   ├── ai_assistant.html             # AI智能助手
│   │   ├── news.html                     # 新闻资讯
│   │   ├── realtime_monitor.html         # 实时监控
│   │   ├── analysis.html                 # 分析页（已重定向到stocks）
│   │   ├── auth/                         # 认证子目录
│   │   │   ├── login.html / register.html / profile.html / forgot_password.html
│   │   ├── admin/                        # 管理后台子目录（7个模板）
│   │   └── errors/                       # 错误页面
│   │       ├── 404.html / 500.html / 429.html
│   │
│   ├── static/                           # 静态资源
│   │   ├── css/                          # 样式文件（Bootstrap自定义 + 业务CSS）
│   │   ├── js/                           # 前端JavaScript（ECharts配置/交互逻辑）
│   │   └── logo.png                      # 系统Logo
│   │
│   └── utils/                            # 工具函数集（25个模块）
│       ├── logger.py                     # Loguru日志配置
│       ├── cache_utils.py                # Redis/内存双层缓存
│       ├── auth.py                       # login_required / admin_required 装饰器
│       └── ...（其他工具模块）
│
├── config.py                             # 配置类（DevelopmentConfig / ProductionConfig）
├── run.py                                # 开发环境启动入口（FLASK_DEBUG=True）
├── run_system.py                         # 菜单式启动入口
├── quick_start.py                        # 轻量启动脚本
│
├── docker-compose.yml                    # Docker Compose 编排（4容器: web/nginx/mysql/redis）
├── Dockerfile                            # Web应用容器镜像定义
├── docker-compose.dev.yml                # 开发环境Docker编排
├── gunicorn.conf.py                      # Gunicorn生产服务器配置
│
├── requirements.txt                      # 完整依赖清单（~50个包）
├── requirements-base.txt                 # 基础依赖
├── requirements-minimal.txt              # 最小依赖
├── requirements-prod.txt                 # 生产依赖
├── requirements-dev.txt                  # 开发依赖
├── requirements-ml.txt                   # 机器学习扩展依赖
│
├── deploy/                               # 部署配置
│   └── nginx.conf                        # Nginx反向代理配置
│
├── scripts/                              # 工具脚本
│   ├── db_tools/                         # 数据库查看工具
│   ├── diagnostics/                      # 诊断脚本
│   └── setup/                            # 初始化脚本
│
├── docs/                                 # 项目文档
│   ├── guides/                           # 使用指南
│   ├── analysis/                         # 分析记录
│   └── archive/                          # 归档文档
│
├── models/                               # 预训练ML模型文件（.pkl）
├── data/                                 # 运行时数据缓存
├── logs/                                 # 运行日志
├── ssl-certs/                            # SSL证书（HTTPS可选）
│
├── 论文_第4章_系统实现/                   # 论文配图（Drawio diagrams）
│   └── diagrams/                         # *.drawio 架构图/类图/流程图
│
├── Data Dictionary/                      # 数据字典
├── start.bat / start.sh                  # 一键启动脚本
├── stop-docker.bat                       # Docker停止脚本
├── runtime_encoding.py                   # 编码运行时修复
└── README.md                             # 项目说明
```

---

## 五、界面（页面）介绍

### 5.1 用户端页面导航

```
┌──────────────────────────────────────────────────────────────────┐
│  [Logo] A股量化分析系统    首页 | 行情 | 选股 | 回测 | AI助手 | 新闻 | 监控  [登录/注册]
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         （页面内容区域）                           │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  © 2026 A股量化分析系统 | Flask + ECharts + DeepSeek             │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 各页面详细说明

#### 页面1：首页 (`/`)
- **顶部横幅**：市场三大指数（上证/深证/创业板）实时点位卡片
- **中部**：涨跌家数统计、行业板块热力图、成交额TOP10表格
- **底部**：快捷入口按钮（选股/回测/AI助手/监控）
- **自动刷新**：指数数据定时轮询更新

#### 页面2：股票列表 (`/stocks`)
- **搜索栏**：关键字输入框 + 行业下拉选择 + 地域下拉选择
- **数据表格**：代码 | 名称 | 行业 | 上市日期 | 最新价 | 涨跌幅
- **分页控件**：上一页/下一页/页码跳转
- **点击跳转**：点击任意行进入个股详情页

#### 页面3：个股详情 (`/stock/<ts_code>`) — 最重要页面
- **Tab切换布局**（6个子Tab）：
  - **Tab1 行情概览**：当前价格/今开/最高/最低/昨收/成交量/成交额/市值/PE/PB/振幅/换手率
  - **Tab2 K线图**：ECharts蜡烛图 + MA5/MA10/MA20/MA30均线叠加 + 成交量副图
  - **Tab3 技术指标**：MACD/KDJ/RSI/CCI/BOLL/WR/DMI/PSY/MTM/EMV/ROC/OBV/VR 共13种，下拉选择切换
  - **Tab4 资金流向**：主力资金净流入/流出柱状图，按超大单/大单/中单/小单分层
  - **Tab5 筹码分布**：成本分布柱状图 + 获利盘/套牢盘比例
  - **Tab6 分时走势**：当日价格曲线 + 均价线 + 昨收基准线 + 成交量柱状图（支持1/5/15/30/60分钟粒度切换）

#### 页面4：选股筛选 (`/screen`)
- **条件面板**：价格范围滑块 / 涨跌幅区间 / 成交量阈值 / 换手率范围 / PE-PB区间 / 市值范围
- **筛选项**：行业多选 / 地域多选
- **结果区**：满足条件的股票列表（复用stocks表格样式）

#### 页板5：策略回测 (`/backtest`)
- **参数设置区**：
  - 股票代码输入 + 日期范围选择
  - 策略下拉（MA/MACD/KDJ/RSI/BOLL）
  - 策略参数调整（如MA短期/长期周期、RSI超买超卖阈值等）
- **执行按钮**：「开始回测」→ 显示加载动画
- **结果展示区**：
  - 累计收益率曲线图（ECharts）
  - K线图 + 买卖信号标注
  - 统计指标卡片：总收益率 | 年化收益 | 最大回撤 | 夏普比率 | 胜率 | 盈亏比 | 总交易次数

#### 页面6：AI智能助手 (`/ai-assistant`)
- **左侧边栏**：历史会话列表（新建/切换/删除/重命名会话）
- **右侧主区域**：
  - 对话消息流（用户消息靠右蓝色/AI回复靠左灰色）
  - SSE流式输出效果（逐字显示）
  - 底部输入框 + 发送按钮
- **预设快捷问题**："什么是MACD？" / "帮我分析XX股票" / "推荐一个适合新手的策略"

#### 页面7：新闻资讯 (`/news`)
- **顶部Tab栏**：财经早餐 | 全球快讯 | 财联社电报 | 同花顺直播（4个数据源切换）
- **新闻列表**：发布时间 | 标题 | 来源标签
- **关键词高亮**：标题中的股票名称/数字特殊标记

#### 页面8：实时监控 (`/monitor`)
- **监控矩阵**：自选股票池实时价格表格（颜色编码：红涨/绿跌）
- **排行榜**：涨幅TOP10 / 跌幅TOP10 双栏对比
- **分时图嵌入**：点击某只股票弹出当日内分钟走势

### 5.3 认证页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录页 | `/auth/login` | 用户名/邮箱 + 密码 + 记住我 + 「去注册」链接 |
| 注册页 | `/auth/register` | 表单：用户名 + 邮箱 + 密码 + 确认密码 + 验证码 + 「获取验证码」按钮 |
| 找回密码 | `/auth/forgot-password` | 输入邮箱 → 发送验证码 → 重置密码 |
| 个人中心 | `/auth/profile` | 4个Tab：基本信息/密码修改/邮箱变更/自选股管理/分析记录/聊天记录 |

### 5.4 管理后台页面

| 页面 | 路由 | 布局特点 |
|------|------|---------|
| 管理员登录 | `/admin/login` | 简洁深色主题，独立的登录入口 |
| 仪表盘 | `/admin/` | 7个统计卡片(KPI) + 最近活动时间线 |
| 用户列表 | `/admin/users` | 表格 + 搜索框 + 操作按钮(查看/启用/停用/封禁/升降级/删除) |
| 用户详情 | `/admin/users/<id>` | 用户基本信息 + 3个子Tab(自选股/分析记录/聊天记录) |
| 操作日志 | `/admin/logs` | 表格 + 类型/状态下拉筛选 |
| 数据中心 | `/admin/data` | 数据统计卡片 + 手动同步表单 |
| 系统自检 | `/admin/system-check` | 4个组件状态卡片(MySQL✓/Redis✓/Tushare✓/AkShare✓) + 耗时显示 |

### 5.5 错误页面

| 页面 | HTTP状态码 | 触发场景 |
|------|-----------|---------|
| `errors/404.html` | 404 | 访问不存在的URL |
| `errors/500.html` | 500 | 服务器内部异常（自动rollback） |
| `errors/429.html` | 429 | 请求频率超限（仅生产环境生效） |

---

## 六、技术规格汇总

### 6.1 后端技术栈

| 类别 | 技术 | 版本/说明 |
|------|------|-----------|
| Web框架 | Flask | >=2.3.0 |
| ORM | SQLAlchemy | >=2.0.0（2.0风格声明式映射） |
| 数据库驱动 | PyMySQL | >=1.1.0 |
| 数据库 | MySQL | 8.0（utf8mb4字符集） |
| 缓存 | Redis（>=5.0）/ 内存字典降级 | 双层缓存机制 |
| 任务队列 | Celery（已配置，预留扩展） | 异步任务 |
| 定时任务 | APScheduler | >=3.10.0 |
| 邮件 | flask-mailman + Resend SMTP | 验证码发送 |
| 限流 | Flask-Limiter | 生产环境200次/分钟 |
| CORS | Flask-CORS | 开发全开/生产白名单 |
| 日志 | Loguru | 文件+控制台双输出 |
| 错误监控 | Sentry（可选） | DSN配置激活 |
| 指标 | Prometheus Flask Instrumentator | `/metrics`端点 |

### 6.2 数据源

| 数据源 | 用途 | 接口特点 |
|--------|------|---------|
| **Tushare Pro** | 日线行情/基本面/财务报表/技术因子 | 需Token（15000积分），RESTful API |
| **AkShare** | 实时行情快照/分钟K线/新闻资讯 | 免费开源，爬虫式采集 |
| **新浪财经HTTP API** | 实时行情列表（涨跌榜） | 直连速度快(~0.5s)，绕过代理限制 |
| **DeepSeek API** | AI智能问答 | SSE流式输出，deepseek-chat模型 |

### 6.3 前端技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 模板引擎 | Jinja2 | 服务端渲染 |
| CSS框架 | Bootstrap | 响应式布局 |
| 图表库 | ECharts | K线/折线/柱状/散点/热力图 |
| JavaScript | 原生JS (ES6+) | Fetch API / DOM操作 |
| 字体图标 | Bootstrap Icons / Font Awesome | UI图标 |

### 6.4 部署架构

```
┌─────────────────────────────────────────┐
│              Nginx (反向代理)             │
│         :80 (HTTP) / :443 (HTTPS)        │
│         静态资源 / SSL终止 / 请求转发      │
└──────────────────┬──────────────────────┘
                   │ proxy_pass :5001
                   ▼
┌─────────────────────────────────────────┐
│          Gunicorn (WSGI服务器)            │
│         4 workers, sync worker mode       │
│              Flask App                   │
└─────────┬───────────────┬───────────────┘
          │               │
          ▼               ▼
   ┌────────────┐  ┌────────────┐
   │   MySQL8.0  │  │   Redis    │
   │  :3307(宿主)│  │  :6380(宿主)│
   └────────────┘  └────────────┘
```

**Docker Compose 四容器编排**：
| 容器 | 镜像 | 端口映射 | 说明 |
|------|------|---------|------|
| web | 自建Dockerfile(Python3.11) | 5001→5001 | Flask应用 |
| nginx | nginx:alpine | 80→80, 443→443 | 反向代理+静态文件 |
| mysql | mysql:8.0 | 3307→3306 | 数据持久化卷 |
| redis | redis:alpine | 6380→6379 | 缓存持久化卷 |

---

## 七、数据模型一览（22个ORM模型）

### 分类总览

| 分类 | 模型名 | 表用途 | 核心字段 |
|------|--------|--------|---------|
| **用户体系**(4) | `User` | 用户账号 | username/email/password_hash/role/status |
| | `UserWatchlist` | 自选股 | user_id/ts_code |
| | `UserAnalysisRecord` | 分析记录 | user_id/stock_code/action/result |
| | `UserChatHistory` | 历史聊天 | user_id/question/answer |
| **AI对话**(2) | `UserAiConversation` | 会话 | user_id/title/created_at |
| | `UserAiMessage` | 消息 | conversation_id/role/content |
| **股票基础**(3) | `StockBasic` | 股票列表 | ts_code/symbol/name/industry/area/list_date |
| | `StockBusiness` | 主营业务 | ts_code/main_business |
| | `StockShock` | 异动信息 | ts_code/shock_type/detail |
| **行情数据**(3) | `StockDailyHistory` | 日线OHLCV | ts_code/trade_date/open/high/low/close/vol/amount |
| | `StockDailyBasic` | 日指标 | ts_code/pe/pb/total_mv/circ_mv/turnover_rate |
| | `StockMinuteData` | 分钟线 | ts_code/time/open/high/low/close/volume/amount |
| **技术分析**(4) | `StockFactor` | 技术因子(13种) | ts_code/macd/kdj_k/kdj_d/kdj_j/rsi/cci/boll_up/mid/low/wr/dmi/psy/mtm/emv/roc/obv/vr |
| | `StockMaData` | 均线数据 | ts_code/ma5/ma10/ma20/ma30 |
| | `StockMoneyflow` | 资金流向 | ts_code/buy_sell_elg/lg/sm/mds/buy_amt/sell_amt |
| | `StockCyqPerf+Chips` | 筹码分布 | ts_code/cost_5pct/cost_15pct/cost_50pct/cost_85pct/cost_95pct/win_ratio/chip_detail |
| **财务数据**(2) | `StockIncomeStatement` | 利润表 | ts_code/revenue/net_profit/eps等 |
| | `StockBalanceSheet` | 资产负债表 | ts_code/total_assets/total_liab/equity等 |
| **系统**(3) | `SystemLog` | 操作日志 | action_type/message/user_id/status/created_at |
| | `TradingSignals` | 交易信号 | ts_code/signal_type/strength |
| | `PortfolioPositions` | 持仓组合 | user_id/ts_code/position_size/cost_price |
| | `RiskAlerts` | 风险预警 | alert_type/level/message/status |

---

## 八、本项目对话关键内容总结

### 8.1 已完成的讨论议题

#### 议题1：系统架构确认 ✅
- 确认系统为 **MVC + Blueprint 分层** 的 B/S 架构
- 明确分为 **用户端**（8大功能模块）和 **管理员端**（7大功能点）
- 权限控制：`before_request` + Session + `role` 字段做 RBAC
- 前后端 **不分离**（Jinja2 SSR），适合毕设场景

#### 议题2：前后端分离 vs 不分离 对比 ✅
- 分析了两种模式的优缺点
- 确认当前项目的选择（不分离）是合理的：单人开发、快速交付、毕设核心在功能不在工程化

#### 议题3：论文摘要审查与修正 ✅
- 逐条对照代码核查摘要事实陈述
- 发现3处需修正：
  1. **Redis** → 应描述为"Redis/内存双层缓存机制"
  2. **Celery** → 应描述为"预留异步任务队列"（非核心运行组件）
  3. **三种数据源(Tushare/AkShare/BaoStock)** → 应修正为"Tushare Pro与AkShare双数据源"（BaoStock仅为辅助工具）
- 给出了修正后的推荐版本

#### 议题4：系统完整性审查（CRUD检查）✅ 完成
- 完成了全系统12个模块的逐源码级CRUD审计
- 发现 **2个🔴必须修复项**：(1)分析记录缺R完整列表/U/D (2)回测结果无法持久化
- 发现 **5个🟡建议改进项**：自选股缺编辑、选股条件无法保存预设、新闻无缓存、AI双重写入、管理员用户列表无分页
- 发现 **1个⚠️架构陷阱**：`services/backtest_engine.py`是空壳，实际实现在 `api/analysis_api.py` 内部类
- 6个ORM模型已定义但未使用(TradingSignals/PortfolioPositions/RiskAlerts等)
- 完整报告见 `docs/SYSTEM_CRUD_AUDIT_REPORT.md`

### 8.2 项目规则/约束记录

| # | 规则 | ID |
|---|------|-----|
| 1 | 每次修改代码后检查文件编码是否UTF-8正常，验证导入/运行链路无报错 | 34865834 |
| 2 | A股量化分析系统技术总结（Flask+SQLAlchemy+Redis+ECharts+Akshare+Tushare），含分时图/技术指标/数据源等详细实现细节 | 69975859 |
| 3 | Tushare SDK使用规范：先创建pro对象设代理、显式传api=pro、实时接口需额外配置verify_token_url；发现tushare realtime_list存在bug，改用新浪财经HTTP API替代（速度0.5秒） | 80195736 |
| 4 | Akshare接口可用性：stock_zh_a_minute正常、stock_intraday_em被代理拦截不可达；实时行情使用新浪HTTP API；4个新闻接口均已接入NewsService | 80761927 |

### 8.3 待办/后续建议

- [ ] 🔴#1 补全 AnalysisRecord 的完整CRUD（独立列表页 + 编辑 + 删除）
- [ ] 🔴#2 实现 BacktestResult 持久化（新建模型 + 回测后自动保存 + 历史列表）
- [ ] 🟡1 自选股增加备注/分组/排序功能
- [ ] 🟡2 选股筛选条件保存为预设
- [ ] 🟡3 新闻API加Redis缓存(TTL=5min)
- [ ] 🟡4 清理AI对话Legacy双重写入
- [ ] 🟡5 管理员用户列表加分页
- [ ] 论文第4章系统实现的Drawio图需要与实际代码保持一致
- [ ] 如需答辩演示，建议准备一组演示账号和数据

---

## 九、服务器部署指南

> **当前状态**：系统已部署上线，域名 **rain11t.xyz**，通过 Docker Compose 编排运行。

### 9.1 部署架构总览

```
                        互联网用户
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│              Nginx (反向代理层)                    │
│         rain11t.xyz :80 / :443                   │
│  ┌────────────────────────────────────────────┐  │
│  │  /static/*   → 静态文件直托(30天缓存)       │  │
│  │  /healthz    → 健康检查(无日志)             │  │
│  │  /*          → proxy_pass → web:5001        │  │
│  │                (SSE关闭缓冲/120s超时)        │  │
│  └────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────┘
                   │ proxy_pass http://web:5001
                   ▼
┌──────────────────────────────────────────────────┐
│           Gunicorn WSGI Server                     │
│     (Docker容器: stock-analysis-web)               │
│                                                   │
│  bind = 0.0.0.0:5001                              │
│  workers = CPU*2+1 (max 8)                         │
│  worker_class = sync                               │
│  timeout = 180s (适配回测计算和LLM流式)            │
│  max_requests = 5000 (防内存泄漏自动重启worker)     │
│  preload_app = True (预加载减少内存占用)            │
│  运行用户: appuser (非root,安全加固)               │
└──────────────┬──────────────────┬─────────────────┘
               │                  │
      ┌────────▼──┐     ┌────────▼────────┐
      │  MySQL 8.0  │     │   Redis (缓存)   │
      │  :3307(宿主) │     │   :6380(宿主)    │
      │  utf8mb4    │     │   可选降级为内存   │
      └─────────────┘     └─────────────────┘
```

### 9.2 服务器基本信息

| 项目 | 值 |
|------|-----|
| **域名** | `rain11t.xyz` （支持 www.rain11t.xyz） |
| **访问地址** | `http://rain11t.xyz` |
| **HTTPS** | 当前使用 HTTP（HTTPS配置已预留，见nginx.conf注释部分） |
| **部署方式** | Docker Compose 四容器编排 |
| **服务器OS** | Linux (基于Dockerfile推断) |
| **Python版本** | 3.11-slim (Docker镜像) |
| **Web服务器** | Gunicorn 21.0+ |
| **反向代理** | Nginx (Alpine镜像) |
| **数据库** | MySQL 8.0 (Docker容器, 端口映射3307) |
| **缓存** | Redis (Alpine容器, 端口映射6380, 可选) |

### 9.3 Docker 容器清单

| 容器名 | 镜像 | 端口映射 | 职责 | 状态检查 |
|--------|------|---------|------|---------|
| `stock-analysis-web` | 自建(Python3.11-slim) | 5001→5001 | Flask应用(Gunicorn) | HTTP GET /healthz (30s间隔) |
| `stock-analysis-nginx` | nginx:alpine | 80→80, 443→443 | 反向代理+静态文件 | 依赖 web 启动 |
| `stock-analysis-mysql` | mysql:8.0 | 3307→3306 | 数据存储(mysqladmin ping) | 10s间隔, 10s超时, 5次重试 |
| `stock-analysis-redis` | redis:alpine | 6380→6379 | 缓存层(redis-cli ping) | 10s间隔 |

**数据持久化卷**：
```
mysql_data:  → /var/lib/mysql (MySQL数据文件)
redis_data:  → /data          (Redis RDB/AOF文件)
./logs:       → /app/logs      (应用日志, bind mount)
./data:       → /app/data      (运行时数据缓存, bind mount)
ssl-certs/:   → /etc/nginx/ssl (SSL证书, 只读挂载)
```

### 9.4 部署命令速查

#### 一键启动（开发环境）

```bash
# Windows 本地开发
start-docker.bat              # 双击即可启动

# Linux/Mac 开发环境
docker compose -f docker-compose.dev.yml up -d --build

# 手动分步启动（调试用）
docker compose -f docker-compose.dev.yml build    # 构建镜像
docker compose -f docker-compose.dev.yml up -d     # 后台启动
docker compose -f docker-compose.dev.yml ps         # 查看状态
```

#### 生产环境部署

```bash
# ===== 首次部署到服务器 =====

# 1. 上传代码到服务器
scp -r ./quantitative_analysis user@your-server:/opt/
ssh user@your-server

# 2. 进入项目目录
cd /opt/quantitative_analysis

# 3. 配置环境变量（必须！）
cp .env.example .env
nano .env    # 填写：SECRET_KEY / DB_PASSWORD / TUSHARE_TOKEN / DEEPSEEK_API_KEY 等

# 4. 生成 SECRET_KEY（生产必做）
python3 -c "import secrets; print(secrets.token_hex(32))"

# 5. 构建并启动所有服务
docker compose up -d --build

# 6. 查看服务状态和日志
docker compose ps
docker compose logs -f web          # 实时查看Web日志
docker compose logs -f mysql        # 查看数据库日志

# 7. 验证部署成功
curl http://localhost:5001/healthz  # 应返回 {"status":"ok",...}
curl http://localhost/healthz       # 通过Nginx访问
```

#### 日常运维命令

```bash
# ===== 服务管理 =====
docker compose restart web           # 重启Web应用（代码更新后）
docker compose restart               # 重启全部服务
docker compose down                 # 停止并删除容器（保留数据）
docker compose down -v              # 停止并删除容器+数据卷（⚠️会丢数据！）
stop-docker.bat                     # Windows一键停止

# ===== 日志查看 =====
docker logs stock-analysis-web --tail 100    # 最近100行Web日志
docker logs stock-analysis-web -f --since 5m # 最近5分钟实时日志
docker logs stock-analysis-mysql             # 数据库日志
docker logs stock-analysis-redis             # Redis日志

# ===== 容器内部操作 =====
docker exec -it stock-analysis-web bash      # 进入Web容器
docker exec -it stock-analysis-mysql bash     # 进入MySQL容器
docker exec -it stock-analysis-mysql mysql -u root -p  # 登录MySQL
docker exec -it stock-analysis-redis redis-cli           # 进入Redis CLI

# ===== 数据库操作 =====
docker exec -it stock-analysis-mysql mysqldump -u root -p stock_cursor > backup.sql   # 备份
docker exec -i stock-analysis-mysql mysql -u root -p stock_cursor < backup.sql         # 恢复

# ===== 代码更新与重新部署 =====
# 方法A：修改后重启（如果用了bind mount开发模式则自动生效）
docker compose restart web

# 方法B：完全重建镜像（依赖变更或首次部署）
docker compose up -d --build

# ===== 资源监控 =====
docker stats                    # 实时CPU/内存/网络IO
docker system df                # 磁盘占用概况
```

### 9.5 代码同步策略

#### 方案一：Git 同步（推荐用于生产）

```bash
# 在本地完成开发和测试后
git add .
git commit -m "feat: 新增XXX功能"
git push origin master

# 在服务器上拉取最新代码并重建
ssh user@your-server
cd /opt/quantitative_analysis
git pull origin master
docker compose up -d --build
```

#### 方案二：直接上传（快速测试用）

```bash
# Windows → Linux服务器（使用 scp 或 rsync）
scp -r app/ user@server:/opt/quantitative_analysis/app/
scp config.py user@server:/opt/quantitative_analysis/config.py
ssh user@server "cd /opt/quantitative_analysis && docker compose restart web"

# 或使用 rsync 增量同步（更快）
rsync -avz --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.venv' --exclude='logs' \
    ./ user@server:/opt/quantitative_analysis/
```

#### 方案三：Docker Volume 挂载开发（仅开发环境）

```yaml
# docker-compose.dev.yml 中已配置：
volumes:
  - ./app:/app/app              # 代码热更新！修改本地即生效
  - ./config.py:/app/config.py:ro  # 配置文件只读挂载
```
**注意**：此模式**仅限开发环境**！生产环境必须使用 `docker-compose.yml`（将代码COPY进镜像），避免容器内代码被外部篡改。

### 9.6 关键配置文件说明

#### `.env` 环境变量（生产必配项）

| 变量名 | 必填 | 说明 | 示例值 |
|--------|------|------|--------|
| `SECRET_KEY` | ✅ **必填** | Flask Session签名密钥，**生产环境必须随机生成** | `a1b2c3d4e5f6...`(64位hex) |
| `DB_PASSWORD` | ✅ 必填 | MySQL root密码 | `changeme` |
| `TUSHARE_TOKEN` | ⚠️ 重要 | Tushare Pro API Token（15000积分） | `xxxxxxxx` |
| `DEEPSEEK_API_KEY` | ⚠️ 重要 | DeepSeek大模型API Key | `sk-xxxxx` |
| `DEEPSEEK_BASE_URL` | 可选 | DeepSeek API地址（如需代理） | 默认 `https://api.deepseek.com/v1` |
| `LLM_PROVIDER` | 可选 | LLM提供商选择 | `deepseek` / `ollama` / `openai` |
| `DEBUG` | 必须 | 生产设 `False` | `False` |
| `FLASK_ENV` | 必须 | 生产设 `production` | `production` |
| `CORS_ORIGINS` | 可选 | 允许的跨域来源（多域名逗号分隔） | `https://rain11t.xyz` |
| `REDIS_HOST` | 可选 | Redis地址（Docker内网用 `redis`） | `redis` |

#### `gunicorn.conf.py` 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `bind` | `0.0.0.0:5001` | 监听所有接口的5001端口 |
| `workers` | `CPU*2+1, max 8` | Worker进程数，根据CPU核心数自适应 |
| `timeout` | `180s` | 超时时间（回测和LLM调用可能较慢） |
| `max_requests` | `5000` | 每个Worker处理5000请求后自动重启（防内存泄漏） |
| `preload_app` | `True` | Master进程预加载应用（节省内存、加快fork） |
| `worker_class` | `sync` | 同步Worker（AI流式场景下比gevent更稳定） |
| `access_log_format` | 自定义 | 包含请求耗时 `%(D)s` 用于性能分析 |

#### `deploy/nginx.conf` 关键配置

```nginx
server_name rain11t.xyz www.rain11t.xyz;    # 绑定域名

# SSE流式响应关键配置（AI助手聊天必须）
proxy_buffering off;      # 关闭Nginx缓冲
proxy_cache off;          # 关闭缓存
proxy_read_timeout 120s;  # LLM流式响应可能持续较长时间

# 静态资源优化
location /static/ {
    expires 30d;           # 浏览器缓存30天
    add_header Cache-Control "public, immutable";
}

# 安全头
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;

# HTTPS预留（取消注释即可启用Let's Encrypt证书）
# ssl_certificate /etc/letsencrypt/live/rain11t.xyz/fullchain.pem;
```

#### `Dockerfile` 构建阶段

```
Stage 1 (builder): python:3.11-slim + gcc/g++/cmake/blas/lapack
    ↓ 安装 requirements.txt 全部依赖（含scikit-learn/xgboost等编译型包）
    ↓ 清理pip缓存

Stage 2 (final): python:3.11-slim (精简版，不含编译工具)
    ↓ 从 builder 复制 site-packages 和 bin
    ↓ 复制应用代码 COPY . .
    ↓ 创建非root用户 appuser (安全加固)
    ↓ EXPOSE 5001 + HEALTHCHECK
    ↓ CMD gunicorn -c gunicorn.conf.py run:app
```

**多阶段构建优势**：最终镜像不包含gcc/c++等编译工具，体积从~1.5GB缩减至~800MB。

### 9.7 生产环境注意事项

#### 🔴 安全相关

| 注意事项 | 详细说明 |
|---------|---------|
| **SECRET_KEY 务必随机生成** | 生产环境的 `config.py` 会检测：若 `SECRET_KEY` 为空或等于默认值且 `FLASK_ENV=production`，**直接退出报错拒绝启动**。生成方式：`python3 -c "import secrets; print(secrets.token_hex(32))"` |
| **禁止 DEBUG=True** | 生产环境开启DEBUG会泄露源码、配置、环境变量等敏感信息 |
| **非root运行** | Dockerfile中已创建 `appuser` 运行应用，避免容器被攻陷后获得root权限 |
| **数据库不要暴露公网** | MySQL端口映射 `3307:3306` 仅用于宿主机调试；生产防火墙应禁止外部访问3307 |
| **Nginx安全头** | 已配置 X-Frame-Options(防点击劫持)、X-XSS-Protection(防XSS)、X-Content-Type-Options(防MIME嗅探) |
| **Session安全** | ProductionConfig 已启用 HttpOnly + SameSite=Lax Cookie标志 |
| **速率限制** | 生产环境自动启用 Flask-Limiter（全局200次/分钟），登录5次/分钟，注册3次/分钟，AI聊天20次/分钟 |
| **.env 文件保护** | .env 已加入 `.gitignore`，不会提交到Git仓库。服务器上确保权限 `chmod 600 .env` |

#### 🟡 性能优化

| 优化项 | 状态 | 说明 |
|-------|------|------|
| 静态文件CDN/Nginx直托 | ✅ | `/static/` 由Nginx直接返回，不走Python，带30天浏览器缓存 |
| Gunicorn多Worker | ✅ | 根据CPU核数自动调整(max 8)，并发能力充足 |
| preload_app | ✅ | Master预加载，减少Worker fork后的内存开销 |
| Worker自动重启 | ✅ | max_requests=5000 后自动recycle worker防止内存泄漏 |
| Redis双层缓存 | ✅ | 优先Redis，不可用时降级为内存字典 |
| 数据库连接池 | ✅ | pool_size=20, pool_recycle=3600s, pre_ping=True |
| ECharts按需加载 | ✅ | 前端图表组件懒加载 |
| **待优化：新闻API缓存** | ⚪ 建议 | 当前每次都实时抓取AkShare，建议加Redis TTL=5min |
| **待优化：Gevent Worker** | ⚪ 可选 | 如需高并发可改 `worker_class=gevent`（但SSE流式需额外处理） |

#### 🟢 运维监控

| 能力 | 命令/方式 | 说明 |
|------|----------|------|
| 健康检查 | `GET /healthz` | 返回DB+Redis状态+版本+运行时长 |
| Prometheus指标 | `GET /metrics` | 需安装 `prometheus_flask_instrumentator` |
| Sentry错误追踪 | 环境变量 `SENTRY_DSN` | 配置后自动捕获未处理异常 |
| 应用日志 | `logs/stock_analysis.log` | Loguru输出，支持rotate |
| Gunicorn访问日志 | `logs/gunicorn_access.log` | 含请求耗时字段 %(D)s |
| Gunicorn错误日志 | `logs/gunicorn_error.log` | Worker崩溃/超时记录 |
| Docker容器日志 | `docker logs -f stock-analysis-web` | stdout/stderr汇总 |
| 管理员系统自检 | `/admin/system-check` | 一键检测4个组件连通性 |

#### ⚠️ 常见问题排查

| 问题现象 | 可能原因 | 排查命令/方案 |
|---------|---------|--------------|
| 页面502 Bad Gateway | Web容器未启动 | `docker compose ps` + `docker compose logs web` |
| 数据库连接失败 | MySQL未就绪或密码错误 | `docker exec -it stock-analysis-mysql mysql -u root -p -e "SELECT 1"` |
| Redis连接警告 | Redis容器未启动（降级为内存缓存） | `docker compose up -d redis`，属正常降级非致命错误 |
| AI助手返回503 | DeepSeek API Key无效或网络不通 | `curl http://localhost:5001/api/ai/status` 检查LLM连通性 |
| 行情数据显示空 | Tushare Token过期或积分不足 | 访问 `/admin/system-check` 检查Tushare状态 |
| 邮箱验证码发送失败 | Resend API Token未配置或邮箱服务不通 | 检查 `.env` 中 `MAIL_USERNAME`/`MAIL_PASSWORD` |
| 静态资源404 | Nginx静态目录挂载路径错误 | 检查 `docker-compose.yml` 中 `./app/static:/var/www/static:ro` |
| SSE流式中断 | Nginx proxy_buffering未关闭 | 确认 nginx.conf 中有 `proxy_buffering off` |
| 容器频繁重启OOM | 内存不足(1GB以下) | `docker stats` 查看内存占用，考虑减少workers或升级机器 |

### 9.8 部署架构图（Drawio参考文本）

```
[互联网] --HTTP:80--> [Nginx:alpine]
                          |
                          |-- /static/* --> 静态文件(30天缓存)
                          |-- /healthz  --> healthz(无日志)
                          |-- /* --> [Gunicorn:5001]
                                       |
                                       |-- Flask App (appuser运行)
                                       |     |
                                       |     |-- Blueprint: main_bp (/)
                                       |     |-- Blueprint: api_bp (/api/*)
                                       |     |-- Blueprint: auth_bp (/auth/*)
                                       |     |-- Blueprint: admin_bp (/admin/*)
                                       |
                                       |-- [MySQL:8.0 :3307] (22张表, utf8mb4)
                                       |-- [Redis:alpine :6380] (可选, 双层缓存)
```

### 9.9 备份与恢复策略

```bash
# ===== 自动备份脚本建议（可加入crontab）=====
#!/bin/bash
# /opt/backup_stock_db.sh — 每日3AM自动执行

BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 1. 备份MySQL
docker exec stock-analysis-mysql mysqldump -u root -p${DB_PASSWORD} \
    --single-transaction --routines --triggers \
    stock_cursor > "$BACKUP_DIR/stock_${DATE}.sql"
gzip "$BACKUP_DIR/stock_${DATE}.sql"

# 2. 清理7天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_DIR}/stock_${DATE}.sql.gz"

# crontab -e 添加:
# 0 3 * * * /opt/backup_stock_db.sh >> /var/log/backup.log 2>&1
```

---

*本文档由项目分析自动生成，最后更新时间：2026-04-27 21:41*
