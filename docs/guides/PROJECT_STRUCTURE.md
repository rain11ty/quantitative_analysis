# 项目结构说明

> 更新日期：`2026-04-28`

## 1. 顶层目录

```text
quantitative_analysis/
├─ app/                    Flask 主应用
├─ data/                   运行期数据目录
├─ deploy/                 Docker / Nginx / systemd 示例
├─ docs/                   当前项目文档
├─ init.sql/               SQL 初始化脚本
├─ models/                 机器学习模型或演示资产
├─ scripts/                数据同步、诊断、维护脚本
├─ ssl-certs/              HTTPS 证书目录
├─ README.md               仓库入口文档
├─ run.py                  标准启动入口
├─ quick_start.py          快速启动入口
└─ run_system.py           菜单式开发维护入口
```

## 2. `app/` 是当前主链路核心

```text
app/
├─ __init__.py             应用工厂、鉴权守卫、错误处理、/healthz
├─ extensions.py           db / redis / mail 初始化
├─ celery_app.py           Celery 预留配置
├─ tasks.py                Celery 预留任务
├─ api/                    JSON API
├─ main/                   页面路由
├─ routes/                 认证与后台
├─ services/               业务服务
├─ models/                 ORM 模型
├─ templates/              Jinja2 模板
└─ utils/                  同步脚本与通用工具
```

### 2.1 `app/api/`

当前有五个 API 模块：

- `stock_api.py`
- `analysis_api.py`
- `news_api.py`
- `realtime_monitor_api.py`
- `ai_assistant_api.py`

### 2.2 `app/main/`

只负责页面入口，不承担复杂业务。

当前有效页面：

- `/`
- `/stocks`
- `/stock/<ts_code>`
- `/screen`
- `/backtest`
- `/ai-assistant`
- `/news`
- `/monitor`

`/analysis` 目前只是兼容性重定向，不再是独立分析页。

### 2.3 `app/routes/`

- `auth_routes.py`：登录、注册、找回密码、个人中心
- `admin_routes.py`：后台登录、用户管理、日志、数据中心、自检

### 2.4 `app/services/`

这是主业务逻辑层，当前活跃服务包括：

- 股票数据
- 市场概览
- 实时监控
- 新闻聚合
- AI 对话
- 邮件验证码
- 分钟线同步
- 用户行为记录
- 系统日志

## 3. `scripts/` 的职责

`scripts/` 放的是命令式维护工具，不会在 `run.py` 中自动执行。

```text
scripts/
├─ sync_tushare_data.py        主行情同步脚本
├─ daily_auto_update.py        自动更新脚本
├─ data_health_check.py        数据健康巡检
├─ add_db_indexes.py           索引优化
├─ backfill_factors*.py        因子补算
├─ migrate_v20260427_crud_fix.py
├─ db_tools/                   手工数据库巡检
└─ diagnostics/                手工诊断脚本
```

## 4. `docs/` 的职责

`docs/` 只保留与当前仓库仍然相关的资料：

- `guides/`：安装、结构、数据库、工具说明
- `analysis/`：项目审查和开发总结
- `reports/`：维护记录

旧 `ml_factor` 空文档已经移除，不再作为当前主线资料保留。

## 5. 哪些内容属于“预留”而不是“当前功能”

以下内容虽然在仓库内存在，但不应被误读成当前已经上线：

- `app/services/backtest_engine.py` 的高级回测方案
- `celery_app.py` / `tasks.py` 的异步任务预留
- `StockIncomeStatement` / `StockBalanceSheet` 等财务数据模型的前端展示
- `app/utils/cash_flow.py` 产生的 `stock_cash_flow` 脚本式数据表
