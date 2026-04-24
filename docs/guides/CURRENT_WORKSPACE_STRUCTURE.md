# 当前工作区项目结构说明

本文基于当前工作区实际存在的文件整理，时间点为 `2026-04-23`。

说明口径：

- 以“当前工作区实际存在的文件”为主，不把 `.venv`、`.git`、`__pycache__`、`logs/`、`data/` 这类运行期目录混入主结构。
- 单独补充 “Git 已记录但当前工作区已删除的历史文件”，避免把历史残留误认为当前主链路。
- “有效代码行数”按非空行、去掉纯注释行的近似口径统计；Markdown、图片、模型、数据库文件不计入代码量。

## 一、项目是怎么连起来的

当前主链路是一个典型的 Flask 分层应用：

`run.py / quick_start.py / run_system.py`
→ `app.create_app()`
→ 注册蓝图 `app/api`、`app/main`、`app/routes`
→ 页面模板 `app/templates` 和静态资源 `app/static`
→ 业务层 `app/services`
→ ORM 模型层 `app/models`
→ 基础能力与外部数据接口 `app/utils`
→ MySQL / Tushare / Akshare / LLM 服务

更细一点：

- 页面访问走 `app/main/views.py`，直接返回模板。
- 模板里的 JS 统一通过 `base.html` 里的 `apiRequest()` 调用 `/api/...`。
- `/api/...` 请求由 `app/api/*.py` 接收，再转到 `app/services/*.py`。
- 服务层再去查 `app/models/*.py` 对应的数据表，或通过 `app/utils/db_utils.py`、`app/services/akshare_service.py`、`MarketOverviewService` 等访问外部数据源。
- 用户登录、个人中心、后台管理则走 `app/routes/auth_routes.py` 和 `app/routes/admin_routes.py`。
- `app/__init__.py` 负责把这些模块装起来，同时统一处理鉴权、Session、CORS、限流、错误页和 `/healthz`。

## 二、顶层目录总览

- `app/`: 当前运行中的 Flask 主应用。
- `deploy/`: Nginx、systemd 等部署示例。
- `docs/`: 当前文档、分析记录、归档资料。
- `images/`: 文档截图资源。
- `models/`: 演示模型文件。
- `scripts/`: 数据同步、诊断、数据库查看、初始化脚本。
- `.codebuddy/`: 辅助修复脚本。
- 根目录：启动入口、配置、依赖、容器文件、运行时数据库/SQL 导出。

## 三、当前工作区逐文件说明

### 1. 根目录与隐藏文件

- `.codebuddy/fix_template_encoding.py`: 模板编码修复辅助脚本。
- `.dockerignore`: Docker 构建时忽略文件规则。
- `.env`: 本地运行环境变量配置。
- `.env.example`: 环境变量示例模板。
- `.gitignore`: Git 忽略规则。
- `README.md`: 项目简介、启动方式和目录入口说明。
- `config.py`: Flask 配置中心，含数据库、日志、LLM、Session、安全配置。
- `docker-compose.dev.yml`: 开发环境的 Docker Compose 配置。
- `docker-compose.yml`: 常规容器编排配置。
- `Dockerfile`: 两阶段构建的应用镜像定义。
- `gen_doc.py`: 文档生成辅助脚本。
- `gen_md.py`: Markdown 文档生成辅助脚本。
- `gunicorn.conf.py`: Gunicorn 运行配置。
- `quick_start.py`: 轻量本地启动器。
- `requirements-base.txt`: 基础依赖集合。
- `requirements-dev.txt`: 开发依赖集合。
- `requirements-ml.txt`: 机器学习相关依赖集合。
- `requirements-prod.txt`: 生产部署额外依赖集合。
- `requirements.txt`: 主依赖入口。
- `requirements_minimal.txt`: 最小化依赖集合。
- `run.py`: 标准 Flask 启动入口。
- `run_system.py`: 交互式系统管理入口，可检查依赖、初始化数据库、展示结构。
- `runtime_encoding.py`: Windows/控制台 UTF-8 环境修复工具。
- `start-docker.bat`: Windows 下启动 Docker 环境。
- `start.bat`: Windows 下直接启动应用。
- `start.sh`: Linux/macOS 下直接启动应用。
- `stock_analysis.db`: 当前工作区内的本地 SQLite 数据库文件。
- `stock_cursor.sql`: 大体量 SQL 导出/备份文件。
- `stop-docker.bat`: Windows 下停止 Docker 环境。
- `Microsoft/Windows/PowerShell/ModuleAnalysisCache`: PowerShell 模块分析缓存，不属于业务代码。

