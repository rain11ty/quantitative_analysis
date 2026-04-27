# 开发总结

> **最后更新**：2026-04-27
> **项目名称**：A股量化分析系统 (Quantitative Analysis System)
> **技术栈**：Flask + SQLAlchemy + MySQL + Redis + ECharts + DeepSeek(LLM) + Tushare/AkShare

---

## 一、项目概述

基于 Python Flask 的专业 A 股量化分析平台，面向**股票投资新手**提供一站式数据分析能力。

### 核心特性（当前版本）

- **8 大用户端功能模块**：首页市场概览 / 股票列表搜索 / 个股详情分析（6 维度 Tab）/ 条件选股筛选 / 5 种策略回测 / AI 智能助手(SSE 流式) / 新闻资讯聚合(4 源) / 实时行情监控
- **完整的用户体系**：注册(邮箱验证码) / 登录 / 个人中心 / 自选股管理 / 分析记录 / 聊天记录
- **完整的管理后台**：仪表盘(11 项 KPI) / 用户 CRUD / 操作日志 / 数据中心 / 分钟线手动同步 / 系统四组件自检
- **AI 赋能**：接入 DeepSeek 大语言模型，支持自然金融问答 + SSE 流式输出 + 多轮对话记忆
- **工程化部署**：Docker Compose 四容器编排(web/nginx/mysql/redis) + Nginx 反向代理 + Gunicorn WSGI + SSL/HTTPS 预留

---

## 二、当前技术栈

| 类别 | 技术 | 版本要求 |
|------|------|---------|
| **Web 框架** | Flask | >= 2.3.0 |
| **ORM** | SQLAlchemy | >= 2.0.0（2.0 风格声明式映射） |
| **数据库** | MySQL | 8.0（utf8mb4 字符集） |
| **缓存** | Redis（>= 5.0）/ 内存字典降级 | 双层缓存机制 |
| **任务队列** | Celery | 已配置，预留异步扩展 |
| **前端模板** | Jinja2（服务端渲染） | Bootstrap + ECharts |
| **图表库** | ECharts | K 线/折线/柱状/热力图 |
| **数据获取** | Tushare Pro / AkShare | Tushare 需 Token（15000 积分） |
| **大模型** | DeepSeek API（推荐）/ Ollama 本地 / OpenAI 兼容 | SSE 流式输出 |
| **邮件** | Resend SMTP（Python smtplib） | 邮箱验证码发送 |
| **限流** | Flask-Limiter | 生产环境 200 次/分钟 |
| **日志** | Loguru | 文件 + 控制台双输出 |
| **监控** | Sentry（可选）+ Prometheus（可选） | 错误追踪 + 指标采集 |
| **数据处理** | Pandas / NumPy / SciPy / statsmodels | 因子计算与分析 |
| **机器学习** | scikit-learn / XGBoost / LightGBM / cvxpy | 预留扩展 |
| **部署** | Docker + Gunicorn + Nginx | 多阶段构建镜像 |

---

## 三、当前系统架构

### 3.1 分层架构（MVC + Blueprint）

```
浏览器 (Jinja2 SSR + ECharts + Bootstrap)
        │ HTTP/HTTPS
        ▼
┌─────────────────────────────────────────┐
│            Flask Web Server              │
│  ┌─────────────────────────────────┐    │
│  │ Controller (Blueprint)          │    │
│  │  main_bp(页面) / api_bp(JSON)   │    │
│  │  auth_bp(认证) / admin_bp(后台) │    │
│  ├─────────────────────────────────┤    │
│  │ Service Layer (业务逻辑)         │    │
│  │  stock / akshare / backtest     │    │
│  │  llm / news / realtime_monitor  │    │
│  │  email / market_overview / ...  │    │
│  ├─────────────────────────────────┤    │
│  │ Data Access (ORM)               │    │
│  │  SQLAlchemy — 22 个业务模型      │    │
│  └─────────────────────────────────┘    │
└──────────────┬──────────────────────────┘
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
  MySQL(22表)  Redis    外部API
  (utf8mb4)   (缓存)   Tushare/AkS/DeepSeek
```

