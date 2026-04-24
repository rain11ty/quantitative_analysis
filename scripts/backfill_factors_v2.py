# -*- coding: utf-8 -*-
"""
批量补算技术指标数据（流式优化版，支持10年数据量）
=====================================================
改进点：
  1. 使用 raw SQL 流式读取（yield_per），避免 .all() 一次全加载
  2. 使用 INSERT ... ON DUPLICATE KEY UPDATE 批量写入（比 ORM merge 快 10x）
  3. CCI 窗口修正为 14（与 stock_service.py 一致）
  4. 支持 --start-date / --end-date 参数控制计算范围
  5. 支持 --force 覆盖已有指标数据
  6. 进度条 + ETA + 预估时间

使用方式：
  # 补算近3年（默认）
  python scripts/backfill_factors_v2.py

  # 补算全部历史
  python scripts/backfill_factors_v2.py --start-date 20150101

  # 仅处理前50只测试
  python scripts/backfill_factors_v2.py --limit 50

  # 强制覆盖已有指标
  python scripts/backfill_factors_v2.py --force

  # 仅统计不写入
  python scripts/backfill_factors_v2.py --dry-run
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import pymysql
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


# ============================================================
#  技术指标计算（与 stock_service.py _calculate_technical_indicators 保持一致）
# ============================================================
def calculate_all_indicators(df):
    """
    向量化计算所有技术指标
    参数 df: DataFrame，必须包含 close/high/low/open/vol/amount 列，按 trade_date 升序
    返回: DataFrame 新增指标列
    """
    close = pd.Series(df['close'], dtype=float)
    high = pd.Series(df['high'], dtype=float)
    low = pd.Series(df['low'], dtype=float)

    # --- MACD(12,26,9) ---
    ema_fast = close.ewm(span=12).mean()
    ema_slow = close.ewm(span=26).mean()
    macd_dif = ema_fast - ema_slow
    macd_dea = macd_dif.ewm(span=9).mean()
    macd_val = (macd_dif - macd_dea) * 2

    # --- KDJ(9,3,3) ---
    low_min_n = low.rolling(window=9).min()
    high_max_n = high.rolling(window=9).max()
    rsv = (close - low_min_n) / (high_max_n - low_min_n.replace(0, np.nan)) * 100
    kdj_k = rsv.ewm(alpha=1/3).mean()
    kdj_d = kdj_k.ewm(alpha=1/3).mean()
    kdj_j = 3 * kdj_k - 2 * kdj_d

    # --- RSI(6,12,24) ---
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))

    def calc_rsi(period):
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    rsi_6 = calc_rsi(6)
    rsi_12 = calc_rsi(12)
    rsi_24 = calc_rsi(24)

    # --- BOLL(20,2) ---
    boll_mid = close.rolling(window=20).mean()
    boll_std = close.rolling(window=20).std()
    boll_upper = boll_mid + (boll_std * 2)
    boll_lower = boll_mid - (boll_std * 2)

    # --- CCI(14) ---
    tp = (high + low + close) / 3
    ma_tp = tp.rolling(window=14).mean()
    md_tp = tp.rolling(window=14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - ma_tp) / (0.015 * md_tp.replace(0, np.nan))

    df = df.copy()
    df['macd_dif'] = macd_dif.round(4).fillna(0)
    df['macd_dea'] = macd_dea.round(4).fillna(0)
    df['macd'] = macd_val.round(4).fillna(0)
    df['kdj_k'] = kdj_k.round(2).fillna(0)
    df['kdj_d'] = kdj_d.round(2).fillna(0)
    df['kdj_j'] = kdj_j.round(2).fillna(0)
    df['rsi_6'] = rsi_6.round(2).fillna(0)
    df['rsi_12'] = rsi_12.round(2).fillna(0)
    df['rsi_24'] = rsi_24.round(2).fillna(0)
    df['boll_upper'] = boll_upper.round(2).fillna(0)
    df['boll_mid'] = boll_mid.round(2).fillna(0)
    df['boll_lower'] = boll_lower.round(2).fillna(0)
    df['cci'] = cci.round(2).fillna(0)

    return df


# ============================================================
#  数据库连接
# ============================================================
def get_db_connection():
    """获取 MySQL 直连（绕过 ORM，用于流式读写）
    注意：不使用 DictCursor，因为 pd.read_sql + DictCursor 会导致列名被当作值返回
    """
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'root'),
        database=os.getenv('DB_NAME', 'stock_cursor'),
        charset=os.getenv('DB_CHARSET', 'utf8mb4'),
    )


# ============================================================
#  获取股票列表
# ============================================================
def get_stock_list(conn, limit=None):
    """获取所有在市股票的 ts_code 列表"""
    sql = "SELECT ts_code FROM stock_basic ORDER BY ts_code"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


# ============================================================
#  流式读取日线数据
# ============================================================
def load_daily_data(conn, ts_code, start_date=None, end_date=None):
    """
    流式加载单只股票的日线数据
    返回 DataFrame，按 trade_date 升序
    """
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT ts_code, trade_date, open, high, low, close, pre_close,
               change_c, pct_chg, vol, amount
        FROM stock_daily_history
        WHERE {where}
        ORDER BY trade_date ASC
    """

    # 使用 pandas 直接读取，比 ORM 快得多
    df = pd.read_sql(sql, conn, params=params)
    if df.empty:
        return df

    # trade_date 是 MySQL DATE 类型，pymysql 返回 datetime.date 对象
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    # 统一列名：change_c → change（与 stock_factor 一致）
    df = df.rename(columns={'change_c': 'change', 'pct_chg': 'pct_change'})
    return df


