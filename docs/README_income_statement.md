# 利润表脚本说明

> 更新日期：`2026-04-28`
> 对应文件：`app/utils/income_statement.py`

## 1. 当前定位

`app/utils/income_statement.py` 是一个脚本式的 Tushare 利润表同步工具，不属于当前 Web 页面或 API 的主链路。

当前项目里与它相关的正式数据层只有：

- ORM 模型：`app/models/stock_income_statement.py`
- 数据表：`stock_income_statement`

但页面和 API 目前并不会直接展示利润表详情。

## 2. 它能做什么

这个脚本会：

- 连接 MySQL
- 调用 Tushare 财务接口
- 创建或补充 `stock_income_statement`
- 批量写入利润表字段

因此它更接近“离线数据准备脚本”，而不是线上功能模块。

## 3. 如何运行

从项目根目录执行：

```bash
python app/utils/income_statement.py
```

运行前需要保证：

- `.env` 中数据库配置可用
- `TUSHARE_TOKEN` 已配置
- 当前 Python 环境已安装项目依赖

## 4. 与当前主项目的关系

当前关系是：

- 有模型
- 有脚本
- 无页面直连
- 无 API 直连
- 无统一调度入口接入 `scripts/sync_tushare_data.py`

因此维护时不要把它误认为“系统已上线的财务分析页面”。

## 5. 后续如果要升级

如果后续确实要把利润表纳入主功能，建议按下面顺序推进：

1. 把脚本迁移为 `scripts/` 下的正式命令。
2. 为同步过程加最小日志与错误处理约定。
3. 在 service 层提供只读查询接口。
4. 最后再决定是否接入页面展示。
