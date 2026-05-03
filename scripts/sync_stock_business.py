# -*- coding: utf-8 -*-
"""
stock_business 宽表数据同步脚本
===============================
从源表（stock_daily_basic, stock_daily_history, stock_factor, stock_moneyflow, stock_basic）
合并数据到 stock_business 宽表，用于条件筛选功能。

使用 INSERT ... SELECT ... ON DUPLICATE KEY UPDATE 实现 upsert，
按 trade_date 分批处理，支持增量和全量同步。

用法:
    python scripts/sync_stock_business.py                  # 默认同步最近 30 个交易日
    python scripts/sync_stock_business.py --days 7         # 同步最近 7 个交易日
    python scripts/sync_stock_business.py --full           # 全量同步
    python scripts/sync_stock_business.py --date 20260502  # 同步指定日期
"""

import argparse
import sys
import time
import logging
from collections import deque
from datetime import datetime

import pymysql

# 加载 .env 配置（项目统一入口）
from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from app.utils.db_utils import DatabaseUtils

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _get_db_connection():
    """获取使用 DictCursor 的数据库连接（脚本专用）。"""
    DatabaseUtils.reload_from_env()
    return pymysql.connect(
        host=DatabaseUtils._host,
        user=DatabaseUtils._user,
        password=DatabaseUtils._password,
        database=DatabaseUtils._database,
        charset=DatabaseUtils._charset,
        cursorclass=pymysql.cursors.DictCursor,
    )

def get_target_dates(conn, days=None, full=False, specific_date=None):
    """获取需要同步的交易日期列表（基于 stock_daily_basic 已有数据）。"""
    with conn.cursor() as cursor:
        if specific_date:
            cursor.execute(
                'SELECT DISTINCT trade_date FROM stock_daily_basic '
                'WHERE trade_date = %s ORDER BY trade_date',
                (specific_date,)
            )
        elif full:
            cursor.execute(
                'SELECT DISTINCT trade_date FROM stock_daily_basic '
                'ORDER BY trade_date'
            )
        else:
            cursor.execute(
                'SELECT DISTINCT trade_date FROM stock_daily_basic '
                'ORDER BY trade_date DESC LIMIT %s',
                (days or 30,)
            )
        rows = cursor.fetchall()
    return sorted([r['trade_date'] for r in rows])


# ---------------------------------------------------------------------------
# 数据预计算（MA 均线 + 5日净流入）
# ---------------------------------------------------------------------------

def _collect_active_ts_codes(cursor, trade_date):
    """获取目标交易日所有活跃股票代码（用于缩小 MA / 净流入计算范围）。"""
    cursor.execute(
        'SELECT DISTINCT ts_code FROM stock_factor WHERE trade_date = %s',
        (trade_date,)
    )
    return [r['ts_code'] for r in cursor.fetchall()]


def prepare_ma_data(cursor, trade_date, ts_codes):
    """从 stock_daily_history 计算 5/10/20/30/60/120 日均线。

    使用双端队列做滑动窗口，避免全表窗口函数扫描。
    只查询目标股票最近 120 个交易日的数据，性能开销可控。

    Returns:
        dict: {ts_code: {'ma5': val, 'ma10': val, ...}}
    """
    if not ts_codes:
        return {}

    placeholders = ','.join(['%s'] * len(ts_codes))
    # 只查最近 150 个交易日的数据（120 日均线需要，留余量应对停牌等缺失）
    sql = f"""
        SELECT ts_code, close
        FROM stock_daily_history
        WHERE ts_code IN ({placeholders})
          AND trade_date <= %s
          AND trade_date >= (
              SELECT MIN(trade_date) FROM (
                  SELECT DISTINCT trade_date FROM stock_daily_history
                  WHERE trade_date <= %s
                  ORDER BY trade_date DESC LIMIT 150
              ) t
          )
        ORDER BY ts_code, trade_date ASC
    """
    cursor.execute(sql, (*ts_codes, trade_date, trade_date))
    rows = cursor.fetchall()

    # 滑动窗口计算各周期均线
    windows = [5, 10, 20, 30, 60, 120]
    result = {}
    current_code = None
    values = deque()

    for row in rows:
        code = row['ts_code']
        close = float(row['close']) if row['close'] is not None else None

        if code != current_code:
            # 新股票，保存上一只的最终 MA 并重置
            if current_code is not None:
                _save_final_ma(result, current_code, values, windows)
            current_code = code
            values = deque()

        if close is not None:
            values.append(close)
            # 只保留最近 120 个值，节省内存
            if len(values) > 120:
                values.popleft()

    # 保存最后一只股票
    if current_code is not None:
        _save_final_ma(result, current_code, values, windows)

    return result


