# -*- coding: utf-8 -*-
"""
stock_business 宽表数据同步脚本
===============================
单连接、单流程方案：预计算 + 同步在同一连接上完成。

用法:
    python scripts/sync_stock_business.py --full --skip-existing
"""

import argparse
import sys
import time
import logging
from collections import deque
from datetime import datetime

import pymysql
from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from app.utils.db_utils import DatabaseUtils

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def _get_db_connection():
    DatabaseUtils.reload_from_env()
    return pymysql.connect(
        host=DatabaseUtils._host,
        user=DatabaseUtils._user,
        password=DatabaseUtils._password,
        database=DatabaseUtils._database,
        charset=DatabaseUtils._charset,
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=600,
        write_timeout=600,
        connect_timeout=30,
    )


def _setup(conn):
    c = conn.cursor()
    c.execute("SET SESSION net_read_timeout = 600")
    c.execute("SET SESSION net_write_timeout = 600")
    c.execute("SET SESSION wait_timeout = 28800")
    c.close()


def _reconnect(conn):
    try:
        conn.ping(reconnect=True)
        _setup(conn)
        return conn
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        conn = _get_db_connection()
        _setup(conn)
        return conn


def get_target_dates(cur, days=None, full=False, specific_date=None, skip_existing=False):
    if specific_date:
        cur.execute(
            'SELECT DISTINCT trade_date FROM stock_daily_basic WHERE trade_date = %s',
            (specific_date,)
        )
    elif full:
        if skip_existing:
            cur.execute(
                'SELECT DISTINCT d.trade_date FROM stock_daily_basic d '
                'LEFT JOIN (SELECT DISTINCT trade_date FROM stock_business) b '
                'ON d.trade_date = b.trade_date '
                'WHERE b.trade_date IS NULL ORDER BY d.trade_date'
            )
        else:
            cur.execute(
                'SELECT DISTINCT trade_date FROM stock_daily_basic ORDER BY trade_date'
            )
    else:
        cur.execute(
            'SELECT DISTINCT trade_date FROM stock_daily_basic '
            'ORDER BY trade_date DESC LIMIT %s', (days or 30,)
        )
    return sorted([r['trade_date'] for r in cur.fetchall()])


# ---------------------------------------------------------------------------
# 预计算 + 同步（单函数，同一连接）
# ---------------------------------------------------------------------------

_WINDOWS = [5, 10, 20, 30, 60, 120]
_BATCH = 200


def _build_insert_sql():
    cols = (
        'ts_code, trade_date, stock_name, daily_close, '
        'turnover_rate, turnover_rate_f, volume_ratio, '
        'pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, '
        'total_share, float_share, free_share, total_mv, circ_mv, '
        'factor_open, factor_high, factor_low, factor_pre_close, '
        'factor_change, factor_pct_change, factor_vol, factor_amount, '
        'factor_adj_factor, '
        'factor_open_hfq, factor_open_qfq, factor_close_hfq, factor_close_qfq, '
        'factor_high_hfq, factor_high_qfq, factor_low_hfq, factor_low_qfq, '
        'factor_pre_close_hfq, factor_pre_close_qfq, '
        'factor_macd_dif, factor_macd_dea, factor_macd, '
        'factor_kdj_k, factor_kdj_d, factor_kdj_j, '
        'factor_rsi_6, factor_rsi_12, factor_rsi_24, '
        'factor_boll_upper, factor_boll_mid, factor_boll_lower, factor_cci, '
        'moneyflow_pct_change, moneyflow_latest, '
        'moneyflow_net_amount, moneyflow_net_d5_amount, '
        'moneyflow_buy_lg_amount, moneyflow_buy_lg_amount_rate, '
        'moneyflow_buy_md_amount, moneyflow_buy_md_amount_rate, '
        'moneyflow_buy_sm_amount, moneyflow_buy_sm_amount_rate, '
        'ma5, ma10, ma20, ma30, ma60, ma120'
    )
    all_f = [f.strip() for f in cols.split(',')]
    upd = [f for f in all_f if f not in ('ts_code', 'trade_date')]
    on_dup = ',\n            '.join(f'{f} = VALUES({f})' for f in upd)
    return cols, on_dup


_INSERT_COLS, _ON_DUP = _build_insert_sql()

