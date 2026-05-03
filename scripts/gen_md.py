# -*- coding: utf-8 -*-
import json

r = json.loads(open("db_schema_dump.json", encoding="utf-8").read())
md = ["# 数据库结构与应用情况\n\n本文档列出了当前系统中已使用的所有数据表结构。**代码中定义但在系统业务逻辑中未使用的表，已在文末专门列出并进行说明。**\n"]

table_desc = {
    "user_account": "存储系统所有用户的账户信息（用户名、密码Hash、权限角色等）。",
    "user_watchlist": "存储用户添加的自选股名单，用于个人面板展示。",
    "user_analysis_records": "存储用户进行股票个股分析后的历史记录与心得总结。",
    "user_chat_history": "存储用户与 AI 智能助手的对话记录。",
    "stock_basic": "存储股票市场全量标的基础信息（代码、名称、上市日期、所属行业）。",
    "stock_daily_basic": "存储股票每日衍生基本面数据（如换手率、PE、PB、总市值）。",
    "stock_daily_history": "存储股票历史日级别K线数据（开高低收价格与成交量）。",
    "stock_minute_data": "存储盘中实时或历史分钟级的高频K线数据（支持1min/5min/15min等）。",
    "stock_business": "存储上市公司的主营业务构成、具体业务收入与利润比例。",
    "business_dictionary": "股票业务字典表，对业务类型分类进行标准化维护。",
    "stock_cyq_perf": "筹码分布特征表，存储筹码集中度、获利比例等衍生指标计算结果。",
    "stock_moneyflow": "股票资金流向表，存储各类单子（大中小）的流入流出情况。",
    "stock_balance_sheet": "公司资产负债表，存储季度财报相关的资产、负债明细。",
    "stock_income_statement": "公司利润表，记录营业收入、净利润等营收核心数据。",
    "stock_cash_flow": "公司现金流量表，记录企业经营活动与现金储备状态。",
    "system_log": "系统行为审计日志，记录敏感操作（登录、配置变更等）。",
    "factor_definition": "量化模型：用于定义与存储各类多因子策略的基础因子定义及其计算公式。",
    "factor_values": "量化模型：存储个股基于 factor_definition 每日产生的具体因子数值。",
    "ml_model_definition": "机器学习：保存训练完成的模型定义参数、使用的特征组合及其它超参数配置。",
    "ml_predictions": "机器学习：存储机器学习模型对具体个股在特定交易日的评分与上涨概率预测。",
    "portfolio_positions": "策略回测：保存量化回测引擎进行模拟调仓交易后的每日持仓分布。",
    "realtime_indicators": "实时监控：存储盘中实时滚动计算的技术指标快照（如MACD、RSI）。",
    "risk_alerts": "风控预警：记录盘中监控策略生成的风险提示或异常波动警告信息。",
    "trading_signals": "交易信号：基于策略实时或日频生成的量化交易操作建议（买入/卖出）。"
}

for t in r["used"]:
    md.append(f"## 表名：`{t['table_name']}` ({t['class_name']})")
    desc = table_desc.get(t['table_name'], t['doc'].strip() or "本表用于存储与 " + t['class_name'] + " 相关的数据。")
    md.append(f"**表作用说明**：{desc}\n")
    md.append("| 字段名 | 字段类型 | 主键 | 描述/注释 |")
    md.append("|---|---|---|---|")
    for c in t["columns"]:
        md.append(f"| {c['name']} | {c['type']} | {c['pk']} | {c['comment']} |")
    md.append("\n")

md.append("## ?? 尚未应用在系统中的表\n\n以下模型表虽然在代码中进行了 ORM 声明，但在系统目前的后台业务逻辑或前端交互中**没有任何实质性调用与数据写入**，属于当前版本废弃或未启用的模型：\n")
for t in r["unused"]:
    md.append(f"- **表名**：`{t['table_name']}` (对应代码类：{t['class_name']})")

with open("数据库表结构.md", "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print("ok")