def _save_final_ma(result, code, values, windows):
    """将当前滑动窗口的各周期均线写入 result。"""
    if not values:
        return
    current_sum = sum(values)
    count = len(values)
    ma_dict = {}
    for w in windows:
        if count >= w:
            # 窗口恰好有 w 个值，取最后 w 个的均值
            window_vals = list(values)[-w:]
            ma_dict[f'ma{w}'] = round(sum(window_vals) / w, 3)
        else:
            # 数据不足 w 行，用所有可用数据计算
            ma_dict[f'ma{w}'] = round(current_sum / count, 3)
    result[code] = ma_dict


def prepare_net_d5_data(cursor, trade_date, ts_codes):
    """计算 5 日累计净流入额（net_mf_amount 之和）。

    只查最近 5 天的 stock_moneyflow，性能开销极小。

    Returns:
        dict: {ts_code: net_d5_amount (float or None)}
    """
    if not ts_codes:
        return {}

    placeholders = ','.join(['%s'] * len(ts_codes))
    sql = f"""
        SELECT ts_code, SUM(net_mf_amount) AS net_d5_amount
        FROM stock_moneyflow
        WHERE ts_code IN ({placeholders})
          AND trade_date <= %s
          AND trade_date >= (
              SELECT MAX(trade_date) FROM (
                  SELECT DISTINCT trade_date FROM stock_moneyflow
                  WHERE trade_date <= %s
                  ORDER BY trade_date DESC LIMIT 5
              ) t
          )
        GROUP BY ts_code
    """
    cursor.execute(sql, (*ts_codes, trade_date, trade_date))
    return {
        r['ts_code']: float(r['net_d5_amount']) if r['net_d5_amount'] is not None else None
        for r in cursor.fetchall()
    }


# ---------------------------------------------------------------------------
# 核心同步逻辑
# ---------------------------------------------------------------------------

