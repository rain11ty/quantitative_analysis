# A 股量化分析系统

基于 Flask 的 A 股量化分析 Web 应用，集成了行情数据、技术分析、策略回测、AI 智能问答、实时监控等功能。支持 Docker 一键部署，Celery 异步任务调度，WebSocket 实时数据推送。

## 功能概览

### 行情与分析
- **股票数据**：列表、详情、日线历史、技术因子（MACD/KDJ/RSI/布林带/CCI）、资金流向（小/中/大/超大单）、筹码分布（CYQ）、均线数据
- **市场概览**：主要指数实时行情、涨跌家数、行业/概念板块排行、板块资金流向、指数 K 线图（1月/3月/6月/1年/3年）
- **选股筛选**：基于 `stock_business` 宽表的多条件组合筛选（估值、技术面、资金面、均线等字段）
- **策略回测**：5 种内置策略（均线交叉、MACD、KDJ、RSI、布林带），支持参数配置，自动计算收益率、夏普比率、最大回撤、胜率等指标
- **实时监控**：AkShare/Sina 行情快照，分钟级 K 线（1/5/15/30/60 分钟），涨跌幅/换手率/成交额排行，个股异动提醒

### AI 助手
- 多 LLM 供应商支持：DeepSeek、通义千问（DashScope）、OpenAI
- SSE 流式响应，对话历史管理（创建/重命名/删除）
- 图片上传（通义千问多模态），速率限制（20次/分钟）

### 用户系统
- 注册（邮箱验证码）、登录/登出、密码修改（邮箱验证）、邮箱绑定变更
- 个人中心：自选股管理、分析历史记录、AI 问答记录、回测结果保存
- 管理后台：用户管理（状态/角色/删除）、系统日志、数据中心、系统自检

### 实时推送
- Flask-SocketIO + eventlet 异步模型
- 5 个实时频道：市场行情、快讯、涨跌排名、板块排行、资金流向
- Celery 缓存刷新后自动推送到所有在线用户浏览器

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | Flask 2.3+ / Flask-RESTful / Flask-SocketIO |
| 数据库 | MySQL 8.0 + SQLAlchemy 2.0 |
| 缓存/消息队列 | Redis（缓存 + Celery broker + SocketIO MQ） |
| 异步任务 | Celery 5.3+（eventlet pool） |
| 数据源 | Tushare（历史数据）、AkShare（实时行情）、BaoStock |
| 数据处理 | pandas / numpy / scikit-learn / XGBoost / LightGBM |
| NLP | jieba / pypinyin（股票搜索） |
| 部署 | Docker Compose + Nginx + Gunicorn（eventlet worker） |
| 邮件 | Resend SMTP（验证码发送） |

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/rain11ty/quantitative_analysis.git
cd quantitative_analysis

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写必要配置（数据库密码、Tushare token、LLM API key 等）

# 3. 启动所有服务
docker compose up -d

# 4. 访问
# Web: http://localhost
# API: http://localhost/api/stocks
# 健康检查: http://localhost/healthz
```

### 方式二：本地开发

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env

# 4. 启动（开发模式）
python run.py
```

默认访问 `http://127.0.0.1:5001`。

## Docker 服务架构

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| web | stock-analysis-web | 5001 | Flask + Gunicorn（eventlet） |
| nginx | stock-analysis-nginx | 80/443 | 反向代理 + 静态文件 + SSL |
| mysql | stock-analysis-mysql | 3307 | MySQL 8.0 数据库 |
| redis | stock-analysis-redis | 6380 | 缓存 + 消息队列 |
| celery-worker | stock-analysis-celery-worker | - | Celery 异步任务（4 并发） |
| celery-beat | stock-analysis-celery-beat | - | Celery 定时任务调度 |

## 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 收盘增量更新 | 每日 18:05 | 日线、复权、指标、资金流向、技术因子 |
| 股票基础信息刷新 | 每周六 08:23 | 新股、改名、退市 |
| 数据健康检查 | 每日 09:07 | 交易日历、日线数量、MACD 填充率 |
| 分钟数据归档 | 每日 15:47 | Top 500 股票分钟 K 线 |
| 宽表同步 | 每日 18:30 | stock_business 宽表合并 |
| 快讯缓存 | 每 60 秒 | 4 源新闻聚合 → Redis → SocketIO |
| 涨跌排名 | 每 30 秒 | 涨跌幅/换手率/成交额排行 |
| 市场概览 | 每 30 秒 | 指数行情 + K 线预热 |
| 板块排行 | 每 60 秒 | 行业/概念板块排名 |
| 资金流向 | 每 120 秒 | 板块资金流向排名 |
| 资金流向回填 | 每周六 20:00 | 2021 年起缺失数据补算 |
| 技术因子回填 | 每周六 21:00 | 2021 年起缺失数据补算 |