_INSERT_SQL = f"""
    INSERT INTO stock_business ({_INSERT_COLS})
    SELECT
        db.ts_code, db.trade_date, sb.name,
        h.close, db.turnover_rate, db.turnover_rate_f, db.volume_ratio,
        db.pe, db.pe_ttm, db.pb, db.ps, db.ps_ttm, db.dv_ratio, db.dv_ttm,
        db.total_share, db.float_share, db.free_share, db.total_mv, db.circ_mv,
        h.open, h.high, h.low, h.pre_close, h.change_c, h.pct_chg, h.vol, h.amount,
        f.adj_factor,
        f.open_hfq, f.open_qfq, f.close_hfq, f.close_qfq,
        f.high_hfq, f.high_qfq, f.low_hfq, f.low_qfq,
        f.pre_close_hfq, f.pre_close_qfq,
        f.macd_dif, f.macd_dea, f.macd,
        f.kdj_k, f.kdj_d, f.kdj_j,
        f.rsi_6, f.rsi_12, f.rsi_24,
        f.boll_upper, f.boll_mid, f.boll_lower, f.cci,
        h.pct_chg, h.close,
        mf.net_mf_amount, mf5.net_d5_amount,
        mf.buy_lg_amount,
        CASE WHEN IFNULL(mf.buy_lg_amount,0)+IFNULL(mf.sell_lg_amount,0)>0
            THEN ROUND(mf.buy_lg_amount/(mf.buy_lg_amount+mf.sell_lg_amount)*100,2) ELSE NULL END,
        mf.buy_md_amount,
        CASE WHEN IFNULL(mf.buy_md_amount,0)+IFNULL(mf.sell_md_amount,0)>0
            THEN ROUND(mf.buy_md_amount/(mf.buy_md_amount+mf.sell_md_amount)*100,2) ELSE NULL END,
        mf.buy_sm_amount,
        CASE WHEN IFNULL(mf.buy_sm_amount,0)+IFNULL(mf.sell_sm_amount,0)>0
            THEN ROUND(mf.buy_sm_amount/(mf.buy_sm_amount+mf.sell_sm_amount)*100,2) ELSE NULL END,
        ma.ma5, ma.ma10, ma.ma20, ma.ma30, ma.ma60, ma.ma120
    FROM stock_daily_basic db
    LEFT JOIN stock_basic sb    ON db.ts_code = sb.ts_code
    LEFT JOIN stock_daily_history h ON db.ts_code = h.ts_code AND db.trade_date = h.trade_date
    LEFT JOIN stock_factor f    ON db.ts_code = f.ts_code AND db.trade_date = f.trade_date
    LEFT JOIN stock_moneyflow mf ON db.ts_code = mf.ts_code AND db.trade_date = mf.trade_date
    LEFT JOIN _ma_cache ma      ON db.ts_code = ma.ts_code AND db.trade_date = ma.trade_date
    LEFT JOIN _mf5_cache mf5    ON db.ts_code = mf5.ts_code AND db.trade_date = mf5.trade_date
    WHERE db.trade_date = %s AND f.ts_code IS NOT NULL
    ON DUPLICATE KEY UPDATE {_ON_DUP}
"""


