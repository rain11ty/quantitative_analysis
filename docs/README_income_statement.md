# 利润表数据工具使用说明

> 最后更新：2026-04-27 | 对应源码：`app/utils/income_statement.py` + `app/models/stock_income_statement.py`

## 概述

本工具用于从 **Tushare Pro API** 获取 A 股上市公司的利润表数据，并写入 MySQL 数据库的 `stock_income_statement` 表中。

### 相关文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| 数据抓取脚本 | `app/utils/income_statement.py` | 批量抓取利润表数据 |
| ORM 模型定义 | `app/models/stock_income_statement.py` | SQLAlchemy 模型定义（89 个字段） |

## 功能特点

- **数据来源**：Tushare Pro API（`income.income` 接口）
- **数据字段**：完整的利润表字段（89 个字段），包括：
  - **核心指标**：基本每股收益/稀释每股收益/营业总收入/营业成本/营业利润/净利润/归属于母公司净利润
  - **收入项目**：利息收入/保费收入/手续费收入/投资净收益/公允价值变动收益
  - **成本费用**：销售费用/管理费用/财务费用/研发费用/资产减值损失
  - **重要衍生指标**：EBIT(息税前利润)/EBITDA(息税折旧摊销前利润)
- **存储目标**：MySQL 数据库 `stock_cursor.stock_income_statement` 表
- **错误处理**：完善异常处理 + API 频率控制（批次间隔 1 秒，每批 50 只股票）

## 数据表结构要点

```sql
-- 主键通常为复合主键
-- 核心字段：
ts_code                -- 股票代码
ann_date               -- 公告日期
end_date               -- 报告期
basic_eps              -- 基本每股收益
diluted_eps            -- 稀释每股收益
total_revenue           -- 营业总收入
revenue                 -- 营业收入
total_cogs             -- 营业总成本
oper_cost              -- 营业成本
operate_profit         -- 营业利润
total_profit           -- 利润总额
n_income               -- 净利润
n_income_attr_p        -- 归母净利润
ebit                   -- 息税前利润
ebitda                 -- 息税折旧摊销前利润
sell_exp               -- 销售费用
admin_exp              -- 管理费用
fin_exp                -- 财务费用
rd_exp                 -- 研发费用
assets_impair_loss     -- 资产减值损失
...（共89个字段）
```

## 使用方式

### 通过数据同步脚本（推荐）

```bash
python scripts/sync_tushare_data.py
```

### 通过数据库探索工具查看

```bash
python scripts/db_tools/database_explorer.py
# 查看 stock_income_statement 表
```

### 在代码中调用

```python
from app.utils.income_statement import fetch_and_save_income_statement

# 单只股票测试
fetch_and_save_income_statement('000001.SZ')

# 全量抓取
fetch_and_save_income_statement(all_stocks=True)
```

## 数据应用场景

### 1. 盈利能力分析
- **毛利率** = (营业收入 − 营业成本) / 营业收入
- **净利率** = 净利润 / 营业收入
- **ROE（净资产收益率）** = 净利润 / 平均净资产

### 2. 成本管控分析
- **费用率** = (销售+管理+财务+研发费用) / 营业收入
- **研发投入比** = 研发费用 / 营业收入（关注高科技创新企业）

### 3. 成长性分析
- 营业收入同比/环比增长率
- 净利润增长率趋势
- EPS（每股收益）增长轨迹

### 4. 量化策略
- 基于财务因子的选股（PE/PB/ROE/营收增长等多因子模型）
- 质量价值筛选（高 ROE + 低 PE + 稳定盈利）
- 财务异常预警（突然亏损/营收大幅下滑）

## 注意事项

1. **Tushare 权限**：需要有效 Token 和足够积分
2. **数据量**：5000+ 只股票 × 多个报告期，首次全量同步耗时较长
3. **当前状态**：ORM 模型和抓取脚本均已就绪，数据已入库；**前端尚未直接展示**利润表详情，作为基本面分析预留数据层
4. **与财务三表的关系**：利润表 + 资产负债表 + 现金流量表构成完整的财务分析体系
5. **数据更新建议**：配合 `scripts/daily_auto_update.py` 定期增量更新