def _build_insert_sql():
    """构建 INSERT ... SELECT ... ON DUPLICATE KEY UPDATE 完整 SQL。

    以 stock_daily_basic 为主表（覆盖全量股票），
    LEFT JOIN stock_basic / stock_factor / stock_daily_history / stock_moneyflow。
    MA 均线和 5 日净流入通过预计算的临时表关联。

    Returns:
        str: 完整 SQL 语句，接受 %(trade_date)s 参数。
    """
    # 目标表列（与 stock_business 模型字段一一对应）
    insert_columns = (
        'ts_code, trade_date, stock_name, '
        'daily_close, turnover_rate, turnover_rate_f, volume_ratio, '
        'pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, '
        'total_share, float_share, free_share, total_mv, circ_mv, '
        'factor_open, factor_high, factor_low, factor_pre_close, '
        'factor_change, factor_pct_change, factor_vol, factor_amount, '
        'factor_adj_factor, '
        'factor_open_hfq, factor_open_qfq, '
        'factor_close_hfq, factor_close_qfq, '
        'factor_high_hfq, factor_high_qfq, '
        'factor_low_hfq, factor_low_qfq, '
        'factor_pre_close_hfq, factor_pre_close_qfq, '
        'factor_macd_dif, factor_macd_dea, factor_macd, '
        'factor_kdj_k, factor_kdj_d, factor_kdj_j, '
        'factor_rsi_6, factor_rsi_12, factor_rsi_24, '
        'factor_boll_upper, factor_boll_mid, factor_boll_lower, '
        'factor_cci, '
        'moneyflow_pct_change, moneyflow_latest, '
        'moneyflow_net_amount, moneyflow_net_d5_amount, '
        'moneyflow_buy_lg_amount, moneyflow_buy_lg_amount_rate, '
        'moneyflow_buy_md_amount, moneyflow_buy_md_amount_rate, '
        'moneyflow_buy_sm_amount, moneyflow_buy_sm_amount_rate, '
        'ma5, ma10, ma20, ma30, ma60, ma120'
    )

    # ON DUPLICATE KEY UPDATE 子句：所有非主键列均用 VALUES() 覆盖
    all_fields = [f.strip() for f in insert_columns.split(',')]
    pk_fields = {'ts_code', 'trade_date'}
    update_fields = [f for f in all_fields if f not in pk_fields]
    on_dup_clause = ',\n            '.join(f'{f} = VALUES({f})' for f in update_fields)

    sql = f"""
        INSERT INTO stock_business ({insert_columns})
        SELECT
            db.ts_code, db.trade_date, sb.name AS stock_name,

            -- 日线基本数据（收盘价取自 daily_history，其余取自 daily_basic）
            h.close AS daily_close,
            db.turnover_rate, db.turnover_rate_f, db.volume_ratio,
            db.pe, db.pe_ttm, db.pb, db.ps, db.ps_ttm, db.dv_ratio, db.dv_ttm,
            db.total_share, db.float_share, db.free_share, db.total_mv, db.circ_mv,

            -- 技术因子（价格取自 daily_history，复权/指标取自 stock_factor）
            h.open AS factor_open,
            h.high AS factor_high,
            h.low AS factor_low,
            h.pre_close AS factor_pre_close,
            h.change_c AS factor_change,
            h.pct_chg AS factor_pct_change,
            h.vol AS factor_vol,
            h.amount AS factor_amount,
            f.adj_factor AS factor_adj_factor,
            f.open_hfq AS factor_open_hfq, f.open_qfq AS factor_open_qfq,
            f.close_hfq AS factor_close_hfq, f.close_qfq AS factor_close_qfq,
            f.high_hfq AS factor_high_hfq, f.high_qfq AS factor_high_qfq,
            f.low_hfq AS factor_low_hfq, f.low_qfq AS factor_low_qfq,
            f.pre_close_hfq AS factor_pre_close_hfq, f.pre_close_qfq AS factor_pre_close_qfq,
            f.macd_dif AS factor_macd_dif, f.macd_dea AS factor_macd_dea, f.macd AS factor_macd,
            f.kdj_k AS factor_kdj_k, f.kdj_d AS factor_kdj_d, f.kdj_j AS factor_kdj_j,
            f.rsi_6 AS factor_rsi_6, f.rsi_12 AS factor_rsi_12, f.rsi_24 AS factor_rsi_24,
            f.boll_upper AS factor_boll_upper, f.boll_mid AS factor_boll_mid,
            f.boll_lower AS factor_boll_lower,
            f.cci AS factor_cci,

            -- 资金流向原始字段
            h.pct_chg AS moneyflow_pct_change,
            h.close AS moneyflow_latest,
            mf.net_mf_amount AS moneyflow_net_amount,

            -- 5 日累计净流入（来自预计算临时表）
            mf5.net_d5_amount AS moneyflow_net_d5_amount,

            -- 大/中/小单买入额及占比（占比 = 买额 / (买额 + 卖额) * 100）
            mf.buy_lg_amount AS moneyflow_buy_lg_amount,
            CASE WHEN IFNULL(mf.buy_lg_amount, 0) + IFNULL(mf.sell_lg_amount, 0) > 0
                THEN ROUND(mf.buy_lg_amount / (mf.buy_lg_amount + mf.sell_lg_amount) * 100, 2)
                ELSE NULL END AS moneyflow_buy_lg_amount_rate,
            mf.buy_md_amount AS moneyflow_buy_md_amount,
            CASE WHEN IFNULL(mf.buy_md_amount, 0) + IFNULL(mf.sell_md_amount, 0) > 0
                THEN ROUND(mf.buy_md_amount / (mf.buy_md_amount + mf.sell_md_amount) * 100, 2)
                ELSE NULL END AS moneyflow_buy_md_amount_rate,
            mf.buy_sm_amount AS moneyflow_buy_sm_amount,
            CASE WHEN IFNULL(mf.buy_sm_amount, 0) + IFNULL(mf.sell_sm_amount, 0) > 0
                THEN ROUND(mf.buy_sm_amount / (mf.buy_sm_amount + mf.sell_sm_amount) * 100, 2)
                ELSE NULL END AS moneyflow_buy_sm_amount_rate,

            -- 均线（来自预计算临时表）
            ma.ma5, ma.ma10, ma.ma20, ma.ma30, ma.ma60, ma.ma120

        FROM stock_daily_basic db
        LEFT JOIN stock_basic sb    ON db.ts_code = sb.ts_code
        LEFT JOIN stock_daily_history h
            ON db.ts_code = h.ts_code AND db.trade_date = h.trade_date
        LEFT JOIN stock_factor f
            ON db.ts_code = f.ts_code AND db.trade_date = f.trade_date
        LEFT JOIN stock_moneyflow mf
            ON db.ts_code = mf.ts_code AND db.trade_date = mf.trade_date
        LEFT JOIN _tmp_ma ma
            ON db.ts_code = ma.ts_code
        LEFT JOIN _tmp_mf5 mf5
            ON db.ts_code = mf5.ts_code
        WHERE db.trade_date = %(trade_date)s
          AND f.ts_code IS NOT NULL
        ON DUPLICATE KEY UPDATE
            {on_dup_clause}
    """
    return sql


