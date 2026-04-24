# Diagnostics Scripts

这些脚本用于手工排查，不属于自动化测试。

## Available scripts

- `market_overview_smoke.py`: 快速查看市场概览接口返回
- `market_overview_item_errors.py`: 检查市场概览明细中的错误项
- `tushare_connection_check.py`: 检查 Tushare 配置和分钟数据抓取路径

## Run examples

```bash
python scripts/diagnostics/market_overview_smoke.py
python scripts/diagnostics/market_overview_item_errors.py
python scripts/diagnostics/tushare_connection_check.py
```

如果后续要接入正式测试框架，建议把稳定的断言迁移到 `pytest` 测试用例中。
