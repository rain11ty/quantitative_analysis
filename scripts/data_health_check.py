#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库完整性校验工具
====================
快速检查所有数据表的完整性、连续性、异常值。

用法:
  docker compose exec -T web python scripts/data_health_check.py
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


def get_conn():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'mysql'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'Qs2026Stock123'),
        database=os.getenv('DB_NAME', 'stock_cursor'),
        charset='utf8mb4',
    )


def print_section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)


def check_basic(c):
    """1. 股票基础信息"""
    print_section("1. 股票基础信息 (stock_basic)")

    c.execute("SELECT COUNT(*) FROM stock_basic")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM stock_basic WHERE ts_code LIKE '%.SH'")
    sh = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM stock_basic WHERE ts_code LIKE '%.SZ'")
    sz = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM stock_basic WHERE ts_code LIKE '%.BJ'")
    bj = c.fetchone()[0]

    print(f"  总股票数:     {total:>8}")
    print(f"  - 上海(.SH):  {sh:>8}")
    print(f"  - 深圳(.SZ):  {sz:>8}")
    print(f"  - 北京(.BJ):  {bj:>8}")

    # 检查关键字段完整性
    c.execute("SELECT COUNT(*) FROM stock_basic WHERE name IS NULL OR name=''")
    null_name = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM stock_basic WHERE industry IS NULL")
    null_ind = c.fetchone()[0]

    issues = []
    if null_name > 0:
        issues.append(f"名称为空: {null_name}只")
    if null_ind > 0:
        issues.append(f"行业为空: {null_ind}只")

    status = "PASS" if not issues else f"WARN ({'; '.join(issues)})"
    print(f"\n  状态: {status}")


def check_calendar(c):
    """2. 交易日历"""
    print_section("2. 交易日历 (stock_trade_calendar)")

    c.execute("SELECT MIN(cal_date), MAX(cal_date), SUM(is_open) FROM stock_trade_calendar")
    row = c.fetchone()
    min_d, max_d, open_days = row[0], row[1], row[2]
    c.execute("SELECT COUNT(*) FROM stock_trade_calendar")
    total = c.fetchone()[0]

    # 计算理论交易日数
    if min_d and max_d:
        span = (max_d - min_d).days + 1
        pct = open_days / span * 100 if span > 0 else 0
    else:
        span, pct = 0, 0

    print(f"  日期范围: {min_d} ~ {max_d} (共{span}天)")
    print(f"  总记录数:   {total:>8}")
    print(f"  其中交易日: {int(open_days) if isinstance(open_days, float) else open_days:>8} ({pct:.1f}%)")

    # 检查最近的交易日
    c.execute("""SELECT cal_date, is_open FROM stock_trade_calendar 
                ORDER BY cal_date DESC LIMIT 5""")
    recent = c.fetchall()
    print(f"\n  最近5个日历:")
    for d, is_open in recent:
        tag = "交易" if is_open else "休市"
        print(f"    {d}  [{tag}]")

    status = "PASS"
    if max_d:
        today = datetime.now().date()
        gap = (today - max_d).days
        if gap > 7:
            status = f"WARN (日历距今天已{gap}天)"
    print(f"\n  状态: {status}")


def check_daily_history(c):
    """3. 日线行情"""
    print_section("3. 日线行情 (stock_daily_history)")

    c.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_daily_history")
    total, min_d, max_d = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_daily_history")
    stocks = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT trade_date) FROM stock_daily_history")
    dates_count = c.fetchone()[0]

    print(f"  总记录数:       {total:>12,}")
    print(f"  覆盖股票数:     {stocks:>8,}")
    print(f"  覆盖交易日期数: {dates_count:>6,}")
    print(f"  日期范围:       {min_d} ~ {max_d}")

    # 每只股票平均天数
    avg_days = total / stocks if stocks > 0 else 0
    print(f"  平均每股票天数: {avg_days:.1f}")

    # 检查最近日期数据量
    c.execute("""SELECT trade_date, COUNT(*) as cnt 
                FROM stock_daily_history 
                GROUP BY trade_date ORDER BY trade_date DESC LIMIT 5""")
    recent = c.fetchall()
    print(f"\n  最近5个交易日数据量:")
    expected_range = None
    for d, cnt in recent:
        if expected_range is None:
            expected_range = (cnt * 0.9, cnt * 1.1)
        ok = expected_range[0] <= cnt <= expected_range[1] if expected_range else True
        mark = "" if ok else " ⚠偏低!"
        print(f"    {d}: {cnt:,} 条{mark}")

    # 检查空值
    c.execute("SELECT COUNT(*) FROM stock_daily_history WHERE close IS NULL OR vol IS NULL")
    null_vals = c.fetchone()[0]

    issues = []
    if null_vals > 0:
        issues.append(f"关键字段为空: {null_vals}条")
    if stocks < 5000:
        issues.append(f"股票覆盖不足: 仅{stocks}只")

    status = "PASS" if not issues else f"WARN ({'; '.join(issues)})"
    print(f"\n  状态: {status}")

    return stocks


