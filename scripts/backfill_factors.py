# -*- coding: utf-8 -*-
"""
批量补全所有股票的技术指标数据（stock_factor 表）
=====================================
原理：
  1. 查出 stock_basic 中所有股票
  2. 对每只股票，从 stock_daily 取日线数据
  3. 用向量化算法计算 MACD/KDJ/RSI/BOLL/CCI
  4. 批量写入 stock_factor（跳过已有记录，ON DUPLICATE KEY UPDATE）

使用方式：
  cd quantitative_analysis
  python scripts/backfill_factors.py

可选参数：
  --limit N        只处理前 N 只股票（用于测试，默认全部）
  --batch-size M   每 M 条提交一次事务（默认 500）
  --dry-run        只统计不写入
"""

import sys
import os
import time
import argparse

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

# Flask 应用上下文（用于 ORM 访问数据库）
from app import create_app
from app.extensions import db
from app.models import StockBasic, StockDailyHistory, StockFactor


def get_existing_factor_dates(session, ts_code: str) -> set:
    """查询某只股票已有的 factor 日期集合"""
    results = session.query(StockFactor.trade_date).filter_by(ts_code=ts_code).all()
    return {r[0] for r in results}


def calculate_all_indicators(df):
    """
    向量化计算所有技术指标（复用 stock_service 的逻辑）
    参数 df: DataFrame，必须包含 close/high/low/open/vol/amount 列，按 trade_date 升序
    返回: DataFrame 新增指标列
    """
    close = pd.Series(df['close'], dtype=float)
    high = pd.Series(df['high'], dtype=float)
    low = pd.Series(df['low'], dtype=float)

    # --- MACD ---
    ema_fast = close.ewm(span=12).mean()
    ema_slow = close.ewm(span=26).mean()
    macd_dif = ema_fast - ema_slow
    macd_dea = macd_dif.ewm(span=9).mean()
    macd_val = (macd_dif - macd_dea) * 2

    # --- KDJ ---
    low_min_n = low.rolling(window=9).min()
    high_max_n = high.rolling(window=9).max()
    rsv = (close - low_min_n) / (high_max_n - low_min_n.replace(0, np.nan)) * 100
    kdj_k = rsv.ewm(alpha=1 / 3).mean()
    kdj_d = kdj_k.ewm(alpha=1 / 3).mean()
    kdj_j = 3 * kdj_k - 2 * kdj_d

    # --- RSI(6, 12, 24) ---
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

    # --- BOLL ---
    boll_mid = close.rolling(window=20).mean()
    boll_std = close.rolling(window=20).std()
    boll_upper = boll_mid + (boll_std * 2)
    boll_lower = boll_mid - (boll_std * 2)

    # --- CCI ---
    tp = (high + low + close) / 3
    ma_tp = tp.rolling(window=20).mean()
    md = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))

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


def process_stock(session, stock, batch_size, dry_run):
    """
    处理单只股票：取日线 -> 计算 -> 写入 stock_factor
    返回: (成功条数, 跳过条数, 错误信息或None)
    """
    ts_code = stock.ts_code

    try:
        # 1. 取日线数据（不限量，取全部）
        daily_rows = (
            session.query(StockDailyHistory)
            .filter_by(ts_code=ts_code)
            .order_by(StockDailyHistory.trade_date.asc())
            .all()
        )
        if not daily_rows:
            return 0, 0, None

        # 转 DataFrame
        records = [r.to_dict() for r in daily_rows]
        df = pd.DataFrame(records)
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        # 2. 已有的 factor 日期（跳过）
        existing_dates = get_existing_factor_dates(session, ts_code)

        # 3. 计算技术指标
        df_with_factors = calculate_all_indicators(df)

        # 4. 过滤掉已有数据 + 前12天热身期不足的数据
        new_records = []
        for i, row in df_with_factors.iterrows():
            if i < 12:  # 热身期跳过
                continue
            date_val = row['trade_date']
            # 统一为 date 类型比较
            if hasattr(date_val, 'date'):
                d = date_val.date()
            elif isinstance(date_val, str):
                d = datetime.strptime(date_val[:10], '%Y-%m-%d').date()
            else:
                d = date_val
            if d in existing_dates:
                continue
            new_records.append(row)

        if not new_records:
            return 0, 0, None

        if dry_run:
            return len(new_records), len(existing_dates), None

        # 5. 批量写入
        inserted = 0
        for row in new_records:
            date_val = row['trade_date']
            if hasattr(date_val, 'date'):
                d = date_val.date()
            elif isinstance(date_val, str):
                d = datetime.strptime(date_val[:10], '%Y-%m-%d').date()
            else:
                d = date_val

            factor = StockFactor(
                ts_code=ts_code,
                trade_date=d,
                close=float(row['close']) if pd.notna(row['close']) else None,
                open=float(row['open']) if pd.notna(row['open']) else None,
                high=float(row['high']) if pd.notna(row['high']) else None,
                low=float(row['low']) if pd.notna(row['low']) else None,
                vol=float(row['vol']) if pd.notna(row['vol']) else None,
                amount=float(row['amount']) if pd.notna(row['amount']) else None,
                macd_dif=float(row['macd_dif']),
                macd_dea=float(row['macd_dea']),
                macd=float(row['macd']),
                kdj_k=float(row['kdj_k']),
                kdj_d=float(row['kdj_d']),
                kdj_j=float(row['kdj_j']),
                rsi_6=float(row['rsi_6']),
                rsi_12=float(row['rsi_12']),
                rsi_24=float(row['rsi_24']),
                boll_upper=float(row['boll_upper']),
                boll_mid=float(row['boll_mid']),
                boll_lower=float(row['boll_lower']),
                cci=float(row['cci']),
            )
            session.merge(factor)  # ON DUPLICATE KEY UPDATE 效果
            inserted += 1

            if inserted % batch_size == 0:
                session.commit()

        session.commit()
        return inserted, len(existing_dates), None

    except Exception as e:
        session.rollback()
        return 0, 0, f"{str(e)[:100]}"


