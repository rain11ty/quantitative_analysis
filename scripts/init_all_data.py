#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键数据初始化脚本
==================
新部署时的数据初始化，依次执行：
  1. 交易日历       (stock_trade_calendar)  — 全量
  2. 股票基础信息   (stock_basic)           — 全量
  3. 日线行情       (stock_daily_history)   — 近 N 年
  4. 复权因子       (stock_factor)          — 近 N 年
  5. 每日指标       (stock_daily_basic)     — 近 N 年
  6. 资金流向       (stock_moneyflow)       — 近 N 年
  7. 北向资金       (moneyflow_hsgt)        — 近 N 年
  8. 技术指标补算   — 全量

用法:
  python scripts/init_all_data.py                  # 全量初始化（近3年，约2-4小时）
  python scripts/init_all_data.py --years 1        # 仅近1年数据
  python scripts/init_all_data.py --skip calendar,basic  # 跳过已完成的步骤
  python scripts/init_all_data.py --dry-run        # 仅检测各表现在数据量，不写入

可跳过的步骤名: calendar, basic, daily, adj, daily_basic, moneyflow, hsgt, factors
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True, encoding='utf-8')

from scripts.sync_tushare_data import TushareDataSync
from loguru import logger

logger.add(
    'logs/init_data_{time:YYYYMMDD}.log',
    rotation='100 MB', retention='30 days', level='INFO',
)


def print_header():
    print()
    print('=' * 70)
    print('  A股量化分析系统 — 一键数据初始化')
    print(f'  开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    print()


def print_step(step: int, total: int, name: str):
    print(f'\n  [{step}/{total}] {name} ...')


def print_result(name: str, rows: int, elapsed: float, skipped: bool = False):
    tag = '跳过(已有数据)' if skipped else f'完成 +{rows} 条'
    print(f'    {tag}  耗时 {elapsed:.0f}s')


def detect_existing(sync: TushareDataSync, table: str, min_rows: int = 100):
    """检测表中已有数据量，超过阈值则认为已完成。"""
    try:
        sync.cursor.execute(f'SELECT COUNT(*) FROM `{table}`')
        count = sync.cursor.fetchone()[0]
        return count >= min_rows
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='一键数据初始化')
    parser.add_argument('--years', type=int, default=3, help='同步近N年数据 (默认3)')
    parser.add_argument(
        '--skip', type=str, default='',
        help='跳过指定步骤，逗号分隔 (calendar, basic, daily, adj, daily_basic, moneyflow, hsgt, factors)',
    )
    parser.add_argument('--dry-run', action='store_true', help='仅检测不写入')
    args = parser.parse_args()

    skip_set = {s.strip() for s in args.skip.split(',') if s.strip()}

    start_date = (datetime.now() - timedelta(days=args.years * 365)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')

    print_header()

    # Dry-run mode
    if args.dry_run:
        print('  *** DRY-RUN 模式：仅显示各表当前数据量 ***\n')
        sync = TushareDataSync()
        try:
            tables = [
                'stock_trade_calendar', 'stock_basic', 'stock_daily_history',
                'stock_factor', 'stock_daily_basic', 'stock_moneyflow',
                'moneyflow_hsgt',
            ]
            for t in tables:
                sync.cursor.execute(f'SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM `{t}`')
                row = sync.cursor.fetchone()
                if row and row[0]:
                    print(f'  {t:<30} {row[0]:>10,} 条  [{row[1]} ~ {row[2]}]')
                else:
                    print(f'  {t:<30} {"--":>10}  (空)')
        finally:
            sync.close()
        return

    # Full sync
    STEPS = [
        ('calendar',    '交易日历',        'sync_trade_calendar',   None,     0),
        ('basic',       '股票基础信息',     'sync_stock_basic',      None,     4000),
        ('daily',       '日线行情',         'sync_daily_history',    start_date, 100),
        ('adj',         '复权因子',         'sync_adj_factor',       start_date, 100),
        ('daily_basic', '每日指标',         'sync_daily_basic',      start_date, 100),
        ('moneyflow',   '个股资金流向',     'sync_moneyflow',        start_date, 100),
        ('hsgt',        '北向资金',         'sync_moneyflow_hsgt',   start_date, 100),
        ('factors',     '技术指标补算',     None,                    None,     0),
    ]

    total_steps = len([s for s in STEPS if s[0] not in skip_set])
    current = 0
    t_start = time.time()

    sync = TushareDataSync()
    try:
        for key, name, method_name, default_start, min_rows in STEPS:
            if key in skip_set:
                print(f'\n  [SKIP] {name} (--skip {key})')
                continue

            current += 1
            print_step(current, total_steps, name)

            # 断点续传检测
            if key != 'factors' and min_rows > 0:
                table_map = {
                    'calendar': 'stock_trade_calendar', 'basic': 'stock_basic',
                    'daily': 'stock_daily_history', 'adj': 'stock_factor',
                    'daily_basic': 'stock_daily_basic', 'moneyflow': 'stock_moneyflow',
                    'hsgt': 'moneyflow_hsgt',
                }
                table = table_map.get(key)
                if table and detect_existing(sync, table, min_rows):
                    print_result(name, 0, 0, skipped=True)
                    continue

            t_step = time.time()

            if key == 'factors':
                # 技术指标使用独立的补算脚本
                from scripts.backfill_factors_v2 import get_db_connection, get_stock_list, process_stock

                conn2 = get_db_connection()
                try:
                    stock_list = get_stock_list(conn2)
                    total = 0
                    for i, ts_code in enumerate(stock_list, 1):
                        inserted, skipped_count, err = process_stock(
                            conn2, ts_code,
                            start_date=None, end_date=None,
                            force=True, dry_run=False, batch_size=3000,
                        )
                        total += inserted
                        if i % 500 == 0:
                            print(f'    进度: {i}/{len(stock_list)}, 已写入 {total} 条')
                    print_result(name, total, time.time() - t_step)
                finally:
                    conn2.close()
            else:
                method = getattr(sync, method_name)
                if default_start:
                    rows = method(start_date=default_start, end_date=end_date)
                else:
                    rows = method()
                print_result(name, rows or 0, time.time() - t_step)

        elapsed = time.time() - t_start
        print()
        print('=' * 70)
        print(f'  初始化完成! 总耗时 {elapsed:.0f}s ({elapsed/60:.1f}分钟)')
        print(f'  结束时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('=' * 70)
        print()

    except KeyboardInterrupt:
        print('\n\n  用户中断。已完成步骤的数据已保存。')
        sys.exit(0)
    except Exception as e:
        logger.error(f'初始化失败: {e}')
        print(f'\n  [ERROR] 初始化失败: {e}')
        sys.exit(1)
    finally:
        sync.close()


if __name__ == '__main__':
    main()
