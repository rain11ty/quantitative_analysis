# 资产负债表脚本说明

> 更新日期：`2026-04-28`
> 对应文件：`app/utils/balance_sheet.py`

## 1. 当前定位

`app/utils/balance_sheet.py` 是仓库中保留的资产负债表同步脚本。

它与当前项目的连接方式是：

- ORM 模型存在：`StockBalanceSheet`
- 数据表存在：`stock_balance_sheet`
- 页面和 API 暂未直接使用

所以它当前属于“数据层预留能力”，不是用户端已开放功能。

## 2. 脚本职责

这个脚本主要负责：

- 创建 `stock_balance_sheet`
- 通过 Tushare 拉取资产负债表数据
- 批量写入 MySQL

适合离线补数或人工初始化，不适合作为页面请求时的实时任务。

## 3. 如何运行

从项目根目录执行：

```bash
python app/utils/balance_sheet.py
```

运行前需要准备：

- 有效的 MySQL 连接
- 正确的 `.env` 数据库配置
- 可用的 `TUSHARE_TOKEN`

## 4. 当前项目里它不做什么

它当前不会：

- 自动被 `run.py` 调用
- 自动被 `scripts/sync_tushare_data.py` 调用
- 直接出现在股票详情页或筛选页

因此文档与答辩材料里如果提到它，应该明确写成“财务数据预留层”。

## 5. 推荐维护方式

如果后续仍要保留这类脚本，建议：

1. 把脚本迁移到 `scripts/` 目录。
2. 为执行入口增加参数化控制。
3. 给同步结果增加明确的日志和失败统计。
4. 只有在查询接口稳定后，再考虑前端展示。
