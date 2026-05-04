# AkShare 接口参考文档

> 本文档整理了与本项目相关的 AkShare 金融数据接口，供开发和维护参考。
> 官方文档: https://akshare.akfamily.xyz/
> 安装: `pip install akshare`
> 所有函数返回 `pandas.DataFrame`，列名默认为中文（东财源）或英文（新浪源）。

---

## 目录

1. [项目当前使用的接口](#1-项目当前使用的接口)
2. [A股行情数据](#2-a股行情数据)
3. [A股基本信息](#3-a股基本信息)
4. [财务数据](#4-财务数据)
5. [资金流向](#5-资金流向)
6. [板块/行业](#6-板块行业)
7. [新闻资讯](#7-新闻资讯)
8. [指数数据](#8-指数数据)
9. [筹码分布](#9-筹码分布)
10. [涨跌停/异动](#10-涨跌停异动)
11. [北向资金](#11-北向资金)
12. [融资融券](#12-融资融券)

---

## 1. 项目当前使用的接口

| # | 函数 | 数据源 | 文件 | 用途 |
|---|------|--------|------|------|
| 1 | `ak.stock_zh_a_spot()` | 新浪 | akshare_service.py, realtime_monitor_service.py | A股全市场实时行情快照 |
| 2 | `ak.stock_zh_index_daily(symbol)` | 新浪 | akshare_service.py | 指数历史日K线 |
| 3 | `ak.index_zh_a_hist(symbol, period, start_date, end_date, adjust)` | 东财 | akshare_service.py | 指数历史K线(日/周/月) |
| 4 | `ak.stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` | 东财 | akshare_service.py | 个股历史K线 |
| 5 | `ak.stock_individual_info_em(symbol)` | 东财 | akshare_service.py | 个股基本信息 |
| 6 | `ak.stock_zh_a_minute(symbol, period, adjust)` | 新浪 | akshare_service.py | 分钟级K线(1/5/15/30/60) |
| 7 | `ak.stock_info_cjzc_em()` | 东财 | news_service.py | 财经早餐 |
| 8 | `ak.stock_info_global_em()` | 东财 | news_service.py | 全球财经快讯 |
| 9 | `ak.stock_info_global_cls(symbol)` | 财联社 | news_service.py | 财联社电报 |
| 10 | `ak.stock_info_global_ths()` | 同花顺 | news_service.py | 同花顺全球财经直播 |

---

## 2. A股行情数据

### `ak.stock_zh_a_hist(symbol, period, start_date, end_date, adjust)`

获取A股历史行情数据（东方财富）。

**参数:**
- `symbol` (str): 股票代码，纯数字，如 `"600519"`
- `period` (str): 周期 `"daily"` / `"weekly"` / `"monthly"`，默认 `"daily"`
- `start_date` (str): 开始日期 `"YYYYMMDD"`，默认 `""`
- `end_date` (str): 结束日期 `"YYYYMMDD"`，默认 `""`
- `adjust` (str): 复权方式 `""` 不复权 / `"qfq"` 前复权 / `"hfq"` 后复权，默认 `""`

**返回列:** `日期`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`

**示例:**
```python
import akshare as ak
df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20240101", end_date="20240401", adjust="qfq")
```

---

### `ak.stock_zh_a_spot_em()`

获取A股全市场实时行情快照（东方财富）。

**参数:** 无

**返回列:** `序号`, `代码`, `名称`, `最新价`, `涨跌幅`, `涨跌额`, `成交量`, `成交额`, `振幅`, `最高`, `最低`, `今开`, `昨收`, `量比`, `换手率`, `市盈率-动态`, `市净率`, `总市值`, `流通市值`, `涨速`, `5分钟涨跌`, `60日涨跌幅`, `年初至今涨跌幅`

---

### `ak.stock_zh_a_spot()`

获取A股全市场实时行情（新浪），旧版接口。

**参数:** 无

**返回列:** `代码`, `名称`, `最新价`, `涨跌额`, `涨跌幅`, `买入`, `卖出`, `昨收`, `今开`, `最高`, `最低`, `成交量`, `成交额`, `时间戳`

---

### `ak.stock_zh_a_hist_min_em(symbol, period, start_date, end_date, adjust)`

获取A股分钟级K线数据（东方财富），比新浪源更稳定。

**参数:**
- `symbol` (str): 股票代码，如 `"600519"`
- `period` (str): 分钟周期 `"1"` / `"5"` / `"15"` / `"30"` / `"60"`
- `start_date` (str): 开始日期时间 `"YYYY-MM-DD HH:MM:SS"`
- `end_date` (str): 结束日期时间 `"YYYY-MM-DD HH:MM:SS"`
- `adjust` (str): 复权方式 `""` / `"qfq"` / `"hfq"`

**返回列:** `时间`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`

---

### `ak.stock_zh_a_minute(symbol, period, adjust)`

获取A股/指数分钟K线数据（新浪）。

**参数:**
- `symbol` (str): 新浪格式代码，如 `"sh600519"` / `"sz000001"` / `"sh000001"` (指数)
- `period` (str): `"1"` / `"5"` / `"15"` / `"30"` / `"60"`
- `adjust` (str): `""` / `"qfq"` / `"hfq"`

**返回列:** `day`, `open`, `high`, `low`, `close`, `volume`, `amount`

---

### `ak.stock_intraday_em(symbol)`

获取个股日内分时成交明细（东方财富）。

**参数:**
- `symbol` (str): 股票代码，如 `"600519"`

**返回列:** `时间`, `成交价`, `手数`, `买卖方向` (买/卖/中)

---

## 3. A股基本信息

### `ak.stock_info_a_code_name()`

获取所有A股代码和名称列表。

**参数:** 无

**返回列:** `code`, `name`

---

### `ak.stock_individual_info_em(symbol)`

获取个股基本信息（东方财富）。

**参数:**
- `symbol` (str): 股票代码，如 `"600519"`

**返回列:** `item`, `value` (key-value格式，含总市值、流通市值、行业、上市日期等)

---

### `ak.stock_zh_a_new()`

获取次新股（上市不足一年）行情数据。

**参数:** 无

**返回列:** `序号`, `代码`, `名称`, `最新价`, `涨跌幅`, `涨跌额`, `成交量`, `成交额`, `振幅`, `最高`, `最低`, `今开`, `昨收`, `换手率`, `市盈率-动态`, `市净率`

---

### `ak.stock_info_sh_name_code()`

获取上海证券交易所股票代码和名称。

**参数:** 无

**返回列:** `COMPANY_CODE`, `COMPANY_ABBR`, `COMPANY_ENG_ABBR`

---

### `ak.stock_info_sz_name_code()`

获取深圳证券交易所股票代码和名称。

**参数:** 无

---

## 4. 财务数据

### `ak.stock_financial_analysis_indicator(symbol)`

获取个股财务分析指标（偿债/盈利/成长/营运能力）。

**参数:**
- `symbol` (str): 股票代码

**返回列:** `日期`, `摊薄每股收益`, `加权每股收益`, `每股收益_调整后`, `每股净资产_调整前`, `每股净资产_调整后`, `每股经营性现金流`, `加权净资产收益率`, `摊薄净资产收益率`, `摊薄总资产收益率`, `净利润率`, `总资产利润率`, `资产负债比率`, `流动比率`, `速动比率`, `现金比率` 等

---

### `ak.stock_balance_sheet_by_report_em(symbol)`

获取个股资产负债表（按报告期）。

**参数:**
- `symbol` (str): 股票代码

**返回列:** `REPORT_DATE`, `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, `MONETARYFUNDS`, `ACCOUNTS_RECE`, `INVENTORY`, `FIXED_ASSETS`, `INTANGIBLE_ASSETS`, `SHORT_LOAN`, `LONG_LOAN` 等

---

### `ak.stock_profit_sheet_by_report_em(symbol)`

获取个股利润表（按报告期）。

**参数:**
- `symbol` (str): 股票代码

**返回列:** `REPORT_DATE`, `TOTAL_OPERATE_INCOME`, `OPERATE_INCOME`, `OPERATE_COST`, `OPERATE_PROFIT`, `TOTAL_PROFIT`, `NETPROFIT`, `PARENT_NETPROFIT`, `BASIC_EPS` 等

---

### `ak.stock_cash_flow_sheet_by_report_em(symbol)`

获取个股现金流量表（按报告期）。

**参数:**
- `symbol` (str): 股票代码

**返回列:** `REPORT_DATE`, `SALES_SERVICES`, `TOTAL_OPERATE_INFLOW`, `TOTAL_OPERATE_OUTFLOW`, `NETCASH_OPERATE`, `TOTAL_INVEST_INFLOW`, `TOTAL_INVEST_OUTFLOW`, `NETCASH_INVEST`, `TOTAL_FINANCE_INFLOW`, `TOTAL_FINANCE_OUTFLOW`, `NETCASH_FINANCE` 等

---

## 5. 资金流向

### `ak.stock_individual_fund_flow(stock, market)`

获取个股资金流向数据（东方财富）。

**参数:**
- `stock` (str): 股票代码，如 `"600519"`
- `market` (str): 市场 `"sh"` / `"sz"`

**返回列:** `日期`, `收盘价`, `涨跌幅`, `主力净流入-净额`, `主力净流入-净占比`, `超大单净流入-净额`, `超大单净流入-净占比`, `大单净流入-净额`, `大单净流入-净占比`, `中单净流入-净额`, `中单净流入-净占比`, `小单净流入-净额`, `小单净流入-净占比`

---

### `ak.stock_individual_fund_flow_rank(indicator)`

获取个股资金流向排名。

**参数:**
- `indicator` (str): `"今日"` / `"3日"` / `"5日"` / `"10日"`

**返回列:** `序号`, `代码`, `名称`, `最新价`, `今日涨跌幅`, `今日主力净流入-净额`, `今日主力净流入-净占比` 等

---

### `ak.stock_market_fund_flow()`

获取大盘资金流向（沪深两市）。

**参数:** 无

**返回列:** `日期`, `上证-收盘价`, `上证-涨跌幅`, `深证-收盘价`, `深证-涨跌幅`, `主力净流入-净额`, `主力净流入-净占比`, `小单净流入-净额`, `中单净流入-净额`, `大单净流入-净额`, `超大单净流入-净额`

---

### `ak.stock_fund_flow_industry(symbol)`

获取行业资金流向。

**参数:**
- `symbol` (str): `"即时"` / `"3日"` / `"5日"` / `"10日"` / `"20日"`

**返回列:** `序号`, `名称`, `今日涨跌幅`, `今日主力净流入-净额`, `今日主力净流入-净占比` 等

---

## 6. 板块/行业

### `ak.stock_board_industry_name_em()`

获取东方财富行业板块名称列表。

**参数:** 无

**返回列:** `板块名称`, `板块代码`, `最新价`, `涨跌额`, `涨跌幅`, `总市值`, `换手率`, `上涨家数`, `下跌家数`, `领涨股票`, `领涨涨跌幅`

---

### `ak.stock_board_concept_name_em()`

获取东方财富概念板块名称列表。

**参数:** 无

**返回列:** 同上

---

### `ak.stock_board_industry_cons_em(symbol)`

获取指定行业板块的成分股。

**参数:**
- `symbol` (str): 行业板块名称，如 `"小金属"`

**返回列:** `序号`, `代码`, `名称`, `最新价`, `涨跌幅`, `涨跌额`, `成交量`, `成交额`, `振幅`, `最高`, `最低`, `今开`, `昨收`, `换手率`

---

### `ak.stock_board_concept_cons_em(symbol)`

获取指定概念板块的成分股。

**参数:**
- `symbol` (str): 概念板块名称，如 `"华为概念"`

---

### `ak.stock_board_industry_hist_em(symbol, period, start_date, end_date, adjust)`

获取行业板块历史行情K线。

**参数:**
- `symbol` (str): 行业板块名称
- `period` (str): `"daily"` / `"weekly"` / `"monthly"`
- `start_date` / `end_date` (str): `"YYYYMMDD"`
- `adjust` (str): `""` / `"qfq"` / `"hfq"`

**返回列:** `日期`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`

---

### `ak.stock_board_concept_hist_em(symbol, period, start_date, end_date, adjust)`

获取概念板块历史行情K线。参数同上。

---

## 7. 新闻资讯

### `ak.stock_info_global_em()`

获取东方财富全球财经快讯。

**参数:** 无

**返回列:** `标题`, `摘要`, `发布时间`, `链接`, `内容`

---

### `ak.stock_info_cjzc_em()`

获取东方财富财经早餐。

**参数:** 无

**返回列:** `标题`, `摘要`, `发布时间`, `链接`

---

### `ak.stock_info_global_cls(symbol)`

获取财联社电报。

**参数:**
- `symbol` (str): 分类 `"全部"` / `"A股"` / `"港股"` / `"美股"` / `"基金"` / `"期货"`

**返回列:** `标题`, `内容`, `发布日期`, `发布时间`

---

### `ak.stock_info_global_ths()`

获取同花顺全球财经直播。

**参数:** 无

**返回列:** `标题`, `内容`, `发布时间`, `链接`

---

### `ak.stock_info_global_sina()`

获取新浪财经全球财经快讯。

**参数:** 无

**返回列:** `标题`, `内容`, `发布时间`

---

## 8. 指数数据

### `ak.stock_zh_index_daily(symbol)`

获取指数历史日K线数据（新浪）。

**参数:**
- `symbol` (str): 新浪格式，如 `"sh000001"` (上证指数), `"sz399001"` (深证成指), `"sh000300"` (沪深300)

**返回列:** `date`, `open`, `high`, `low`, `close`, `volume`

---

### `ak.index_zh_a_hist(symbol, period, start_date, end_date, adjust)`

获取指数历史行情（东方财富），支持周/月K线。

**参数:**
- `symbol` (str): 纯数字代码，如 `"000001"` / `"399001"` / `"000300"`
- `period` (str): `"daily"` / `"weekly"` / `"monthly"`
- `start_date` / `end_date` (str): `"YYYYMMDD"`
- `adjust` (str): `""` / `"qfq"` / `"hfq"`

**返回列:** `日期`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`

---

### `ak.stock_zh_index_spot_em()`

获取主要指数实时行情（东方财富）。

**参数:** 无

**返回列:** `序号`, `代码`, `名称`, `最新价`, `涨跌幅`, `涨跌额`, `成交量`, `成交额`, `振幅`, `最高`, `最低`, `今开`, `昨收`, `量比`

---

### `ak.index_zh_a_hist_min_em(symbol, period)`

获取指数分钟级K线数据（东方财富）。

**参数:**
- `symbol` (str): 指数代码，如 `"000001"`
- `period` (str): `"1"` / `"5"` / `"15"` / `"30"` / `"60"`

**返回列:** `时间`, `开盘`, `收盘`, `最高`, `最低`, `成交量`, `成交额`, `振幅`, `涨跌幅`, `涨跌额`, `换手率`

---

## 9. 筹码分布

### `ak.stock_cyq_em(symbol, adjust)`

获取个股筹码分布数据（东方财富）。

**参数:**
- `symbol` (str): 股票代码
- `adjust` (str): `"qfq"` / `"hfq"`

**返回列:** `日期`, `获利比例`, `平均成本`, `90%成本-低`, `90%成本-高`, `90%成本集中度`, `70%成本-低`, `70%成本-高`, `70%成本集中度`, `筹码峰值-价格`, `筹码峰值-占比`

---

### `ak.stock_cyq_perf(symbol)`

获取个股筹码分布绩效指标。

**参数:**
- `symbol` (str): 股票代码

**返回列:** `日期`, `股票代码`, `获利比例`, `平均成本`, `90%成本-低`, `90%成本-高`, `集中度`, `70%成本-低`, `70%成本-高`, `集中度`, `筹码峰值`

---

## 10. 涨跌停/异动

### `ak.stock_zt_pool_em(date)`

获取涨停板池（东方财富）。

**参数:**
- `date` (str): 日期 `"YYYYMMDD"`，默认当日

**返回列:** `序号`, `代码`, `名称`, `涨跌幅`, `最新价`, `成交额`, `流通市值`, `总市值`, `换手率`, `封板资金`, `首次封板时间`, `最后封板时间`, `炸板次数`, `涨停统计`, `连板数`, `所属行业`

---

### `ak.stock_dt_pool_em(date)`

获取跌停板池（东方财富）。

**参数:**
- `date` (str): 日期 `"YYYYMMDD"`，默认当日

**返回列:** `序号`, `代码`, `名称`, `涨跌幅`, `最新价`, `成交额`, `流通市值`, `总市值`, `换手率`, `封板资金`, `最后封板时间`, `连续跌停天数`, `所属行业`

---

### `ak.stock_changes_em(symbol)`

获取盘口异动数据（东方财富）。

**参数:**
- `symbol` (str): 异动类型，如 `"火箭发射"` / `"快速反弹"` / `"大笔买入"` / `"封涨停板"` / `"打开跌停板"` / `"有大买盘"` / `"竞价上涨"` / `"高开5日线"` / `"向上缺口"` / `"60日新高"` / `"60日大幅上涨"` / `"加速下跌"` / `"高台跳水"` / `"大笔卖出"` / `"封跌停板"` / `"打开涨停板"` / `"有大卖盘"` / `"竞价下跌"` / `"低开5日线"` / `"向下缺口"` / `"60日新低"` / `"60日大幅下跌"`

---

## 11. 北向资金

### `ak.stock_hsgt_north_net_flow_in_em(symbol)`

获取北向资金净流入数据（东方财富）。

**参数:**
- `symbol` (str): `"北向"` / `"沪股通"` / `"深股通"`

**返回列:** `日期`, `当日净流入`, `当日余额`, `历史累计净流入`, `当日成交净买额` 等

---

### `ak.stock_hsgt_north_acc_flow_in_em(symbol)`

获取北向资金累计净流入。参数同上。

---

### `ak.stock_hsgt_north_flow_em(symbol)`

获取北向资金历史流向明细。

**参数:**
- `symbol` (str): `"北向"` / `"沪股通"` / `"深股通"`

**返回列:** `日期`, `当日净流入`, `当日余额` 等

---

### `ak.stock_hsgt_board_rank_em(symbol)`

获取北向资金板块排名。

**参数:**
- `symbol` (str): `"北向资金增持行业板块排行-今日"` / `"北向资金增持个股排行-今日"` 等

**返回列:** `序号`, `名称`, `代码`, `涨跌幅`, `北向资金净买入`, `北向资金净买入占比` 等

---

## 12. 融资融券

### `ak.stock_margin_detail_szse(date)`

获取深市融资融券明细数据。

**参数:**
- `date` (str): 日期 `"YYYYMMDD"`

**返回列:** `证券代码`, `证券简称`, `融资买入额`, `融资余额`, `融券卖出量`, `融券余量`, `融券余额`, `融资融券余额`

---

### `ak.stock_margin_detail_sse(date)`

获取沪市融资融券明细数据。

**参数:**
- `date` (str): 日期 `"YYYYMMDD"`

**返回列:** `标的证券代码`, `标的证券简称`, `融资买入额`, `融资余额`, `融券卖出量`, `融券余量`, `融券余额`, `融资融券余额`

---

### `ak.stock_margin_sse(date)`

获取沪市融资融券每日汇总。

**参数:**
- `date` (str): 日期

**返回列:** `信用交易日期`, `融资余额`, `融券余额`, `融资融券余额`, `融资买入额`, `融券卖出量`

---

## 注意事项

1. **AkShare 更新频繁**（通常每周更新），函数签名和返回列可能变化，使用前建议通过 `help(ak.function_name)` 或官方文档确认。
2. **列名语言**: 东财源函数返回中文列名，新浪源函数返回英文列名。
3. **代理问题**: 部分网络环境下需要设置代理，项目中 `akshare_service.py` 的 `call_with_no_proxy()` 已处理代理冲突。
4. **频率限制**: 东财接口有反爬机制，建议在调用间加入 `time.sleep(0.5)` 避免被封。
5. **官方文档**: https://akshare.akfamily.xyz/data/stock/stock.html
