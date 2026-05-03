# 版本更新说明

## 当前版本信息

- **最新分支**: `codex/current-version-20260428`
- **最新提交**: `3ebfb073` — chore: 更新 .gitignore，排除论文目录和工具生成文件
- **基准版本**: `748a8ab5` — init:股票量化分析系统v1.0（服务器当前版本）
- **变更规模**: 160 个文件变更，+23854 行，-20378 行

---

## 一、数据库表结构变更（部署时需执行 SQL）

### 1.1 新增表（3 张）

#### `stock_shock` — 异常波动数据表
```sql
CREATE TABLE IF NOT EXISTS stock_shock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    name VARCHAR(40),
    trade_market VARCHAR(20),
    reason TEXT,
    period VARCHAR(40),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### `stock_cyq_chips` — 筹码分布数据表
```sql
CREATE TABLE IF NOT EXISTS stock_cyq_chips (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    percent DECIMAL(10,4),
    PRIMARY KEY (ts_code, trade_date, price)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### `user_backtest_result` — 用户回测结果表
```sql
CREATE TABLE IF NOT EXISTS user_backtest_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ts_code VARCHAR(20),
    stock_name VARCHAR(100),
    strategy_type VARCHAR(30) NOT NULL,
    strategy_label VARCHAR(50),
    params JSON,
    start_date VARCHAR(20) NOT NULL,
    end_date VARCHAR(20) NOT NULL,
    initial_capital FLOAT DEFAULT 100000,
    performance JSON,
    trades JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_account(id),
    INDEX idx_user_id (user_id),
    INDEX idx_ts_code (ts_code),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 1.2 修改表（3 张）

```sql
-- user_account 新增字段
ALTER TABLE user_account ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 COMMENT '邮箱是否已验证';

-- user_watchlist 新增字段
ALTER TABLE user_watchlist ADD COLUMN note VARCHAR(255) COMMENT '备注信息';
ALTER TABLE user_watchlist ADD COLUMN sort_order INT DEFAULT 0 COMMENT '排序权重';

-- user_analysis_record 修改字段 + 新增字段
ALTER TABLE user_analysis_record MODIFY COLUMN summary VARCHAR(500) NOT NULL COMMENT 'record summary';
ALTER TABLE user_analysis_record ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'updated time';
```

---

## 二、代码功能变更

### 2.1 新增功能

| 功能 | 说明 |
|------|------|
| **新闻资讯模块** | 集成东方财富、财联社、同花顺 4 个新闻源，支持聚合浏览和原文跳转 |
| **筹码分布分析** | 新增 `stock_cyq_chips` 表和筹码分布展示功能 |
| **异常波动监控** | 新增 `stock_shock` 表，展示个股异常波动（ST、涨跌幅超限等） |
| **回测结果持久化** | 新增 `user_backtest_result` 表，用户回测结果可保存和查看 |
| **分时走势图** | 实时监控页新增分时走势（1/5/15/30/60 分钟），支持 Akshare/Tushare/日线回退三级数据源 |
| **邮件告警服务** | Celery 任务失败时自动发送告警邮件到管理员邮箱 |
| **Docker 部署支持** | 新增 Dockerfile、docker-compose.yml、nginx.conf，支持一键部署 |
| **数据健康检查** | 新增 `data_health_check.py` 脚本和 Celery 定时检查任务，8 项数据完整性校验 |
| **管理后台数据同步** | 管理员可通过 Web 页面手动触发分钟数据同步 |

### 2.2 Bug 修复

| 修复 | 说明 |
|------|------|
| **AI 流式响应超时** | 增加 180 秒总超时，避免连接无限挂起 |
| **数据库连接池耗尽** | 修复 SQLAlchemy 连接池配置 |
| **API 参数校验** | 非法整数参数返回 400 而非 500 |
| **自选股添加失败** | 修复自选股 CRUD 逻辑 |
| **日线时间选择** | 修复日线图时间范围选择器 |
| **Session 丢失** | 修复 HTTP 环境下 COOKIE_SECURE 导致的 session 丢失 |
| **CSS 缓存不更新** | 添加静态文件版本号参数，强制刷新 Nginx 缓存 |
| **管理后台页面** | 修复按钮颜色、健康检查、用户详情页面 |

### 2.3 重构优化

| 优化 | 说明 |
|------|------|
| **数据库配置** | 默认配置提取为模块级常量 |
| **缓存工具** | 删除被覆盖的无效 property 定义 |
| **技术指标计算** | 移除 4 个未使用的计算方法，新增 CCI 指标 |
| **Akshare 导入** | 改为可选导入，缺少依赖时不报错 |
| **静态资源** | 前端 JS/CSS 文件清理，移除未使用的 ML 模块 |

### 2.4 定时任务（Celery Beat）

| 任务 | 时间 | 说明 |
|------|------|------|
| 每日增量更新 | 每天 18:05 | 日线/复权因子/基本面/资金流向/北向资金 + 技术指标重算 |
| 股票列表刷新 | 每周六 08:23 | 从 Tushare 全量刷新 stock_basic |
| 数据健康检查 | 每天 09:07 | 8 项数据完整性校验，异常时邮件告警 |
| 分钟数据同步 | 每天 15:47 | 归档分钟 K 线（默认关闭，需手动启用） |

---

## 三、部署指南

### 3.1 更新代码

```bash
cd /opt/quantitative_analysis
git fetch origin
git checkout codex/current-version-20260428
# 或者 git pull origin codex/current-version-20260428
```

### 3.2 更新数据库表结构

```bash
mysql -u root -p your_database_name < CHANGELOG.md
# 或者手动复制上方 SQL 执行
```

### 3.3 更新依赖

```bash
pip install -r requirements.txt
```

### 3.4 补充缺失数据

```bash
# 全量初始化（首次部署或数据缺失较多时）
python scripts/init_all_data.py --years 3

# 日常增量补充
python scripts/daily_auto_update.py

# 单独补技术指标
python scripts/backfill_factors_v2.py --start-date 20260101
```

### 3.5 重启服务

```bash
# Docker 部署
docker-compose down && docker-compose up -d

# 或手动部署
sudo systemctl restart gunicorn
sudo systemctl restart celery-worker
sudo systemctl restart celery-beat
```

---

## 四、分支说明

| 分支 | 用途 | 状态 |
|------|------|------|
| `master` | 主分支，初始版本 | 服务器当前版本 |
| `codex/current-version-20260428` | **最新开发分支** | 包含所有功能更新和 Bug 修复 |
| `codex-vue-refactor` | Vue 前端重构实验分支 | 实验中，未完成 |
| `fix/pool-exhaust-and-css` | 连接池和 CSS 修复分支 | 已合并到主分支 |
| `upload-clean-20260416` | 清理上传分支 | 已合并 |

**部署建议**: 服务器应切换到 `codex/current-version-20260428` 分支，该分支包含所有最新功能和修复。