### 2. `app/` 应用装配层

- `app/__init__.py`: Flask 工厂函数、蓝图注册、Session/鉴权/CORS/限流/错误处理/健康检查总入口。
- `app/extensions.py`: Flask-SQLAlchemy 的 `db` 扩展实例。

### 3. `app/api/` JSON API 层

- `app/api/__init__.py`: API 蓝图定义与路由模块装载入口。
- `app/api/ai_assistant_api.py`: AI 会话列表、消息历史、重命名、删除、聊天、流式输出、状态检查接口。
- `app/api/analysis_api.py`: 条件选股与简化回测接口；文件内还内置了一个页面使用的轻量 `BacktestEngine`。
- `app/api/realtime_monitor_api.py`: 实时监控页所需的仪表盘和单股详情接口。
- `app/api/stock_api.py`: 股票列表、详情、历史、因子、资金流、筹码分布、行业/地区、自选股等接口。

### 4. `app/main/` 页面入口层

- `app/main/__init__.py`: 页面蓝图定义与视图装载入口。
- `app/main/views.py`: 首页、股票列表、详情、分析、选股、回测、AI 助手、实时监控的页面路由。

### 5. `app/routes/` 认证与后台页面层

- `app/routes/admin_routes.py`: 管理员登录、用户管理、日志查看、数据中心、单股分钟数据同步。
- `app/routes/auth_routes.py`: 用户登录、注册、忘记密码、个人中心、资料更新、密码更新、自选股与历史记录保存。

### 6. `app/services/` 业务服务层

- `app/services/__init__.py`: 服务包初始化文件。
- `app/services/ai_conversation_service.py`: AI 对话会话与消息持久化、上下文裁剪、流式回复状态管理。
- `app/services/akshare_service.py`: Akshare/Sina 快照封装，主要服务于实时行情、指数、市场统计，并带代理诊断。
- `app/services/backtest_engine.py`: 预留的高级回测引擎接口，面向未来多因子/组合优化扩展。
- `app/services/llm_service.py`: 对接 Ollama / OpenAI 兼容接口 / DeepSeek 的统一 LLM 调用层。
- `app/services/market_overview_service.py`: 市场概览服务，按 Akshare → Tushare → 本地缓存三级降级获取指数和涨跌家数。
- `app/services/minute_data_sync_service.py`: 通过 Baostock 同步分钟线数据到数据库。
- `app/services/realtime_monitor_service.py`: 实时监控页的数据拼装层，负责报价、K 线、信号和自选联动。
- `app/services/stock_service.py`: 股票查询主服务，负责列表、搜索、详情、因子、资金流、筹码分布和条件筛选。
- `app/services/system_log_service.py`: 系统日志落库服务。
- `app/services/user_activity_service.py`: 自选股、分析记录、聊天记录等用户活动写入服务。

### 7. `app/models/` ORM 模型层

- `app/models/__init__.py`: 所有 SQLAlchemy 模型的统一导出入口。
- `app/models/ai_conversation.py`: AI 会话表与 AI 消息表模型。
- `app/models/portfolio_positions.py`: 组合持仓表模型。
- `app/models/risk_alerts.py`: 风险预警表模型。
- `app/models/stock_balance_sheet.py`: 资产负债表数据模型。
- `app/models/stock_basic.py`: 股票基础信息模型。
- `app/models/stock_business.py`: 业务宽表模型，承载选股筛选的宽字段集合。
- `app/models/stock_cyq_perf.py`: 筹码分布数据模型。
- `app/models/stock_daily_basic.py`: 每日基础指标模型。
- `app/models/stock_daily_history.py`: 日线行情模型。
- `app/models/stock_factor.py`: 技术因子模型。
- `app/models/stock_income_statement.py`: 利润表数据模型。
- `app/models/stock_ma_data.py`: 均线结果模型。
- `app/models/stock_minute_data.py`: 分钟线行情模型。
- `app/models/stock_moneyflow.py`: 资金流向模型。
- `app/models/system_log.py`: 系统操作日志模型。
- `app/models/trading_signals.py`: 交易信号模型。
- `app/models/user.py`: 用户账户模型，含角色、状态、密码哈希和关联关系。
- `app/models/user_activity.py`: 用户自选股、分析记录、聊天历史模型。

