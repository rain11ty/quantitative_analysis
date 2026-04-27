# 资产负债表数据工具使用说明

> 最后更新：2026-04-27 | 对应源码：`app/utils/balance_sheet.py` + `app/models/stock_balance_sheet.py`

## 概述

本工具用于从 **Tushare Pro API** 获取 A 股上市公司的资产负债表数据，并写入 MySQL 数据库的 `stock_balance_sheet` 表中。

### 相关文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| 数据抓取脚本 | `app/utils/balance_sheet.py` | 批量抓取所有股票的资产负债表数据 |
| ORM 模型定义 | `app/models/stock_balance_sheet.py` | SQLAlchemy 模型定义（158 个字段） |
| 数据库工具脚本 | `scripts/db_tools/database_explorer.py` | 可用于交互式查看表结构和数据样例 |

## 功能特点

- **数据来源**：Tushare Pro API（`income.balancesheet` 接口）
- **数据范围**：A 股全部上市公司，历史报告期数据
- **数据字段**：完整的资产负债表字段（共约 158 个字段），包括：
  - 基本信息：ts_code / ann_date / end_date / report_type / comp_type
  - 资产类：货币资金/应收账款/存货/固定资产/无形资产/商誉/递延税资产 等
  - 负债类：短期借款/应付账款/长期借款/应付债券/递延税负债 等
  - 权益类：股本/资本公积/盈余公积/未分配利润/少数股东权益 等
  - 金融/保险行业特有科目
- **存储目标**：MySQL 数据库 `stock_cursor.stock_balance_sheet` 表
- **错误处理**：完善的异常处理 + API 频率控制
- **去重策略**：INSERT IGNORE 避免重复数据

## 使用方式

### 方式一：通过数据同步脚本（推荐）

```bash
# 在项目根目录执行
python scripts/sync_tushare_data.py
```

该主同步脚本会调用 `balance_sheet.py` 中的函数完成批量抓取。

### 方式二：通过数据库探索工具查看数据

```bash
python scripts/db_tools/database_explorer.py
# 选择查看 stock_balance_sheet 表的结构和样例数据
```

### 方式三：在 Python 代码中调用

```python
from app.utils.balance_sheet import fetch_and_save_balance_sheet

# 抓取单只股票测试
fetch_and_save_balance_sheet('000001.SZ')

# 或批量抓取全部
fetch_and_save_balance_sheet(all_stocks=True)
```

## 数据表结构要点

```sql
-- 主键为复合主键
PRIMARY KEY (ts_code, ann_date)

-- 核心字段示例：
ts_code          -- 股票代码（如 000001.SZ）
ann_date         -- 公告日期
end_date         -- 报告期
report_type      -- 报报类型（1=合并/2=单季/3=累计）
total_assets     -- 资产总计
total_liab       -- 负债合计
total_hldr_eqy   -- 股东权益合计
money_cap        -- 货币资金
accounts_receiv  -- 应收账款
inventories       -- 存货
fix_assets       -- 固定资产
intan_assets     -- 无形资产
goodwill          -- 商誉
...（共158个字段）
```

## 注意事项

1. **Tushare 权限**：需要 Tushare Pro Token 且有足够积分访问财务数据接口
2. **数据量**：资产负债表数据量大（5000+ 只股票 × 多个报告期），首次全量同步耗时较长
3. **当前状态**：此表数据已抓取并存在于数据库中，ORM 模型已定义（`StockBalanceSheet`），但**当前系统前端页面尚未直接展示**资产负债表数据，作为基本面分析的预留数据层
4. **关联**：与利润表(`stock_income_statement`)、现金流量表共同构成完整的财务三表体系

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| API 调用失败 | Token 过期或积分不足 | 检查 `.env` 中 TUSHARE_TOKEN 配置 |
| 数据插入失败 | 表不存在或字段不匹配 | 确认 `db.create_all()` 已执行或运行迁移脚本 |
| 请求超时 | 数据量过大 | 减小批次大小或分时段执行 |