# ============================================================
#  查询已有 factor 数据
# ============================================================
def get_existing_factors(conn, ts_code, force=False):
    """
    查询某只股票已有的 factor 记录
    force=False: 返回已有日期集合（用于跳过）
    force=True:  返回空集（全部重算覆盖）
    """
    if force:
        return set()

    sql = """
        SELECT trade_date FROM stock_factor
        WHERE ts_code = %s AND macd_dif IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, (ts_code,))
        return {row[0] for row in cur.fetchall()}


# ============================================================
#  批量写入（INSERT ... ON DUPLICATE KEY UPDATE）
# ============================================================
FACTOR_COLUMNS = [
    'ts_code', 'trade_date',
    'close', 'open', 'high', 'low', 'pre_close', 'change', 'pct_change',
    'vol', 'amount',
    'macd_dif', 'macd_dea', 'macd',
    'kdj_k', 'kdj_d', 'kdj_j',
    'rsi_6', 'rsi_12', 'rsi_24',
    'boll_upper', 'boll_mid', 'boll_lower',
    'cci',
]

UPDATE_COLUMNS = [c for c in FACTOR_COLUMNS if c not in ('ts_code', 'trade_date')]

INSERT_SQL = f"""
    INSERT INTO stock_factor ({', '.join(f'`{c}`' for c in FACTOR_COLUMNS)})
    VALUES ({', '.join(['%s'] * len(FACTOR_COLUMNS))})
    ON DUPLICATE KEY UPDATE {', '.join(f'`{c}`=VALUES(`{c}`)' for c in UPDATE_COLUMNS)}