### 3.2 Blueprint 划分

| Blueprint | URL 前缀 | 职责 |
|-----------|---------|------|
| **main_bp** | `/`（无前缀） | 页面渲染（9 个用户端页面） |
| **api_bp** | `/api/*` | JSON 数据接口（5 个模块，~57 个端点） |
| **auth_bp** | `/auth/*` | 用户认证（登录/注册/个人中心） |
| **admin_bp** | `/admin/*` | 管理后台（仅 `role=admin` 可访问） |

### 3.3 权限控制机制

- **Session + RBAC 双重机制**
- `before_request` 中间件统一鉴权
- 公开白名单覆盖大部分行情 API（未登录可访问首页/股票列表/详情等）
- `/admin/*` 强制校验 `is_admin`
- 生产环境 Flask-Limiter 速率限制（全局 200 次/分钟，登录 5 次/分钟）

---

## 四、当前数据库设计（22 张 ORM 模型）

### 4.1 模型分类总览

| 分类 | 数量 | 模型名 | 说明 |
|------|------|--------|------|
| **用户体系** | 4 | User / UserWatchlist / AnalysisRecord / UserChatHistory | 账号+活动 |
| **AI 对话** | 2 | UserAiConversation / UserAiMessage | 结构化多轮对话 |
| **股票基础** | 3 | StockBasic / StockBusiness / StockShock | 基本信息+主营+异动 |
| **行情数据** | 3 | StockDailyHistory / StockDailyBasic / StockMinuteData | 日线/指标/分钟线 |
| **技术分析** | 4 | StockFactor(13种因子) / StockMaData / StockMoneyflow / StockCyqPerf+Chips | 因子/均线/资金流/筹码 |
| **财务数据** | 2 | StockIncomeStatement / StockBalanceSheet | 利润表/资产负债表（预留） |
| **系统** | 3 | SystemLog / TradingSignals / PortfolioPositions / RiskAlerts | 日志+预留扩展 |

> 注：TradingSignals / PortfolioPositions / RiskAlerts / StockIncomeStatement / StockBalanceSheet 共 5 个模型已定义但当前无 API 读写调用，属于预留扩展。

---

## 五、当前已实现功能清单

### 5.1 用户端功能（✅ 全部完成）

| # | 功能 | 关键文件 | 状态 |
|---|------|---------|------|
| 1 | **首页市场概览**（三大指数/涨跌统计/行业热力/成交排行） | index.html + market_overview_service | ✅ |
| 2 | **股票列表搜索**（5000+ 只 A 股/关键字/行业/地域/分页） | stocks.html + stock_api + stock_service | ✅ |
| 3 | **个股详情分析**（6 个 Tab：行情/K线(蜡烛图+MA均线)/技术指标(13种切换)/资金流向(分层柱状)/筹码分布(成本曲线)/分时走势(多粒度)） | stock_detail.html (73KB) + stock_service | ✅ |
| 4 | **条件选股筛选**（价格/涨跌幅/成交量/PE-PB/市值/行业地域多维组合） | screen.html + analysis_api(screen) | ✅ |
| 5 | **策略回测**（MA/MACD/KDJ/RSI/BOLL 5 种策略 + 绩效指标 + ECharts 收益曲线） | backtest.html + analysis_api(backtest) | ✅ |
| 6 | **实时监控看板**（自选矩阵/涨跌排行/分时嵌入/成交量预警） | realtime_monitor.html (62KB) + realtime_monitor_service | ✅ |
| 7 | **AI 智能助手**（DeepSeek SSE 流式/多轮记忆/会话管理/金融知识库） | ai_assistant.html + ai_assistant_api + llm_service | ✅ |
| 8 | **新闻资讯聚合**（东财早餐/全球快讯/财联社电报/同花顺直播 4 源） | news.html + news_api + news_service | ✅ |

### 5.2 用户认证（✅ 完成）

