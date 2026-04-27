# 当前工作区结构盘点

> 盘点时间：`2026-04-28`
> 盘点范围：以当前工作区实际存在的项目文件为准，不把 `.venv`、`node_modules`、`__pycache__` 视为主结构的一部分

## 1. 关键统计

按当前仓库状态统计：

- `app/api/`：`6` 个文件，其中 `5` 个功能模块
- `app/services/`：`13` 个文件，其中 `12` 个实际服务类文件
- `app/models/`：`21` 个 Python 文件，导出 `24` 个 ORM 模型
- `app/templates/`：`24` 个模板文件
- `scripts/`：`18` 个维护脚本文件
- `docs/`：以项目说明、结构说明、审查结论和维护记录为主

## 2. 当前主链路

```text
run.py / quick_start.py / run_system.py
  -> app.create_app()
     -> 注册 main/api/auth/admin 蓝图
     -> 初始化 db / redis / mail
     -> 提供页面、API、后台与 /healthz
```

这说明当前仓库的真正核心是一个完整 Web 应用，而不是单纯的数据抓取脚本集合。

## 3. 目录逐项说明

### 3.1 根目录文件

| 文件 | 用途 |
|---|---|
| `run.py` | 标准启动入口 |
| `quick_start.py` | 快速启动 |
| `run_system.py` | 菜单式维护入口 |
| `config.py` | 环境与依赖配置 |
| `runtime_encoding.py` | Windows UTF-8 兼容修复 |
| `requirements*.txt` | 依赖分组 |
| `docker-compose*.yml` | 容器编排 |
| `Dockerfile` | 镜像构建 |

### 3.2 `app/`

这是当前仓库最重要的目录：

- `api/`：股票、分析、新闻、监控、AI 五大接口模块
- `main/`：页面路由
- `routes/`：认证和后台
- `services/`：业务逻辑
- `models/`：ORM 模型
- `templates/`：Jinja2 模板
- `static/`：主题 CSS、移动端 JS、本地 vendor 资源
- `utils/`：缓存、日志、Tushare/AkShare 相关脚本与工具

### 3.3 `scripts/`

`scripts/` 当前更像“运维工具箱”：

- 同步脚本
- 数据健康检查
- 因子补算
- 数据库查看工具
- 连接性诊断工具

### 3.4 `docs/`

当前 `docs/` 已按下面三种角色整理：

- 指南类：如何安装、怎么理解结构、数据库长什么样
- 分析类：当前项目评审、开发总结、CRUD 审计
- 报告类：维护日志

## 4. 当前已经确认的边界

### 4.1 活跃页面边界

活跃页面是：

- 首页
- 股票列表
- 股票详情
- 选股
- 回测
- AI 助手
- 新闻
- 实时监控
- 用户与后台相关页面

`analysis.html` 文件仍在模板目录中，但主路由已经不再直接渲染它。

### 4.2 活跃模型边界

当前与主链路强相关的模型包括：

- 用户、会话、自选股、分析记录、回测结果
- 股票基础、日线、分钟线、因子、资金流、筹码、异动
- 系统日志

偏预留模型包括：

- `TradingSignals`
- `PortfolioPositions`
- `RiskAlerts`
- `StockIncomeStatement`
- `StockBalanceSheet`

### 4.3 财务数据边界

财务三表相关文件目前分成两类：

- ORM：`StockIncomeStatement`、`StockBalanceSheet`
- 脚本：`income_statement.py`、`balance_sheet.py`、`cash_flow.py`

它们存在于仓库内，但当前页面和 API 没有直接把这些能力作为正式用户功能暴露出来。

## 5. 对维护者最重要的结论

如果要继续在这个仓库上开发，应该默认认为：

1. `app/` 是产品代码主线。
2. `scripts/` 是辅助维护工具，不是页面功能本身。
3. `docs/` 应描述当前 Flask 主线，而不是旧 `ml_factor` 历史材料。