def check_factor(c):
    """4. 复权因子+技术指标"""
    print_section("4. 复权因子 & 技术指标 (stock_factor)")

    c.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_factor")
    total, min_d, max_d = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_factor")
    stocks = c.fetchone()[0]

    # 各技术指标的填充率
    indicators = [
        ('adj_factor', '复权因子'),
        ('macd_dif', 'MACD_DIF'),
        ('macd_dea', 'MACD_DEA'),
        ('macd', 'MACD'),
        ('kdj_k', 'KDJ_K'),
        ('kdj_j', 'KDJ_J'),
        ('rsi_6', 'RSI6'),
        ('rsi_12', 'RSI12'),
        ('boll_upper', 'BOLL上轨'),
        ('boll_lower', 'BOLL下轨'),
        ('cci', 'CCI'),
    ]

    print(f"  总记录数:       {total:>12,}")
    print(f"  覆盖股票数:     {stocks:>8,}")
    print(f"  日期范围:       {min_d} ~ {max_d}")
    print(f"\n  技术指标填充率:")

    issues = []
    for col, label in indicators:
        c.execute(f"SELECT COUNT(*) FROM stock_factor WHERE {col} IS NOT NULL AND {col} != 0")
        filled = c.fetchone()[0]
        rate = filled / total * 100 if total > 0 else 0
        bar = "#" * int(rate / 3)
        mark = "" if rate >= 90 else (" ⚠" if rate >= 50 else " ✗严重不足!")
        print(f"    {label:<14s} {filled:>10,} ({rate:>5.1f}%) [{bar:<33}] {mark}")
        if rate < 80:
            issues.append(f"{label} 填充率仅 {rate:.1f}%")

    # 有完整指标的股票数
    c.execute("""
        SELECT COUNT(DISTINCT ts_code) FROM stock_factor 
        WHERE macd_dif IS NOT NULL 
          AND kdj_k IS NOT NULL 
          AND rsi_6 IS NOT NULL 
          AND boll_upper IS NOT NULL
          AND cci IS NOT NULL
    """)
    full_stocks = c.fetchone()[0]

    print(f"\n  有完整5大指标(MACD/KDJ/RSI/BOLL/CCI): {full_stocks}/{stocks} 只")
    if full_stocks < stocks * 0.9:
        issues.append(f"完整指标股票占比低: {full_stocks}/{stocks}")

    status = "PASS" if not issues else f"WARN ({'; '.join(issues)})"
    print(f"\n  状态: {status}")


def check_daily_basic(c):
    """5. 每日基本面指标"""
    print_section("5. 每日指标 (PE/PB/换手等) stock_daily_basic")

    c.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_daily_basic")
    total, min_d, max_d = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_daily_basic")
    stocks = c.fetchone()[0]

    fields = ['pe', 'pe_ttm', 'pb', 'turnover_rate', 'total_mv']
    
    print(f"  总记录数:       {total:>12,}")
    print(f"  覆盖股票数:     {stocks:>8,}")
    print(f"  日期范围:       {min_d} ~ {max_d}")
    print("\n  字段填充率:")
    for col in fields:
        c.execute(f"SELECT COUNT(*) FROM stock_daily_basic WHERE {col} IS NOT NULL AND {col} != 0")
        filled = c.fetchone()[0]
        rate = filled / total * 100 if total > 0 else 0
        print(f"    {col:<16s} {filled:>10,} ({rate:>5.1f}%)")

    status = "PASS" if total > 100000 else "WARN (数据量偏少)"
    print(f"\n  状态: {status}")