### 8. `app/utils/` 基础工具与数据同步辅助层

- `app/utils/__init__.py`: 工具包初始化文件。
- `app/utils/api_helpers.py`: API 统一异常包装、统一响应结构辅助函数。
- `app/utils/auth.py`: 登录校验、管理员校验装饰器。
- `app/utils/balance_sheet.py`: 资产负债表数据抓取/写入辅助脚本。
- `app/utils/baostock_daily.py`: 使用 Baostock 获取日线/分钟数据的辅助脚本。
- `app/utils/cash_flow.py`: 现金流量表数据抓取/写入辅助脚本。
- `app/utils/cyq_perf.py`: 筹码分布数据处理辅助脚本。
- `app/utils/daily_basic.py`: 每日基础指标抓取/写入辅助脚本。
- `app/utils/daily_history_by_code.py`: 按股票代码抓取日线历史辅助脚本。
- `app/utils/daily_history_by_date.py`: 按日期抓取日线历史辅助脚本。
- `app/utils/db_utils.py`: MySQL 和 Tushare 初始化工具。
- `app/utils/income_statement.py`: 利润表数据抓取/写入辅助脚本。
- `app/utils/logger.py`: 日志初始化工具。
- `app/utils/ma_calculator.py`: EMA/均线计算辅助函数。
- `app/utils/min15.py`: 15 分钟线抓取辅助脚本。
- `app/utils/min30.py`: 30 分钟线抓取辅助脚本。
- `app/utils/min5.py`: 5 分钟线抓取辅助脚本。
- `app/utils/min60.py`: 60 分钟线抓取辅助脚本。
- `app/utils/moneyflow.py`: 资金流向抓取/写入辅助脚本。
- `app/utils/moneyflow_ths.py`: 同花顺口径资金流辅助脚本。
- `app/utils/stk_factor.py`: 技术因子抓取/计算辅助脚本。
- `app/utils/stock_basic.py`: 股票基础信息抓取辅助脚本。
- `app/utils/stock_company.py`: 公司信息抓取辅助脚本。
- `app/utils/trade_calendar.py`: 交易日历抓取辅助脚本。

### 9. `app/templates/` 前端页面模板

- `app/templates/base.html`: 全站基础模板、导航栏、统一样式入口、`apiRequest()` JS 工具。
- `app/templates/index.html`: 首页，展示市场情绪、指数走势、系统状态。
- `app/templates/stocks.html`: 股票列表页，支持行业/地区/搜索筛选。
- `app/templates/stock_detail.html`: 个股详情页，展示历史、因子、资金流、筹码和自选股操作。
- `app/templates/analysis.html`: 个股分析主页面，前端逻辑很重，是页面代码量最大的模板之一。
- `app/templates/screen.html`: 条件选股页面。
- `app/templates/backtest.html`: 回测操作页面。
- `app/templates/ai_assistant.html`: AI 金融助手页面，支持会话管理和流式回答。
- `app/templates/realtime_monitor.html`: 实时监控页，展示行情面板、单股走势、监控信号。
- `app/templates/errors/404.html`: 404 页面。
- `app/templates/errors/429.html`: 429 限流页面。
- `app/templates/errors/500.html`: 500 错误页面。
- `app/templates/auth/login.html`: 用户登录页。
- `app/templates/auth/register.html`: 用户注册页。
- `app/templates/auth/forgot_password.html`: 忘记密码页。
- `app/templates/auth/profile.html`: 个人中心页。
- `app/templates/admin/login.html`: 后台登录页。
- `app/templates/admin/dashboard.html`: 后台概览页。
- `app/templates/admin/users.html`: 用户列表管理页。
- `app/templates/admin/user_detail.html`: 单用户详情页。
- `app/templates/admin/logs.html`: 系统日志查看页。
- `app/templates/admin/data.html`: 数据中心与单股同步入口页。

### 10. `app/static/` 静态资源

- `app/static/css/account-admin.css`: 个人中心与后台管理样式。
- `app/static/css/financial-theme.css`: 全站金融主题样式。
- `app/static/css/mobile.css`: 移动端专用样式。
- `app/static/css/responsive-financial.css`: 响应式布局样式。
- `app/static/js/mobile.js`: 移动端交互逻辑。