| 功能 | 状态 |
|------|------|
| 用户名/邮箱登录 + 记住我 | ✅ |
| 注册（用户名+邮箱+密码+邮箱验证码强制校验） | ✅ |
| 忘记密码（验证码→重置三步流程） | ✅ |
| 个人中心（资料修改/密码修改/邮箱变更） | ✅ |
| 自选股管理（添加/删除/列表展示） | ✅ |
| 退出登录 | ✅ |

### 5.3 管理员后台（✅ 完成）

| # | 功能 | 状态 |
|---|------|------|
| 1 | 仪表盘（11 项 KPI 统计卡片 + 最近日志时间线） | ✅ |
| 2 | 用户列表（搜索/启用/停用/封禁/升降级/删除，禁止操作自身） | ✅ |
| 3 | 用户详情（基本信息 + 自选股/分析记录/聊天记录三个 Tab） | ✅ |
| 4 | 操作日志（类型+状态筛选，最新 300 条） | ✅ |
| 5 | 数据中心（股票数量/分钟数据量统计） | ✅ |
| 6 | 手动分钟线数据同步（按代码+周期触发） | ✅ |
| 7 | 系统自检（MySQL/Redis/Tushare/AkShare 四组件连通性一键检测） | ✅ |

### 5.4 基础设施（✅ 完成）

| 能力 | 说明 |
|------|------|
| Redis 双层缓存 | 优先 Redis，不可用时降级为内存字典 |
| Celery 任务队列 | 已配置（预留扩展），支持定时任务调度 |
| 邮件验证码 | Resend SMTP 发送（5 分钟有效期） |
| CORS 跨域 | 开发全开/生产白名单模式 |
| 速率限制 | Flask-Limiter，生产环境自动生效 |
| UTF-8 强制 | 所有 text 响应自动添加 charset=utf-8 |
| 健康检查 | GET /healthz 返回 DB+Redis+版本状态 |
| 错误处理 | 统一 404/500/429 错误页（JSON/HTML 双响应格式） |
| Sentry 监控 | 可选，DSN 配置即激活 |
| Prometheus 指标 | 可选，GET /metrics 端点 |

---

## 六、API 接口清单（当前有效）

### 6.1 股票数据 API（`/api/stocks`）

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/stocks` | A 股列表（分页+行业/地域/关键字筛选） |
| GET | `/api/stocks/<ts_code>` | 个股详情 + daily_basic |
| GET | `/api/stocks/<ts_code>/history` | 日 K 线历史（日期范围，最大 5000 条） |
| GET | `/api/stocks/<ts_code>/factors` | 13 种技术因子指标 |
| GET | `/api/stocks/<ts_code>/moneyflow` | 资金流向（主力/分层资金买卖） |
| GET | `/api/stocks/<ts_code>/cyq` | 筹码分布性能数据 |
| GET | `/api/stocks/<ts_code>/cyq_chips` | 筹码分布明细 |
| GET | `/api/market/index/<code>/kline` | 指数 K 线 |
| GET | `/api/market/overview` | 市场概览 |
| GET | `/api/market/health` | Tushare 服务状态 |
| GET | `/api/market/akshare_health` | AkShare 服务状态 |
| GET | `/api/industries` | 行业列表 |
| GET | `/api/areas` | 地域列表 |

### 6.2 分析/回测 API（`/api/analysis`）

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/analysis/screen` | 多条件组合选股筛选 |
| POST | `/api/analysis/backtest` | 5 种策略回测执行 |

### 6.3 新闻 API（`/api/news`）

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/news?source=all` | 4 源聚合新闻 |
| GET | `/api/news?source=cjzc/global_em/cls/ths` | 单源新闻 |

### 6.4 实时监控 API（`/api/monitor`）

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/monitor/dashboard` | 监控仪表盘（自选股矩阵） |
| GET | `/api/monitor/ranking` | 涨跌排行（limit ≤ 50） |
| GET | `/api/monitor/stocks/<ts_code>` | 个股监控详情 |
| GET | `/api/monitor/intraday/<ts_code>?granularity=` | 分时走势（1/5/15/30/60min） |
| GET | `/api/monitor/shock` | 异动波动数据 |