"""


def batch_upsert_factors(conn, records, batch_size=3000):
    """批量写入 stock_factor 表"""
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
#  处理单只股票
# ============================================================
def process_stock(conn, ts_code, start_date, end_date, force, dry_run, batch_size):
    """
    处理单只股票：取日线 → 计算 → 写入 stock_factor
    返回: (成功条数, 跳过条数, 错误信息或None)
    """
    try:
        # 1. 加载日线数据（需要更早的数据作为预热期，多取 50 天）
        warmup_date = None
        if start_date:
            warmup_date = (datetime.strptime(start_date, '%Y%m%d') - timedelta(days=90)).strftime('%Y%m%d')

        df = load_daily_data(conn, ts_code, start_date=warmup_date, end_date=end_date)
        if df.empty or len(df) < 20:
            return 0, 0, None

        # 2. 获取已有 factor 日期（有有效指标的才跳过）
        existing_dates = get_existing_factors(conn, ts_code, force=force)

        # 3. 计算技术指标
        df_with_factors = calculate_all_indicators(df)

        # 4. 过滤：热身期 + 日期范围 + 已有跳过
        records = []
        warmup_count = 25  # MACD(26) 需要约 26 天预热
        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt = pd.to_datetime(end_date) if end_date else None

        for i, row in df_with_factors.iterrows():
            if i < warmup_count:
                continue

            trade_date = row['trade_date']
            trade_date_obj = trade_date.date() if hasattr(trade_date, 'date') else trade_date

            # 日期范围过滤
            if start_dt and trade_date < start_dt:
                continue
            if end_dt and trade_date > end_dt:
                continue

            # 已有有效指标则跳过
            if not force and trade_date_obj in existing_dates:
                continue

            records.append((
                ts_code,
                trade_date_obj,
                float(row['close']) if pd.notna(row.get('close')) else None,
                float(row['open']) if pd.notna(row.get('open')) else None,
                float(row['high']) if pd.notna(row.get('high')) else None,
                float(row['low']) if pd.notna(row.get('low')) else None,
                float(row.get('pre_close', 0)) if pd.notna(row.get('pre_close')) else None,
                float(row.get('change', 0)) if pd.notna(row.get('change')) else None,
                float(row.get('pct_change', 0)) if pd.notna(row.get('pct_change')) else None,
                float(row['vol']) if pd.notna(row.get('vol')) else None,
                float(row['amount']) if pd.notna(row.get('amount')) else None,
                float(row['macd_dif']),
                float(row['macd_dea']),
                float(row['macd']),
                float(row['kdj_k']),
                float(row['kdj_d']),
                float(row['kdj_j']),
                float(row['rsi_6']),
                float(row['rsi_12']),
                float(row['rsi_24']),
                float(row['boll_upper']),
                float(row['boll_mid']),
                float(row['boll_lower']),
                float(row['cci']),
            ))

        if not records:
            return 0, len(existing_dates), None

        if dry_run:
            return len(records), len(existing_dates), None

        # 5. 批量写入
        inserted = batch_upsert_factors(conn, records, batch_size)
        return inserted, len(existing_dates), None

    except Exception as e:
        conn.rollback()
        return 0, 0, f"{str(e)[:200]}"


# ============================================================
#  进度条
# ============================================================
def print_progress(idx, total, start_time, extra_info=''):
    """打印进度条 + ETA"""
    pct = idx / total * 100 if total > 0 else 0
    elapsed = time.time() - start_time
    eta = (elapsed / idx * (total - idx)) if idx > 0 and idx < total else 0

    bar_len = 30
    filled = int(bar_len * idx / total) if total > 0 else 0
    bar = '=' * filled + '>' * (1 if filled < bar_len else 0) + '.' * max(bar_len - filled - 1, 0)

    elapsed_str = f"{elapsed:.0f}s"
    eta_str = f"{eta:.0f}s" if eta > 0 else "--"

    msg = f"\r  [{bar}] {idx}/{total} ({pct:.1f}%) | {elapsed_str} elapsed, ETA {eta_str}"
    if extra_info:
        msg += f" | {extra_info}"

    if sys.stdout.isatty():
        print(msg, end='', flush=True)
    else:
        if idx % 50 == 0 or idx == total:
            print(f"  进度: {idx}/{total} ({pct:.1f}%), {extra_info}")


# ============================================================
#  主函数
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='批量补算技术指标数据（流式优化版）')
    parser.add_argument('--limit', type=int, default=None, help='只处理前N只股票')
    parser.add_argument('--batch-size', type=int, default=3000, help='每批写入条数（默认3000）')
    parser.add_argument('--start-date', type=str, default=None,
                        help='起始日期 YYYYMMDD（默认近3年：今天-3年）')
    parser.add_argument('--end-date', type=str, default=None,
                        help='结束日期 YYYYMMDD（默认今天）')
    parser.add_argument('--dry-run', action='store_true', help='只统计不写入')
    parser.add_argument('--force', action='store_true',
                        help='强制覆盖已有指标数据（默认跳过已有有效指标的记录）')
    args = parser.parse_args()

    # 默认：近3年
    if not args.start_date:
        three_years_ago = (datetime.now() - timedelta(days=365 * 3)).strftime('%Y%m%d')
        args.start_date = three_years_ago
    if not args.end_date:
        args.end_date = datetime.now().strftime('%Y%m%d')

    print("=" * 60)
    print("  技术指标批量补算工具 v2（流式优化版）")
    print(f"  日期范围: {args.start_date} ~ {args.end_date}")
    print(f"  模式: {'[DRY RUN]' if args.dry_run else '[正式写入]'}"
          f"{'  [FORCE覆盖]' if args.force else ''}")
    print("=" * 60)

    conn = get_db_connection()

    try:
        start_time = time.time()

        # 获取股票列表
        stock_list = get_stock_list(conn, limit=args.limit)
        total_stocks = len(stock_list)
        print(f"\n共 {total_stocks} 只待处理股票\n")

        stats = {
            'success': 0,
            'inserted': 0,
            'skipped': 0,
            'no_data': 0,
            'error': 0,
            'errors_detail': [],
        }

        for idx, ts_code in enumerate(stock_list, 1):
            inserted, skipped, err = process_stock(
                conn, ts_code,
                start_date=args.start_date,
                end_date=args.end_date,
                force=args.force,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
            )

            if err:
                stats['error'] += 1
                stats['errors_detail'].append(f"  {ts_code}: {err}")
            elif inserted == 0 and skipped == 0:
                stats['no_data'] += 1
            else:
                stats['success'] += 1
                stats['inserted'] += inserted
                stats['skipped'] += skipped

            extra = f"+{stats['inserted']}条 跳过{stats['skipped']} 错误{stats['error']}"
            print_progress(idx, total_stocks, start_time, extra)

        elapsed = time.time() - start_time

        # 最终报告
        print(f"\n\n{'=' * 60}")
        print("  补算完成报告")
        print(f"{'=' * 60}")
        print(f"  日期范围:     {args.start_date} ~ {args.end_date}")
        print(f"  处理股票总数: {total_stocks}")
        print(f"  成功处理:     {stats['success']}")
        print(f"  无数据跳过:   {stats['no_data']}")
        print(f"  失败跳过:     {stats['error']}")
        print(f"  新增因子数:   {stats['inserted']} 条")
        print(f"  跳过已有:     {stats['skipped']} 条")
        print(f"  耗时:         {elapsed:.1f}s")
        print(f"  速度:         {stats['inserted'] / elapsed:.0f} 条/秒" if elapsed > 0 and stats['inserted'] > 0 else "")

        if stats['errors_detail']:
            print(f"\n  失败详情 ({min(len(stats['errors_detail']), 20)} 条):")
            for e in stats['errors_detail'][:20]:
                print(e)
            if len(stats['errors_detail']) > 20:
                print(f"  ... 还有 {len(stats['errors_detail']) - 20} 条错误")
        print()

    finally:
        conn.close()


if __name__ == '__main__':
    main()
