# 数据库文档

> 最后更新：2026-04-27 | 本文档包含建表脚本和模型说明

## 一、数据库概况

| 项目 | 值 |
|------|-----|
| **数据库类型** | MySQL 8.0 |
| **字符集** | utf8mb4（`app/models` 和 `config.py` 中统一配置） |
| **数据库名** | stock_cursor（通过 `.env` 的 DB_NAME 配置） |
| **ORM 框架** | SQLAlchemy 2.0+（声明式映射） |
| **连接池** | pool_size=20, pool_recycle=3600s, pool_pre_ping=True |
| **表数量** | 22 张业务表（17 个活跃 + 5 个预留扩展） |

## 二、当前活跃表清单（17 张）

### 用户体系（4 张）

#### 1. users（User 模型）

```sql
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    status ENUM('active', 'disabled', 'banned') DEFAULT 'active',
    avatar_url VARCHAR(500) DEFAULT NULL,
    nickname VARCHAR(80) DEFAULT NULL,
    phone VARCHAR(20) DEFAULT NULL,
    last_login_at DATETIME DEFAULT NULL,
    last_login_ip VARCHAR(45) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户账户表';
```

#### 2. user_watchlist（UserWatchlist）

```sql
CREATE TABLE IF NOT EXISTS user_watchlist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100) DEFAULT NULL,
    market VARCHAR(10) DEFAULT NULL,
    source VARCHAR(20) DEFAULT 'manual',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户自选股表';
```

#### 3. user_analysis_record（AnalysisRecord）

```sql
CREATE TABLE IF NOT EXISTS user_analysis_record (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ts_code VARCHAR(20) DEFAULT NULL,
    stock_name VARCHAR(100) DEFAULT NULL,
    module_name VARCHAR(50) NOT NULL,
    summary TEXT,
    result JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户分析记录表';
```

#### 4. user_chat_history（UserChatHistory — Legacy）

> 注意：此表为 Legacy 表，AI 对话已迁移到 UserAiConversation/UserAiMessage 新体系，但此表仍被 profile 页面的聊天记录预览引用。

```sql
CREATE TABLE IF NOT EXISTS user_chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    source VARCHAR(20) DEFAULT 'ai_assistant',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户聊天记录(Legacy)';
```

---

### AI 对话（2 张）

#### 5. ai_conversations（UserAiConversation）

```sql
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL DEFAULT '新对话',
    summary TEXT,
    status ENUM('active', 'archived', 'deleted') DEFAULT 'active',
    message_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI会话表';
```

#### 6. ai_messages（UserAiMessage）

```sql
CREATE TABLE IF NOT EXISTS ai_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content LONGTEXT NOT NULL,
    token_count INT DEFAULT NULL,
    status ENUM('streaming', 'completed', 'failed') DEFAULT 'completed',
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation (conversation_id, created_at),
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI消息表';
```

---

### 股票基础（3 张）

#### 7. stock_basic（StockBasic）

```sql
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code VARCHAR(20) NOT NULL PRIMARY KEY COMMENT 'TS代码',
    symbol VARCHAR(20) DEFAULT NULL COMMENT '股票代码',
    name VARCHAR(100) DEFAULT NULL COMMENT '股票名称',
    area VARCHAR(100) DEFAULT NULL COMMENT '地域',
    industry VARCHAR(200) DEFAULT NULL COMMENT '所属行业',
    market VARCHAR(10) DEFAULT NULL COMMENT '市场',
    list_date DATE DEFAULT NULL COMMENT '上市日期',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否活跃'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票公司基本信息表';
```

#### 8. stock_business（StockBusiness — 宽表，58 字段）

> 选股筛选用的预聚合宽表。字段过多不在此全部列出，核心包括：
> ts_code / main_business / revenue / cost / profit / growth 等多维度财务/业务指标。

#### 9. stock_shock（StockShock — 异动信息）

```sql
CREATE TABLE IF NOT EXISTS stock_shock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    shock_type VARCHAR(20) NOT NULL COMMENT '异动类型: price_up/down/volume_surge',
    detail TEXT COMMENT '异动详情',
    shock_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ts_code (ts_code),
    INDEX idx_shock_type (shock_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票异动信息表';
```

---

### 行情数据（3 张）

#### 10. stock_daily_history（StockDailyHistory）

```sql
CREATE TABLE IF NOT EXISTS stock_daily_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2) DEFAULT NULL,
    high DECIMAL(10,2) DEFAULT NULL,
    low DECIMAL(10,2) DEFAULT NULL,
    close DECIMAL(10,2) DEFAULT NULL,
    pre_close DECIMAL(10,2) DEFAULT NULL,
    change DECIMAL(10,2) DEFAULT NULL,
    pct_chg DECIMAL(10,4) DEFAULT NULL,
    vol BIGINT UNSIGNED DEFAULT NULL,
    amount DECIMAL(18,2) DEFAULT NULL,
    INDEX idx_ts_date (ts_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='日K线行情历史表';
```

#### 11. stock_daily_basic（StockDailyBasic）