### 6.5 AI 助手 API（`/api/ai`）

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/ai/conversations` | 新建会话 |
| GET | `/api/ai/conversations` | 会话列表（搜索+最近50条） |
| GET | `/api/ai/conversations/<id>/messages` | 会话消息历史 |
| PATCH | `/api/ai/conversations/<id>` | 重命名会话 |
| DELETE | `/api/ai/conversations/<id>` | 删除会话 |
| POST | `/api/ai/chat?stream=true` | SSE 流式聊天 |
| GET | `/api/ai/status` | LLM 服务连通性检测 |

### 6.6 用户活动 API

| 方法 | 端点 | 功能 |
|------|------|------|
| POST/GET/DELETE | `/api/watchlist/<ts_code>` | 自选股增删查 |
| POST | `/auth/profile/records/analysis` | 保存分析记录 |
| POST | `/auth/profile/records/chat` | 保存聊天记录（Legacy） |

---

## 七、部署架构

### 7.1 Docker Compose 四容器编排

| 容器 | 镜像 | 端口映射 | 说明 |
|------|------|---------|------|
| web | 自建(Python 3.11-slim, 两阶段构建) | 5001→5001 | Flask(Gunicorn) |
| nginx | nginx:alpine | 80→80, 443→443 | 反向代理+静态文件 |
| mysql | mysql:8.0 | 3307→3306 | 数据持久化卷 |
| redis | redis:alpine | 6380→6379 | 缓存持久化卷（可选） |

### 7.2 关键配置

- **Gunicorn**: workers=CPU*2+1(max8), timeout=180s, max_requests=5000, preload_app=True
- **Nginx**: SSE 关闭缓冲(proxy_buffering off), 静态资源 30 天缓存, 安全头
- **Dockerfile**: 两阶段构建(builder+final)，最终镜像 ~800MB，非 root 用户运行(appuser)

### 7.3 启动方式

```bash
# Windows 本地开发
start.bat                          # 一键启动
start-docker.bat                   # Docker 开发环境

# Linux/Mac
./start.sh                         # 直接启动
docker compose -f docker-compose.dev.yml up -d --build  # Docker 开发

# 生产部署
docker compose up -d --build       # 一键编排全部服务
```

默认访问地址：`http://127.0.0.1:5001`（本地）/ `http://rain11t.xyz`（生产域名）

---

## 八、代码量概况（截至 2026-04-27）

| 语言 | 文件数 | 近似行数 |
|------|-------|---------|
| Python (.py) | 98 | ~14,500 |
| HTML (.html) | 24 | ~4,800 |
| CSS (.css) | 4 | ~670 |
| JavaScript (.js) | 3 | ~480 |
| 总计 | ~171 | ~23,250（不含 vendor 库和 SQL 备份） |

**最重的 5 个文件**：
1. `app/services/realtime_monitor_service.py` — 69.69KB
2. `app/templates/stock_detail.html` — 73.65KB
3. `app/templates/realtime_monitor.html` — 62.77KB
4. `app/services/akshare_service.py` — 38.67KB
5. `app/services/stock_service.py` — 37.59KB

---

## 九、已知待改进项（来自 2026-04-27 CRUD 审计）

### 必须修复（影响答辩可信度）
- 🔴 分析记录模块缺独立 R/U/D（仅有 Create 和 Profile 页摘要预览）
- 🔴 回测结果无法保存（执行完即丢弃，缺 BacktestResult 持久化）

### 建议改进
- 🟡 自选股缺少备注/分组/排序编辑
- 🟡 选股条件无法保存为预设
- 🟡 新闻 API 无缓存（每次实时抓取 AkShare）
- 🟡 AI 对话 Legacy ChatHistory 双重写入冗余
- 🟡 管理员用户列表无分页

### 预留但未使用的 ORM 模型（5 个）
- TradingSignals / PortfolioPositions / RiskAlerts / StockIncomeStatement / StockBalanceSheet

---

*本文档从早期版本全面更新至 2026-04-27，反映项目当前实际状态。*