def run_sync(conn, dates):
    """预计算 MA + 净流入，然后按日期同步。全部在同一连接上完成。"""
    cur = conn.cursor()

    # ---- 预计算 MA ----
    logger.info('预计算 MA 均线...')
    t0 = time.time()
    cur.execute('DROP TEMPORARY TABLE IF EXISTS _ma_cache')
    cur.execute("""
        CREATE TEMPORARY TABLE _ma_cache (
            ts_code VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            ma5 DECIMAL(10,3), ma10 DECIMAL(10,3), ma20 DECIMAL(10,3),
            ma30 DECIMAL(10,3), ma60 DECIMAL(10,3), ma120 DECIMAL(10,3),
            PRIMARY KEY (ts_code, trade_date)
        )
    """)

    cur.execute('SELECT DISTINCT ts_code FROM stock_daily_history ORDER BY ts_code')
    all_codes = [r['ts_code'] for r in cur.fetchall()]
    total_codes = len(all_codes)
    inserted = 0

    for bi in range(0, total_codes, _BATCH):
        batch = all_codes[bi:bi + _BATCH]
        ph = ','.join(['%s'] * len(batch))
        cur.execute(
            f"SELECT ts_code, trade_date, close FROM stock_daily_history "
            f"WHERE ts_code IN ({ph}) ORDER BY ts_code, trade_date",
            batch
        )

        rows = []
        current_code = None
        windows = {w: deque(maxlen=w) for w in _WINDOWS}

        for row in cur:
            code, date, close = row['ts_code'], row['trade_date'], row['close']
            if close is None:
                continue
            close = float(close)
            if code != current_code:
                current_code = code
                windows = {w: deque(maxlen=w) for w in _WINDOWS}
            for w in _WINDOWS:
                windows[w].append(close)
            if len(windows[5]) >= 5:
                rows.append((
                    code, date,
                    round(sum(windows[5]) / len(windows[5]), 3),
                    round(sum(windows[10]) / len(windows[10]), 3) if len(windows[10]) >= 10 else None,
                    round(sum(windows[20]) / len(windows[20]), 3) if len(windows[20]) >= 20 else None,
                    round(sum(windows[30]) / len(windows[30]), 3) if len(windows[30]) >= 30 else None,
                    round(sum(windows[60]) / len(windows[60]), 3) if len(windows[60]) >= 60 else None,
                    round(sum(windows[120]) / len(windows[120]), 3) if len(windows[120]) >= 120 else None,
                ))

        if rows:
            cur.executemany('INSERT INTO _ma_cache VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', rows)
            conn.commit()
            inserted += len(rows)

        if (bi // _BATCH) % 10 == 0:
            logger.info('  MA: %d/%d 只股票，已写入 %d 条', bi + len(batch), total_codes, inserted)

    logger.info('MA 预计算完成: %d 条，耗时 %.1fs', inserted, time.time() - t0)

    # ---- 预计算净流入 ----
    logger.info('预计算 5 日净流入...')
    t1 = time.time()
    cur.execute('DROP TEMPORARY TABLE IF EXISTS _mf5_cache')
    cur.execute("""
        CREATE TEMPORARY TABLE _mf5_cache (
            ts_code VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            net_d5_amount DECIMAL(20,2),
            PRIMARY KEY (ts_code, trade_date)
        )
    """)

    inserted2 = 0
    for bi in range(0, total_codes, _BATCH):
        batch = all_codes[bi:bi + _BATCH]
        ph = ','.join(['%s'] * len(batch))
        cur.execute(
            f"SELECT ts_code, trade_date, net_mf_amount FROM stock_moneyflow "
            f"WHERE ts_code IN ({ph}) ORDER BY ts_code, trade_date",
            batch
        )

        rows = []
        current_code = None
        window = deque(maxlen=5)
        for row in cur:
            code, date, amt = row['ts_code'], row['trade_date'], row['net_mf_amount']
            if amt is None:
                continue
            if code != current_code:
                current_code = code
                window = deque(maxlen=5)
            window.append(float(amt))
            if len(window) >= 5:
                rows.append((code, date, round(sum(window), 2)))

        if rows:
            cur.executemany('INSERT INTO _mf5_cache VALUES (%s,%s,%s)', rows)
            conn.commit()
            inserted2 += len(rows)

    logger.info('净流入预计算完成: %d 条，耗时 %.1fs', inserted2, time.time() - t1)

    # ---- 按日期同步 ----
    logger.info('开始按日期写入 stock_business ...')
    total_rows = 0
    start_time = time.time()

    for i, trade_date in enumerate(dates, 1):
        try:
            cur.execute(_INSERT_SQL, (trade_date,))
            affected = cur.rowcount
            conn.commit()
            total_rows += affected
            elapsed = time.time() - start_time
            avg = elapsed / i
            eta = avg * (len(dates) - i)
            logger.info(
                '[%d/%d] %s: %d 条 | 累计 %d 条 | 耗时 %.0fs | ETA %.0fs',
                i, len(dates), trade_date, affected, total_rows, elapsed, eta
            )
        except Exception as e:
            logger.error('[%d/%d] %s: 失败 - %s', i, len(dates), trade_date, e)
            conn = _reconnect(conn)
            cur = conn.cursor()

    # 清理
    cur.execute('DROP TEMPORARY TABLE IF EXISTS _ma_cache')
    cur.execute('DROP TEMPORARY TABLE IF EXISTS _mf5_cache')
    conn.commit()
    cur.close()

    elapsed = time.time() - start_time
    logger.info('同步完成！共 %d 个交易日，%d 条数据，耗时 %.1fs', len(dates), total_rows, elapsed)
    return total_rows


def main():
    parser = argparse.ArgumentParser(description='同步 stock_business 宽表')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--date', type=str, default=None)
    parser.add_argument('--skip-existing', action='store_true')
    args = parser.parse_args()

    logger.info('开始同步 stock_business 宽表 ...')
    conn = _get_db_connection()
    _setup(conn)

    try:
        cur = conn.cursor()
        specific_date = None
        if args.date:
            try:
                specific_date = datetime.strptime(args.date, '%Y%m%d').date()
            except ValueError:
                logger.error('日期格式错误: %s', args.date)
                sys.exit(1)

        dates = get_target_dates(cur, days=args.days, full=args.full,
                                 specific_date=specific_date,
                                 skip_existing=args.skip_existing)
        cur.close()

        if not dates:
            logger.warning('没有找到需要同步的交易日数据')
            return

        mode = '全量' if args.full else ('指定日期' if specific_date else f'最近{args.days}天')
        if args.skip_existing:
            mode += '（跳过已有）'
        logger.info('模式: %s，共 %d 个交易日待同步', mode, len(dates))

        run_sync(conn, dates)

    finally:
        conn.close()


def sync_stock_business(days=None, full=False, specific_date=None, skip_existing=False):
    conn = _get_db_connection()
    _setup(conn)
    try:
        cur = conn.cursor()
        dates = get_target_dates(cur, days=days, full=full,
                                 specific_date=specific_date,
                                 skip_existing=skip_existing)
        cur.close()
        if not dates:
            return 0
        return run_sync(conn, dates)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
