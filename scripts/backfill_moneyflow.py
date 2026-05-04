#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量回填个股资金流向数据（Tushare moneyflow 接口）
==================================================
将 stock_moneyflow 表中缺失的历史数据补全到 2021 年。

用法:
  # 回填 2021-01-01 至今（默认）
  python scripts/backfill_moneyflow.py

  # 指定日期范围
  python scripts/backfill_moneyflow.py --start-date 20220101 --end-date 20231231

  # 仅处理前 50 只测试
  python scripts/backfill_moneyflow.py --limit 50

  # 仅统计不写入
  python scripts/backfill_moneyflow.py --dry-run
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import pymysql
import tushare as ts
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True, encoding='utf-8')


# ============================================================
#  数据库连接
# ============================================================
def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'root'),
        database=os.getenv('DB_NAME', 'stock_cursor'),
        charset=os.getenv('DB_CHARSET', 'utf8mb4'),
    )


def init_tushare():
    token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
    if not token:
        raise ValueError('TUSHARE_TOKEN 未设置')
    ts.set_token(token)
    pro = ts.pro_api()
    proxy_url = (os.getenv('TUSHARE_PROXY_URL', '') or '').strip()
    if proxy_url:
        pro._DataApi__http_url = proxy_url
    return pro


# ============================================================
#  获取交易日历
# ============================================================
def get_trade_dates(conn, start_date, end_date):
    sql = (
        "SELECT DATE_FORMAT(cal_date, '%%Y%%m%%d') "
        "FROM stock_trade_calendar "
        "WHERE is_open = 1 AND cal_date >= %s AND cal_date <= %s "
        "ORDER BY cal_date"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        return [row[0] for row in cur.fetchall()]


# ============================================================
#  查询已有 moneyflow 数据日期
# ============================================================
def get_existing_moneyflow_dates(conn):
    sql = "SELECT DISTINCT DATE_FORMAT(trade_date, '%%Y%%m%%d') FROM stock_moneyflow"
    with conn.cursor() as cur:
        cur.execute(sql)
        return set(row[0] for row in cur.fetchall())


# ============================================================
#  批量写入
# ============================================================
MONEYFLOW_COLUMNS = [
    'ts_code', 'trade_date',
    'buy_sm_vol', 'buy_sm_amount', 'sell_sm_vol', 'sell_sm_amount',
    'buy_md_vol', 'buy_md_amount', 'sell_md_vol', 'sell_md_amount',
    'buy_lg_vol', 'buy_lg_amount', 'sell_lg_vol', 'sell_lg_amount',
    'buy_elg_vol', 'buy_elg_amount', 'sell_elg_vol', 'sell_elg_amount',
    'net_mf_vol', 'net_mf_amount',
]

UPDATE_COLS = [c for c in MONEYFLOW_COLUMNS if c not in ('ts_code', 'trade_date')]

INSERT_SQL = f"""
    INSERT INTO stock_moneyflow ({', '.join(f'`{c}`' for c in MONEYFLOW_COLUMNS)})
    VALUES ({', '.join(['%s'] * len(MONEYFLOW_COLUMNS))})
    ON DUPLICATE KEY UPDATE {', '.join(f'`{c}`=VALUES(`{c}`)' for c in UPDATE_COLS)}
"""


def batch_upsert(conn, records, batch_size=5000):
    if not records:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            cur.executemany(INSERT_SQL, batch)
            inserted += len(batch)
    conn.commit()
    return inserted


# ============================================================
#  获取单日资金流向
# ============================================================
def fetch_moneyflow_for_date(pro, trade_date, max_retries=5):
    """获取指定日期的个股资金流向数据"""
    for attempt in range(max_retries):
        try:
            time.sleep(0.35)  # Tushare rate limit
            df = pro.moneyflow(trade_date=trade_date)
            if df is None or df.empty:
                return []
            df = df.replace({np.nan: None}).where(pd.notnull(df), None)
            records = []
            for _, r in df.iterrows():
                td = datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None
                records.append((
                    r.get('ts_code'), td,
                    r.get('buy_sm_vol'), r.get('buy_sm_amount'),
                    r.get('sell_sm_vol'), r.get('sell_sm_amount'),
                    r.get('buy_md_vol'), r.get('buy_md_amount'),
                    r.get('sell_md_vol'), r.get('sell_md_amount'),
                    r.get('buy_lg_vol'), r.get('buy_lg_amount'),
                    r.get('sell_lg_vol'), r.get('sell_lg_amount'),
                    r.get('buy_elg_vol'), r.get('buy_elg_amount'),
                    r.get('sell_elg_vol'), r.get('sell_elg_amount'),
                    r.get('net_mf_vol'), r.get('net_mf_amount'),
                ))
            return records
        except Exception as e:
            err_str = str(e).lower()
            is_network_err = any(kw in err_str for kw in [
                'connection refused', 'connection reset', 'max retries',
                'newconnectionerror', 'socket hang up', 'timeout',
            ])
            if not is_network_err:
                raise
            wait = min(2 ** attempt, 30)
            logger.warning(f'网络错误(第{attempt+1}次): {type(e).__name__}，{wait}s后重试...')
            time.sleep(wait)
    raise Exception(f'重试{max_retries}次后仍然失败')


# ============================================================
#  主函数
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='批量回填个股资金流向数据')
    parser.add_argument('--start-date', type=str, default=None,
                        help='起始日期 YYYYMMDD（默认20210101）')
    parser.add_argument('--end-date', type=str, default=None,
                        help='结束日期 YYYYMMDD（默认今天）')
    parser.add_argument('--limit', type=int, default=None,
                        help='只处理前N个交易日（调试用）')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='每批写入条数（默认5000）')
    parser.add_argument('--dry-run', action='store_true',
                        help='只统计不写入')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='跳过已有数据的日期（默认开启）')
    args = parser.parse_args()

    if not args.start_date:
        args.start_date = '20210101'
    if not args.end_date:
        args.end_date = datetime.now().strftime('%Y%m%d')

    print("=" * 60)
    print("  个股资金流向批量回填工具")
    print(f"  日期范围: {args.start_date} ~ {args.end_date}")
    print(f"  模式: {'[DRY RUN]' if args.dry_run else '[正式写入]'}")
    print("=" * 60)

    conn = get_db_connection()
    pro = init_tushare()

    try:
        start_time = time.time()

        # 获取交易日列表
        trade_dates = get_trade_dates(conn, args.start_date, args.end_date)
        if not trade_dates:
            print("没有交易日需要处理")
            return

        # 过滤已有数据的日期
        if args.skip_existing:
            existing_dates = get_existing_moneyflow_dates(conn)
            before_count = len(trade_dates)
            trade_dates = [d for d in trade_dates if d not in existing_dates]
            print(f"  跳过已有数据: {before_count - len(trade_dates)} 个交易日")
            print(f"  待处理: {len(trade_dates)} 个交易日")

        if args.limit:
            trade_dates = trade_dates[:args.limit]

        total_dates = len(trade_dates)
        print(f"\n共 {total_dates} 个交易日待处理\n")

        stats = {
            'success': 0,
            'inserted': 0,
            'empty': 0,
            'error': 0,
            'errors_detail': [],
        }

        for idx, trade_date in enumerate(trade_dates, 1):
            try:
                records = fetch_moneyflow_for_date(pro, trade_date)

                if not records:
                    stats['empty'] += 1
                    if idx % 100 == 0:
                        print(f"  [{idx}/{total_dates}] {trade_date}: 无数据 | "
                              f"+{stats['inserted']}条 空{stats['empty']} 错误{stats['error']}")
                    continue

                if not args.dry_run:
                    inserted = batch_upsert(conn, records, args.batch_size)
                else:
                    inserted = len(records)

                stats['success'] += 1
                stats['inserted'] += inserted

                if idx % 10 == 0 or idx == total_dates:
                    elapsed = time.time() - start_time
                    avg = elapsed / idx
                    eta = avg * (total_dates - idx)
                    print(f"  [{idx}/{total_dates}] {trade_date}: +{len(records)}条 | "
                          f"累计{stats['inserted']}条 | 耗时{elapsed:.0f}s | ETA {eta:.0f}s")

            except Exception as e:
                stats['error'] += 1
                stats['errors_detail'].append(f"  {trade_date}: {str(e)[:200]}")
                logger.error(f"  {trade_date} 错误: {e}")

        elapsed = time.time() - start_time

        # 最终报告
        print(f"\n{'=' * 60}")
        print("  回填完成报告")
        print(f"{'=' * 60}")
        print(f"  日期范围:     {args.start_date} ~ {args.end_date}")
        print(f"  待处理天数:   {total_dates}")
        print(f"  成功处理:     {stats['success']}")
        print(f"  无数据跳过:   {stats['empty']}")
        print(f"  失败跳过:     {stats['error']}")
        print(f"  新增记录:     {stats['inserted']} 条")
        print(f"  耗时:         {elapsed:.1f}s")

        if stats['errors_detail']:
            print(f"\n  失败详情 ({min(len(stats['errors_detail']), 20)} 条):")
            for e in stats['errors_detail'][:20]:
                print(e)
        print()

    finally:
        conn.close()


if __name__ == '__main__':
    main()
