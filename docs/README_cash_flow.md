# 现金流量表数据工具使用说明

> 最后更新：2026-04-27 | 对应源码：`app/utils/cash_flow.py`

## 概述

本工具用于从 **Tushare Pro API** 获取 A 股上市公司的现金流量表数据，并写入 MySQL 数据库。

### 相关文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| 数据抓取脚本 | `app/utils/cash_flow.py` | 批量抓取现金流量表数据 |

> 注：现金流量表当前作为数据抓取工具存在于 `app/utils/` 层，如需对应 ORM 模型需新建 `stock_cashflow.py`（目前系统中暂无独立的 CashFlow ORM 模型）。

## 功能特点

- **数据来源**：Tushare Pro API（`cashflow` 接口）
- **数据字段**：完整的现金流量表字段（约 91 个字段），包括：
  - **经营活动现金流**：销售收现/购货付现/支付税费/经营净额(NCF)/间接法净额
  - **投资活动现金流**：投资收回/投资支付/购建固定资产/投资净额
  - **筹资活动现金流**：吸收投资/取得借款/偿还债务/分配股利/筹资净额
  - **现金及等价物**：汇率影响/净增加额/期初余额/期末余额
  - **间接法补充项目**：资产减值准备/折旧摊销/信用减值损失
  - 金融/保险行业特有科目
- **错误处理**：异常处理 + API 频率控制
- **去重策略**：INSERT IGNORE 避免重复数据

## 核心字段一览

| 分类 | 示例字段 |
|------|---------|
| 经营活动 | `n_cashflow_act`(经营净额) / `c_fr_sale_sg`(销售收现) / `c_paid_goods_s`(购货付现) / `st_cash_out_act`(经营流出小计) |
| 投资活动 | `n_cashflow_inv_act`(投资净额) / `c_pay_acq_const_fiolta`(购建固定资产) / `c_disp_withdrwl_invest`(投资收回) |
| 筹资活动 | `n_cash_flows_fnc_act`(筹资净额) / `c_recp_cap_contrib`(吸收投资) / `c_prepay_amt_borr`(偿还债务) / `c_pay_dist_dpcp_int_exp`(分配股利) |
| 现金余额 | `n_incr_cash_cash_equ`(净增加额) / `c_cash_equ_end_period`(期末余额) |
| 重要指标 | `net_profit`(净利润) / `free_cashflow`(自由现金流量) / `finan_exp`(财务费用) |

## 使用方式

### 通过数据同步脚本

```bash
python scripts/sync_tushare_data.py
```

主同步脚本会按需调用各数据抓取模块，包括现金流量表。

### 在代码中调用

```python
from app.utils.cash_flow import fetch_and_save_cashflow

# 抓取单只股票
fetch_and_save_cashflow('000001.SZ')

# 批量抓取
fetch_and_savecashflow(all_stocks=True)
```

## 现金流量分析应用场景

### 现金流量质量评估
- **经营净额/净利润 > 1**：盈利质量好
- **自由现金流为正且稳定**：公司自我造血能力强
- **持续正的经营现金流**：公司经营健康

### 现金流量模式识别
1. **成长型**：经营(+)/投资(-)/筹资(+) — 扩张期
2. **成熟型**：经营(+)/投资(-)/筹资(-) — 回报期
3. **衰退型**：经营(-)/投资(+)/筹资(±) — 萎缩期

### 量化策略应用
- 基于现金流的选股因子
- 现金流异常检测
- 企业价值评估（DCF 模型输入）

## 注意事项

1. **Tushare 权限**：需要有效 Token 和足够积分
2. **数据量**：全量抓取耗时较长，建议分批执行
3. **当前集成状态**：抓取工具已实现，可作为独立脚本或被 `sync_tushare_data.py` 调用
4. **与系统的关系**：现金流量数据属于财务数据层的组成部分，目前系统前端尚未直接展示此类详细财务数据，作为预留扩展