### 11. `scripts/` 工具脚本

- `scripts/backfill_factors.py`: 基于日线历史补算技术因子并回填 `stock_factor`。
- `scripts/sync_tushare_data.py`: 大批量同步 Tushare 数据到 MySQL 的主脚本。
- `scripts/db_tools/README.md`: 数据库工具目录说明。
- `scripts/db_tools/database_explorer.py`: 数据库探索与自定义因子生成辅助工具。
- `scripts/db_tools/db_viewer.py`: 数据库表结构与样例数据查看工具。
- `scripts/diagnostics/README.md`: 诊断脚本说明。
- `scripts/diagnostics/market_overview_item_errors.py`: 检查市场概览返回项的错误情况。
- `scripts/diagnostics/market_overview_smoke.py`: 快速跑通市场概览接口的烟雾检查。
- `scripts/diagnostics/tushare_connection_check.py`: Tushare 连接诊断脚本，偏手工排障用途。
- `scripts/setup/create_risk_tables.py`: 创建风险相关表及示例数据。
- `scripts/setup/create_simple_demo_model.py`: 生成简单演示模型文件。
- `scripts/setup/create_simple_prediction_service.py`: 生成简单预测服务原型。
- `scripts/setup/create_working_model.py`: 生成可工作的模型示例文件。

### 12. `deploy/` 部署文件

- `deploy/nginx.conf`: Nginx 反向代理配置示例。
- `deploy/stock-analysis.service`: systemd 服务配置示例。

### 13. `docs/` 文档文件

- `docs/VUE_REFACTOR_PLAN.md`: 前端 Vue 化改造计划文档。
- `docs/README_balance_sheet.md`: 资产负债表数据工具说明。
- `docs/README_cash_flow.md`: 现金流量表数据工具说明。
- `docs/README_income_statement.md`: 利润表数据工具说明。
- `docs/analysis/CURRENT_PROJECT_REVIEW.md`: 当前项目审查记录。
- `docs/analysis/DEVELOPMENT_SUMMARY.md`: 项目开发总结。
- `docs/guides/CURRENT_WORKSPACE_STRUCTURE.md`: 当前这份工作区结构说明。
- `docs/guides/DATABASE_TOOLS_README.md`: 数据库工具使用说明。
- `docs/guides/ENHANCED_FINANCIAL_FACTORS_README.md`: 增强财务因子说明。
- `docs/guides/INSTALL_GUIDE.md`: 安装指南。
- `docs/guides/PROJECT_STRUCTURE.md`: 项目结构说明文档。
- `docs/guides/Text2SQL功能列表.md`: Text2SQL 相关功能规划说明。
- `docs/guides/data_requirements_for_real_training.md`: 真实价格训练数据需求说明。
- `docs/guides/database.md`: 数据库脚本/说明总文档。
- `docs/reports/operation_log.md`: 操作日志记录。
- `docs/archive/ml_factor/ML_FACTOR_README.md`: 旧版多因子模块归档说明。
- `docs/archive/ml_factor/README.md`: 旧版多因子模块归档入口。
- `docs/archive/ml_factor/task.md`: 旧版多因子模块任务记录。
- `docs/archive/ml_factor/多因子模型系统功能列表.md`: 旧版多因子模块功能清单归档。
- `docs/archive/ml_factor/多因子模型系统完整指南.md`: 旧版多因子模块完整指南归档。
- `docs/archive/ml_factor/多因子模型系统实现总结.md`: 旧版多因子模块实现总结归档。
- `docs/archive/ml_factor/系统总结.md`: 旧版系统总结归档。
- `docs/archive/ml_factor/项目功能分析与优化建议.md`: 旧版项目分析与优化建议归档。

### 14. `models/` 模型资产

- `models/demo_model_v2.pkl`: 演示用模型文件。
- `models/demo_model_v2_scaler.pkl`: 演示模型对应的缩放器文件。

### 15. `images/` 截图资源