def sync_one_date(conn, trade_date):
    """同步单个交易日数据到 stock_business（INSERT ... ON DUPLICATE KEY UPDATE）。

    流程:
    1. 获取当日活跃股票列表
    2. 预计算 MA 均线（Python 滑动窗口）→ 写入临时表 _tmp_ma
    3. 预计算 5 日净流入 → 写入临时表 _tmp_mf5
    4. 执行 INSERT ... SELECT ... ON DUPLICATE KEY UPDATE
    5. 清理临时表

    Returns:
        int: 受影响行数（INSERT + UPDATE）
    """
    cursor = conn.cursor()

    # 1) 获取当日活跃股票（基于 stock_factor，覆盖最全）
    ts_codes = _collect_active_ts_codes(cursor, trade_date)
    if not ts_codes:
        logger.info('  %s: stock_factor 无数据，跳过', trade_date)
        cursor.close()
        return 0

    logger.info('  %s: %d 只股票，计算 MA / 净流入 ...', trade_date, len(ts_codes))

    # 2) 预计算 MA 均线 → 临时表
    ma_data = prepare_ma_data(cursor, trade_date, ts_codes)
    cursor.execute('DROP TEMPORARY TABLE IF EXISTS _tmp_ma')
    cursor.execute("""
        CREATE TEMPORARY TABLE _tmp_ma (
            ts_code VARCHAR(20) PRIMARY KEY,
            ma5 DECIMAL(10,3), ma10 DECIMAL(10,3), ma20 DECIMAL(10,3),
            ma30 DECIMAL(10,3), ma60 DECIMAL(10,3), ma120 DECIMAL(10,3)
        )
    """)
    if ma_data:
        ma_rows = []
        for code, ma_dict in ma_data.items():
            ma_rows.append((
                code,
                ma_dict.get('ma5'), ma_dict.get('ma10'), ma_dict.get('ma20'),
                ma_dict.get('ma30'), ma_dict.get('ma60'), ma_dict.get('ma120'),
            ))
        cursor.executemany(
            'INSERT INTO _tmp_ma VALUES (%s,%s,%s,%s,%s,%s,%s)', ma_rows
        )

    # 3) 预计算 5 日净流入 → 临时表
    net_d5_data = prepare_net_d5_data(cursor, trade_date, ts_codes)
    cursor.execute('DROP TEMPORARY TABLE IF EXISTS _tmp_mf5')
    cursor.execute("""
        CREATE TEMPORARY TABLE _tmp_mf5 (
            ts_code VARCHAR(20) PRIMARY KEY,
            net_d5_amount DECIMAL(20,2)
        )
    """)
    if net_d5_data:
        mf5_rows = [(code, amt) for code, amt in net_d5_data.items()]
        cursor.executemany(
            'INSERT INTO _tmp_mf5 VALUES (%s, %s)', mf5_rows
        )

    # 4) 构建并执行 INSERT ... SELECT ... ON DUPLICATE KEY UPDATE
    merge_sql = _build_insert_sql()

    cursor.execute(merge_sql, {'trade_date': trade_date})
    affected = cursor.rowcount
    conn.commit()

    # 5) 清理临时表
    cursor.execute('DROP TEMPORARY TABLE IF EXISTS _tmp_ma')
    cursor.execute('DROP TEMPORARY TABLE IF EXISTS _tmp_mf5')
    cursor.close()

    return affected


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='同步 stock_business 宽表数据')
    parser.add_argument('--days', type=int, default=30,
                        help='同步最近 N 个交易日（默认 30）')
    parser.add_argument('--full', action='store_true',
                        help='全量同步所有交易日')
    parser.add_argument('--date', type=str, default=None,
                        help='同步指定日期（格式 YYYYMMDD）')
    args = parser.parse_args()

    logger.info('开始同步 stock_business 宽表 ...')
    conn = _get_db_connection()

    try:
        # 解析日期参数
        specific_date = None
        if args.date:
            try:
                specific_date = datetime.strptime(args.date, '%Y%m%d').date()
            except ValueError:
                logger.error('日期格式错误: %s，请使用 YYYYMMDD 格式', args.date)
                sys.exit(1)

        dates = get_target_dates(conn, days=args.days, full=args.full,
                                 specific_date=specific_date)
        if not dates:
            logger.warning('没有找到需要同步的交易日数据')
            return

        mode = '全量' if args.full else ('指定日期' if specific_date else f'最近{args.days}天')
        logger.info('模式: %s，共 %d 个交易日待同步', mode, len(dates))

        total_rows = 0
        start_time = time.time()

        for i, trade_date in enumerate(dates, 1):
            try:
                count = sync_one_date(conn, trade_date)
                total_rows += count
                elapsed = time.time() - start_time
                avg = elapsed / i
                eta = avg * (len(dates) - i)
                logger.info(
                    '[%d/%d] %s: %d 条 | 累计 %d 条 | 耗时 %.0fs | 预计剩余 %.0fs',
                    i, len(dates), trade_date, count, total_rows, elapsed, eta
                )
            except Exception as e:
                logger.error('[%d/%d] %s: 失败 - %s', i, len(dates), trade_date, e)
                conn.ping(reconnect=True)

        elapsed = time.time() - start_time
        logger.info(
            '同步完成！共 %d 个交易日，%d 条数据，耗时 %.1fs',
            len(dates), total_rows, elapsed
        )

    finally:
        conn.close()


def sync_stock_business(days=None, full=False, specific_date=None):
    """同步 stock_business 宽表（供外部脚本调用）。

    Args:
        days: 同步最近 N 个交易日（默认 30）
        full: 全量同步所有交易日
        specific_date: 同步指定日期（date 对象）

    Returns:
        int: 总写入/更新行数
    """
    conn = _get_db_connection()
    try:
        dates = get_target_dates(conn, days=days, full=full, specific_date=specific_date)
        if not dates:
            logger.warning('没有找到需要同步的交易日数据')
            return 0

        total_rows = 0
        for i, trade_date in enumerate(dates, 1):
            try:
                count = sync_one_date(conn, trade_date)
                total_rows += count
                logger.info('[%d/%d] %s: %d 条', i, len(dates), trade_date, count)
            except Exception as e:
                logger.error('[%d/%d] %s: 失败 - %s', i, len(dates), trade_date, e)
                conn.ping(reconnect=True)

        logger.info('stock_business 同步完成: %d 个交易日, %d 条数据', len(dates), total_rows)
        return total_rows
    finally:
        conn.close()


if __name__ == '__main__':
    main()