```sql
CREATE TABLE IF NOT EXISTS stock_daily_basic (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close DECIMAL(10,2) DEFAULT NULL,
    turnover_rate DECIMAL(6,3) DEFAULT NULL,
    turnover_rate_f DECIMAL(6,3) DEFAULT NULL,
    volume_ratio DECIMAL(6,3) DEFAULT NULL,
    pe DECIMAL(12,3) DEFAULT NULL,
    pe_ttm DECIMAL(12,3) DEFAULT NULL,
    pb DECIMAL(12,3) DEFAULT NULL,
    ps DECIMAL(12,3) DEFAULT NULL,
    ps_ttm DECIMAL(12,3) DEFAULT NULL,
    dv_ratio DECIMAL(10,3) DEFAULT NULL,
    dv_ttm DECIMAL(10,3) DEFAULT NULL,
    total_share DECIMAL(20,2) DEFAULT NULL,
    float_share DECIMAL(20,2) DEFAULT NULL,
    free_share DECIMAL(20,2) DEFAULT NULL,
    total_mv DECIMAL(20,2) DEFAULT NULL,
    circ_mv DECIMAL(20,2) DEFAULT NULL,
    INDEX idx_ts_date (ts_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='日线基本数据表';
```

#### 12. stock_minute_data（StockMinuteData — 分钟级行情）

```sql
CREATE TABLE IF NOT EXISTS stock_minute_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_time DATETIME NOT NULL,
    open DECIMAL(10,2) DEFAULT NULL,
    high DECIMAL(10,2) DEFAULT NULL,
    low DECIMAL(10,2) DEFAULT NULL,
    close DECIMAL(10,2) DEFAULT NULL,
    volume BIGINT UNSIGNED DEFAULT NULL,
    amount DECIMAL(18,2) DEFAULT NULL,
    INDEX idx_ts_time (ts_code, trade_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='分钟级行情数据表';
```

---

### 技术分析（4 张）

#### 13. stock_factor（StockFactor — 13 种技术因子）

> 核心字段：ts_code / trade_date / macd_dif / macd_dea / macd /
> kdj_k / kdj_d / kdj_j / rsi / cci / boll_upper / boll_mid / boll_lower /
> wr / dmi_plus / dmi_minus / dmi_adx / psy / mtm / emv / roc / obv / vr
> （共约 33 个技术指标字段）

#### 14. stock_ma_data（StockMaData — 均线数据）

> 字段：ts_code / trade_date / ma5 / ma10 / ma20 / ma30

#### 15. stock_moneyflow（StockMoneyflow — 资金流向）

> 字段：ts_code / trade_date /
> buy_elg / sell_elg / lg / sm / mds（超大单/大单/中单/小单）/
> buy_amt / sell_amt / net_mf_inflow / net_mf_inflow_ma 等

#### 16. stock_cyq_perf（StockCyqPerf — 筹码性能）

> 字段：ts_code / trade_date /
> his_low / his_high / cost_5pct / cost_15pct / cost_50pct / cost_85pct / cost_95pct /
> weight_avg / winner_rate

#### 16b. stock_cyq_chips（StockCyqChips — 筹码分布明细）

```sql
CREATE TABLE IF NOT EXISTS stock_cyq_chips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    weight DECIMAL(8,4) NOT NULL COMMENT '该价位筹码占比',
    change_pct DECIMAL(8,4) DEFAULT 0 COMMENT '相比上期变动',
    INDEX idx_ts_date (ts_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='筹码分布明细表';
```

---

### 财务数据（2 张 — 预留扩展）

#### 17. stock_income_statement（StockIncomeStatement — 利润表）

> 89 个字段。ORM 已定义在 `app/models/stock_income_statement.py`。
> 数据抓取脚本在 `app/utils/income_statement.py`。
> 当前状态：**模型和数据已就绪，前端尚未直接展示**。

#### 18. stock_balance_sheet（StockBalanceSheet — 资产负债表）

> 约 158 个字段。ORM 在 `app/models/stock_balance_sheet.py`。
> 数据抓取脚本在 `app/utils/balance_sheet.py`。
> 当前状态：同上，预留扩展。

---

### 系统（1 张）

#### 19. system_log（SystemLog）

```sql
CREATE TABLE IF NOT EXISTS system_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL COMMENT '操作类型: admin_login/user_login/data_sync等',
    message TEXT COMMENT '操作描述',
    user_id INT DEFAULT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    status ENUM('success', 'failed', 'warning') DEFAULT 'success',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_action_type (action_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统操作日志表';
```

---

## 三、预留扩展表（3 张 — 已定义未使用）

以下 5 个 ORM 模型在代码中已定义但当前无 API/页面读写调用：

| # | 表名 | 模型文件 | 预留用途 |
|---|------|---------|---------|
| 20 | trading_signals | `trading_signals.py` | 交易信号（买卖点自动生成） |
| 21 | portfolio_positions | `portfolio_positions.py` | 组合持仓管理 |
| 22 | risk_alerts | `risk_alerts.py` | 风险预警规则 |

> 这些表的存在不影响系统运行（零查询开销），作为未来功能扩展的预留接口。

## 四、数据库初始化与维护

### 自动建表

应用启动时 `db.create_all(checkfirst=True)` 会检查并创建所有已注册模型的表。

### 手动同步数据

```bash
# 全量 Tushare 数据同步
python scripts/sync_tushare_data.py

# 每日增量更新
python scripts/daily_auto_update.py

# 因子补算
python scripts/backfill_factors_v2.py

# 数据健康巡检
python scripts/data_health_check.py
```

### 数据库查看工具

```bash
# 交互式探索
python scripts/db_tools/database_explorer.py

# Web UI 查看
python scripts/db_tools/db_viewer.py
```

### 索引优化

```bash
python scripts/add_db_indexes.py
```