def check_moneyflow(c):
    """6. 资金流向"""
    print_section("6. 个股资金流向 (stock_moneyflow)")

    c.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM stock_moneyflow")
    total, min_d, max_d = c.fetchone()

    c.execute("""
        SELECT SUM(CASE WHEN net_mf_amount > 0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN net_mf_amount < 0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN net_mf_amount = 0 THEN 1 ELSE 0 END)
        FROM stock_moneyflow
    """)
    pos, neg, zero = c.fetchone()

    print(f"  总记录数:   {total:>12,}")
    print(f"  日期范围:   {min_d} ~ {max_d}")
    print(f"  净流入>0:   {pos:>10,} 天次")
    print(f"  净流入<0:   {neg:>10,} 天次")
    print(f"  净流入=0:   {zero:>10,} 天次")

    # 最近一天的资金流向概况
    c.execute("""
        SELECT trade_date,
               SUM(net_mf_amount) as total_net,
               AVG(net_mf_amount) as avg_net
        FROM stock_moneyflow 
        WHERE trade_date = (SELECT MAX(trade_date) FROM stock_moneyflow)
        GROUP BY trade_date
    """)
    row = c.fetchone()
    if row and row[0]:
        print(f"\n  最新日期({row[0]}): 净流入合计={row[1]:,.0f}万元, 均值={row[2]:,.0f}万元/股")

    status = "PASS" if total > 1000000 else "WARN (数据量偏少)"
    print(f"\n  状态: {status}")


def check_hsgt(c):
    """7. 北向资金"""
    print_section("7. 北向资金 (moneyflow_hsgt)")

    c.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM moneyflow_hsgt")
    total, min_d, max_d = c.fetchone()

    c.execute("""
        SELECT trade_date, north_money, south_money 
        FROM moneyflow_hsgt ORDER BY trade_date DESC LIMIT 5
    """)
    recent = c.fetchall()

    print(f"  总记录数:   {total:>6}")
    print(f"  日期范围:   {min_d} ~ {max_d}")
    print(f"\n  最近5天北向资金:")
    for d, north, south in recent:
        n_str = f"+{north:,.0f}" if north and north > 0 else f"{north:,.0f}"
        s_str = f"+{south:,.0f}" if south and south > 0 else f"{south:,.0f}"
        print(f"    {d}: 北向{n_str:>14}万  南向{s_str:>14}万")

    status = "PASS" if total > 200 else "WARN (数据量少)"
    print(f"\n  状态: {status}")


def check_data_continuity(c):
    """8. 数据连续性抽样检查"""
    print_section("8. 数据连续性抽样 (抽查代表性股票)")

    # 选几只典型股票
    test_stocks = [
        ('000001.SZ', '平安银行'), ('600519.SH', '贵州茅台'),
        ('000858.SZ', '五粮液'), ('601398.SH', '工商银行'),
        ('300750.SZ', '宁德时代'),
    ]

    for code, name in test_stocks:
        # 日线数据连续性
        c.execute("""
            SELECT trade_date FROM stock_daily_history 
            WHERE ts_code=%s ORDER BY trade_date ASC LIMIT 1
        """, (code,))
        first_row = c.fetchone()
        if not first_row:
            print(f"  {code} {name}: 无日线数据 ✗")
            continue

        c.execute("""
            SELECT trade_date FROM stock_daily_history 
            WHERE ts_code=%s ORDER BY trade_date DESC LIMIT 1
        """, (code,))
        last_row = c.fetchone()

        c.execute("SELECT COUNT(*) FROM stock_daily_history WHERE ts_code=%s", (code,))
        days = c.fetchone()[0]

        # 计算预期交易日数
        c.execute("""
            SELECT COUNT(*) FROM stock_trade_calendar 
            WHERE is_open=1 AND cal_date BETWEEN %s AND %s
        """, (first_row[0], last_row[0]))
        expected = c.fetchone()[0]

        coverage = days / expected * 100 if expected > 0 else 0
        mark = "✓" if coverage >= 95 else ("~" if coverage >= 80 else "✗")

        # 检查最新数据是否在近5天内
        latest_str = str(last_row[0])[:10] if last_row[0] else "N/A"

        print(f"  {mark} {code} {name:<8s} | {days:>4}天 | 预期{expected}天 | 覆盖{coverage:>5.1f}% | 最新{latest_str}")

        # 技术指标检查
        c.execute(f"""
            SELECT COUNT(*) FROM stock_factor 
            WHERE ts_code=%s AND macd_dif IS NOT NULL AND rsi_6 IS NOT NULL AND cci IS NOT NULL
        """, (code,))
        factor_ok = c.fetchone()[0]
        factor_mark = "✓" if factor_ok >= days * 0.9 else ("~" if factor_ok > 0 else "✗")
        print(f"      技术指标完整: {factor_mark} {factor_ok}/{days} 天")


def main():
    conn = get_conn()
    try:
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print("=" * 65)
        print(f"  A股量化分析系统 — 数据库健康检查")
        print(f"  检查时间: {now}")
        print("=" * 65)

        check_basic(c)
        check_calendar(c)
        check_daily_history(c)
        check_factor(c)
        check_daily_basic(c)
        check_moneyflow(c)
        check_hsgt(c)
        check_data_continuity(c)

        print("\n" + "=" * 65)
        print(f"  检查完成! 时间: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 65)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