- `images/1-2.png`: 文档截图资源。
- `images/1-3.png`: 文档截图资源。
- `images/1-4.png`: 文档截图资源。
- `images/1-5.png`: 文档截图资源。
- `images/1-6.png`: 文档截图资源。
- `images/1-7.png`: 文档截图资源。
- `images/1-8.png`: 文档截图资源。
- `images/1-9.png`: 文档截图资源。
- `images/1-10.png`: 文档截图资源。
- `images/1-11.png`: 文档截图资源。
- `images/1-12.png`: 文档截图资源。
- `images/1-13.png`: 文档截图资源。
- `images/1-14.png`: 文档截图资源。
- `images/1-15.png`: 文档截图资源。
- `images/1-16.png`: 文档截图资源。
- `images/1-17.png`: 文档截图资源。
- `images/1-18.png`: 文档截图资源。
- `images/1-19.png`: 文档截图资源。
- `images/1-20.png`: 文档截图资源。
- `images/1-21.png`: 文档截图资源。
- `images/1-22.png`: 文档截图资源。

## 四、哪些文件是当前运行主链路的关键节点

最关键的入口和枢纽文件如下：

- `run.py`: 应用启动。
- `app/__init__.py`: 应用工厂和所有蓝图/中间逻辑的装配中心。
- `app/main/views.py`: 页面入口。
- `app/api/stock_api.py`: 股票数据 API。
- `app/api/analysis_api.py`: 选股/回测 API。
- `app/api/ai_assistant_api.py`: AI 助手 API。
- `app/api/realtime_monitor_api.py`: 实时监控 API。
- `app/services/stock_service.py`: 股票数据主服务。
- `app/services/realtime_monitor_service.py`: 实时监控主服务。
- `app/services/market_overview_service.py`: 市场概览服务。
- `app/services/akshare_service.py`: 实时行情与指数快照服务。
- `app/services/llm_service.py`: 大模型调用服务。
- `app/models/*.py`: 数据库表结构。
- `app/templates/base.html`: 前端基础壳与统一 API 调用入口。

## 五、Git 里仍记录但当前工作区已删除的历史文件

当前 `git status` 显示，下面这类文件仍在 Git 记录里，但工作区已经删除，说明仓库仍有“待清理的历史残留”：

- 历史一次性脚本：`check.py`、`convert.py`、`convert2.py`、`dump_db.py`、`extract.py`、`fix_encoding.py`、`fix_screen.py`、`inspect_db.py`、`restore.py`。
- 历史测试脚本：`test_market.py`、`test_market2.py`、`test_tushare_connection.py`。
- 历史多因子前端：`templates/ml_factor/index.html`、`static/js/ml_factor.js`。
- 历史文档：旧版 `docs/analysis/*`、`docs/guides/*`、`docs/ML_FACTOR_README.md` 等。
- 历史输出/杂项：`git-push.err.txt`、`git-push.out.txt`、`tool_calls.txt`、`tk.csv`、`db_schema_dump.json`、`_docker-daemon-config.json`。

这些内容不应再视为当前运行主线的一部分。

## 六、有效代码行数

统计口径：仅统计当前工作区实际存在的代码/配置文件，按非空行、去掉纯注释行近似计算。

### 1. 当前工作区总有效代码行数

- 总计：`21766` 行

### 2. 按语言拆分

- Python：`10922` 行
- HTML：`8051` 行
- CSS：`2054` 行
- JavaScript：`404` 行

### 3. 按区域拆分

- `app/` 主应用：`18918` 行
- `scripts/` 工具脚本：`2100` 行
- 根目录启动/配置脚本：`389` 行
- 部署配置：`335` 行

### 4. 代码量最大的文件

- `app/templates/analysis.html`: `1737` 行
- `app/templates/stock_detail.html`: `1243` 行
- `app/templates/ai_assistant.html`: `1139` 行
- `app/templates/realtime_monitor.html`: `890` 行
- `app/services/akshare_service.py`: `721` 行
- `scripts/sync_tushare_data.py`: `662` 行
- `app/templates/screen.html`: `625` 行
- `app/services/stock_service.py`: `589` 行
- `app/services/realtime_monitor_service.py`: `544` 行

### 5. 一个有用的结论

这个项目的“重心”其实非常明显：

- 后端主逻辑集中在 `app/services/*.py`。
- 前端复杂度主要集中在几个大模板：`analysis.html`、`stock_detail.html`、`ai_assistant.html`、`realtime_monitor.html`。
- 所以如果后续要做重构，最值得优先拆分的不是模型层，而是“重模板 + 重服务文件”。