def main():
    parser = argparse.ArgumentParser(description='批量补全技术因子数据')
    parser.add_argument('--limit', type=int, default=None, help='只处理前N只股票')
    parser.add_argument('--batch-size', type=int, default=500, help='每批提交条数（默认500）')
    parser.add_argument('--dry-run', action='store_true', help='只统计不写入')
    args = parser.parse_args()

    app = create_app('default')

    with app.app_context():
        print("=" * 60)
        print("  技术因子批量补全工具")
        print(f"  模式: {'[DRY RUN - 仅统计]' if args.dry_run else '[正式写入]'}")
        print("=" * 60)

        start_time = time.time()

        # 获取所有股票
        query = StockBasic.query.order_by(StockBasic.ts_code)
        if args.limit:
            query = query.limit(args.limit)
        all_stocks = query.all()

        total_stocks = len(all_stocks)
        print(f"\n共 {total_stocks} 只待处理股票\n")

        stats = {
            'success': 0,
            'inserted': 0,
            'skipped': 0,
            'error': 0,
            'errors_detail': [],
        }

        for idx, stock in enumerate(all_stocks, 1):
            inserted, skipped, err = process_stock(
                db.session, stock, args.batch_size, args.dry_run
            )

            if err:
                stats['error'] += 1
                stats['errors_detail'].append(f"  {stock.ts_code}({stock.symbol}): {err}")
            else:
                stats['success'] += 1
                stats['inserted'] += inserted
                stats['skipped'] += skipped

            # 进度显示
            pct = idx / total_stocks * 100
            bar_len = 30
            filled = int(bar_len * idx / total_stocks)
            bar = '=' * filled + '>' * (1 if filled < bar_len else '') + '.' * max(bar_len - filled - 1, 0)

            status = f"[{bar}] {idx}/{total_stocks} ({pct:.1f}%) | "
            status += f"+{stats['inserted']}条 ~{skipped}已存在 | "
            if err:
                status += "ERR"
            else:
                status += "OK"

            # 同行刷新（仅终端支持时）
            if sys.stdout.isatty():
                print(f"\r{status}", end='', flush=True)
            else:
                if idx % 50 == 0 or idx == total_stocks:
                    print(f"  进度: {idx}/{total_stocks}")

        elapsed = time.time() - start_time

        # 最终报告
        print(f"\n\n{'=' * 60}")
        print("  补全完成报告")
        print(f"{'=' * 60}")
        print(f"  处理股票总数: {total_stocks}")
        print(f"  成功处理:     {stats['success']}")
        print(f"  失败跳过:     {stats['error']}")
        print(f"  新增因子数:   {stats['inserted']} 条")
        print(f"  跳过已有:     {stats['skipped']} 条")
        print(f"  耗时:         {elapsed:.1f}s")

        if stats['errors_detail']:
            print(f"\n  失败详情 ({min(len(stats['errors_detail']), 10)} 条):")
            for e in stats['errors_detail'][:10]:
                print(e)
            if len(stats['errors_detail']) > 10:
                print(f"  ... 还有 {len(stats['errors_detail']) - 10} 条错误")
        print()


if __name__ == '__main__':
    main()
