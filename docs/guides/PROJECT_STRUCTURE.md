# 项目结构说明

> 最后更新：2026-04-27

## 活跃区域

### `app/` — Flask 应用主体

当前运行中的 Web 应用，采用 MVC + Blueprint 分层架构：

| 子目录 | 职责 | 文件数 |
|--------|------|-------|
| `api/` | JSON API 接口层（url_prefix=/api） | 6（5个模块 + __init__） |
| `main/` | 页面路由蓝图（无前缀，9个页面） | 2 |
| `routes/` | 认证路由(/auth/*) + 管理后台(/admin/*) | 2 |
| `services/` | 业务逻辑层（13个服务） | 13 |
| `models/` | SQLAlchemy ORM 模型（22个模型） | 20 |
| `templates/` | Jinja2 HTML 模板（24个文件） | 24（含子目录） |
| `static/` | 静态资源（CSS/JS/Logo/Vendor库） | ~10 |
| `utils/` | 基础工具函数与数据同步脚本（25个模块） | 25 |

**根目录额外文件**：
- `celery_app.py` — Celery 异步任务队列配置（已配置，预留扩展）
- `tasks.py` — Celery 定时任务定义
- `extensions.py` — db / redis_client / mail 扩展实例

### `scripts/` — 工具脚本集中区

手工脚本和运维脚本按功能分子目录存放：

| 子目录 | 内容 | 文件数 |
|--------|------|-------|
| （根级） | 数据同步/索引优化/因子补算/每日更新/数据巡检/迁移脚本 | 7 |
| `db_tools/` | 数据库查看工具（explorer + viewer） | 3 |
| `diagnostics/` | 连通性检查、烟雾测试 | 4 |
| `setup/` | 初始化准备脚本（风险表/模型生成） | 4 |

### `docs/` — 项目文档

| 子目录 | 内容 | 状态 |
|--------|------|------|
| `guides/` | 当前有效的说明文档 | ✅ 活跃 |
| `analysis/` | 分析记录和历史审查 | 参考 |
| `archive/ml_factor/` | 已下线多因子模块归档（7个文件） | 历史资料 |
| （根级） | 完整指南 / CRUD审计报告 / Vue重构计划 / 财务工具说明 | 大部分已更新至 2026-04-27 |

### 其他重要目录

| 目录 | 说明 |
|------|------|
| `deploy/` | Nginx 反向代理配置 + systemd 服务单元 |
| `models/` | 预训练 ML 模型（.pkl 文件） |
| `Data Dictionary/` | 数据字典文档（实时行情接口 + 新闻资讯接口） |
| `论文_第4章_系统实现/diagrams/` | 论文配图（7 个 .drawio 图：框架图/类图/时序图/流程图） |
| `init.sql/` | 数据库 SQL 初始化脚本 |
| `ssl-certs/` | SSL 证书（HTTPS 可选） |

## 根目录文件规范

仓库根目录只保留以下几类文件：

**必须保留**：
- 应用入口：`run.py`、`quick_start.py`、`run_system.py`
- 配置与依赖：`config.py`、`requirements*.txt`
- 部署文件：`Dockerfile`、`docker-compose*.yml`、`gunicorn.conf.py`
- 平台启动脚本：`start.bat`、`start.sh`、`stop-docker.bat`、`start-docker.bat`
- 编码修复：`runtime_encoding.py`
- 数据备份：`_dump_docker_empty.sql`、`stock_analysis.db`

**不应堆在根目录**：
- 一次性编码/修复脚本 → 放 `scripts/`
- 临时测试脚本 → 放 `scripts/diagnostics/` 或直接删除
- 手工导出的排障文本 → 放 `docs/reports/` 或删除
- 已删除功能的页面资源 → 清理或归档到 `docs/archive/`

## 架构概要图

```
quantitative_analysis/
├── app/                          # Flask 应用核心（MVC 全套）
│   ├── api/                     # 5个API模块（stock/analysis/news/monitor/ai）
│   ├── main/                    # 页面视图（9个页面路由）
│   ├── routes/                  # auth_routes(认证) + admin_routes(管理后台)
│   ├── services/               # 13个业务服务
│   ├── models/                 # 22个ORM模型（17活跃+5预留）
│   ├── templates/              # 24个Jinja2模板
│   ├── static/                 # CSS/JS/Logo/Vendor库
│   ├── utils/                  # 25个工具模块
│   ├── celery_app.py          # Celery配置（预留）
│   └── tasks.py                # Celery任务定义（预留）
├── config.py                   # 配置中心
├── run.py                       # 启动入口(:5001)
├── docker-compose.yml           # 生产编排（4容器）
├── scripts/                     # 工具脚本（18个文件）
├── docs/                        # 文档（14个md文件 + 归档）
├── deploy/                      # Nginx + systemd
├── models/                      # ML模型资产
├── Data Dictionary/            # 数据字典
└── 论文_第4章_系统实现/         # 论文配图
```

## 新增模块记录（相对于早期版本）

相比项目初期，以下模块是后续新增的：

1. **新闻资讯模块**（2026-04）：`news_api.py` + `news_service.py` + `news.html` — 4源聚合
2. **邮件服务**（2026-04）：`email_service.py` — Resend SMTP 验证码发送
3. **Celery 异步队列**（2026-04）：`celery_app.py` + `tasks.py` — 预留扩展
4. **Redis 双层缓存**（2026-04）：`cache_utils.py` + Redis 可选降级为内存字典
5. **筹码分布明细模型**（2026-04）：`stock_cyq_chips.py` — 新增 Chips 表
6. **异动信息模型**（2026-04）：`stock_shock.py` — 新增 Shock 表
7. **管理员健康检查页**（2026-04）：`admin/health_check.html` — 四组件一键检测
8. **数据自动更新调度**（2026-04）：`daily_auto_update.py` — 增量同步宽表
9. **数据健康巡检**（2026-04）：`data_health_check.py` — 表完整性检测
10. **论文配图**（2026-04）：`论文_第4章_系统实现/` — 7 张 Drawio 图