所有任务均使用 Redis 分布式锁防止重复执行，eventlet 超时保护，失败邮件告警。

## 环境变量

详见 `.env.example`，核心配置：

```bash
# 数据库
DB_HOST=mysql
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=stock_cursor

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Tushare
TUSHARE_TOKEN=your_token

# LLM（三选一）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key

# 邮件（Resend SMTP）
MAIL_PASSWORD=your_resend_token

# Flask
SECRET_KEY=your_secret_key
```

## 目录结构

```
quantitative_analysis/
├── app/                          # Flask 应用核心
│   ├── api/                      # REST API（/api/*）
│   ├── main/                     # 页面路由
│   ├── models/                   # SQLAlchemy 模型（18 个）
│   ├── routes/                   # 认证 + 管理后台蓝图
│   ├── services/                 # 业务逻辑层（11 个服务）
│   ├── utils/                    # 工具函数（缓存、认证、日志）
│   ├── static/                   # CSS/JS/静态资源
│   ├── templates/                # Jinja2 模板
│   │   ├── admin/                # 管理后台页面
│   │   ├── auth/                 # 认证相关页面
│   │   └── errors/               # 错误页面
│   ├── __init__.py               # 应用工厂
│   ├── celery_app.py             # Celery 配置
│   ├── tasks.py                  # 异步任务定义
│   └── extensions.py             # 扩展单例
├── deploy/                       # Nginx / systemd 配置
├── docs/                         # 项目文档
├── scripts/                      # 数据同步/诊断脚本
├── models/                       # 预训练模型文件
├── config.py                     # 配置类
├── run.py                        # 主入口（eventlet + SocketIO）
├── docker-compose.yml            # 生产环境（6 服务）
├── docker-compose.dev.yml        # 开发环境（3 服务）
├── Dockerfile                    # 多阶段构建
├── gunicorn.conf.py              # Gunicorn 配置
└── requirements.txt              # 依赖清单
```

## 页面路由

| 路径 | 功能 |
|------|------|
| `/` | 首页（市场概览 + K 线 + 快讯 + 排名） |
| `/stocks` | 股票列表（搜索/行业/地域筛选） |
| `/stock/<ts_code>` | 个股详情（K 线/因子/资金流/筹码） |
| `/screen` | 条件选股 |
| `/backtest` | 策略回测 |
| `/ai-assistant` | AI 智能问答 |
| `/news` | 财经快讯 |
| `/monitor` | 实时监控 |
| `/auth/login` | 登录 |
| `/auth/register` | 注册 |
| `/auth/profile` | 个人中心 |
| `/admin/` | 管理后台 |

## API 接口

所有 API 以 `/api` 为前缀，主要端点：

- `GET /api/stocks` — 股票列表（分页/筛选）
- `GET /api/stocks/<ts_code>` — 股票详情
- `GET /api/market/overview` — 市场概览
- `GET /api/market/boards` — 板块排行
- `GET /api/market/sector-fund-flow` — 资金流向
- `POST /api/analysis/screen` — 条件选股
- `POST /api/analysis/backtest` — 策略回测
- `POST /api/ai/chat` — AI 对话（SSE 流式）
- `GET /api/monitor/ranking` — 实时排名
- `GET /api/news` — 新闻聚合
- `GET /healthz` — 健康检查

## 数据库

MySQL 8.0，数据库名 `stock_cursor`，主要表：

**行情数据**：stock_basic、stock_daily_history、stock_daily_basic、stock_factor、stock_moneyflow、stock_cyq_perf、stock_cyq_chips、stock_business（宽表）、stock_minute_data

**用户数据**：user_account、user_watchlist、user_analysis_record、user_chat_history、user_backtest_result、user_ai_conversation、user_ai_message

**系统数据**：system_log

## 许可证

本项目仅供学习交流与研究演示使用，入市有风险，投资需谨慎。
