#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日数据自动更新脚本（Crontab 调用）
====================================
每天收盘后(18:00) 自动增量更新数据:
  1. 日线行情 (stock_daily_history)
  2. 复权因子 (stock_factor - adj_factor)
  3. 每日指标 (stock_daily_basic)
  4. 个股资金流向 (stock_moneyflow)
  5. 北向资金 (moneyflow_hsgt)
  6. 技术指标补算 (MACD/KDJ/RSI/BOLL/CCI)

用法:
  python scripts/daily_auto_update.py          # 全量增量更新
  python scripts/daily_auto_update.py --quick   # 仅日线+指标(快)
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import tushare as ts
import pymysql
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True, encoding='utf-8')

# 日志输出到文件
logger.add(
    "logs/daily_update_{time:YYYYMMDD}.log",
    rotation="10 MB", retention="7 days", level="INFO"
)


class DailyAutoUpdater:
    """每日自动更新器"""

    RATE_LIMIT = 0.35

    def __init__(self):
        self.token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
        self.proxy_url = (os.getenv('TUSHARE_PROXY_URL', '') or '').strip()
        self.pro = self._init_pro()
        self.conn, self.cursor = self._init_db()
        self._call_count = 0

    def _init_pro(self):
        if not self.token:
            raise ValueError('TUSHARE_TOKEN 未设置')
        ts.set_token(self.token)
        pro = ts.pro_api()
        if self.proxy_url:
            pro._DataApi__http_url = self.proxy_url
        return pro

    def _init_db(self):
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', 'mysql'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', 'Qs2026Stock123'),
            database=os.getenv('DB_NAME', 'stock_cursor'),
            charset='utf8mb4',
        )
        return conn, conn.cursor()

    def _rate_limit(self):
        self._call_count += 1
        time.sleep(self.RATE_LIMIT)

    def _call_with_retry(self, func, max_retries=5, **kwargs):
        """带重试的API调用"""
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                return func(**kwargs)
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

    def _get_latest_date(self, table, date_col='trade_date'):
        self.cursor.execute(f"SELECT MAX(`{date_col}`) FROM `{table}`")
        result = self.cursor.fetchone()
        if result and result[0]:
            if isinstance(result[0], str):
                return result[0]
            return result[0].strftime('%Y%m%d')
        return None

    def _get_trading_dates(self, start_date, end_date):
        self.cursor.execute("""
            SELECT cal_date FROM stock_trade_calendar
            WHERE is_open=1 AND cal_date >= %s AND cal_date <= %s ORDER BY cal_date
        """, (start_date, end_date))
        return [row[0].strftime('%Y%m%d') if hasattr(row[0], 'strftime') else str(row[0]).replace('-', '') for row in self.cursor.fetchall()]

    def _batch_upsert(self, table, columns, data_tuples, batch_size=5000):
        if not data_tuples:
            return 0
        pk_cols = {'ts_code', 'trade_date'}
        update_cols = [c for c in columns if c not in pk_cols]
        cols_str = ', '.join(f'`{c}`' for c in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        upd_str = ', '.join(f'`{c}`=VALUES(`{c}`)' for c in update_cols) if update_cols else '`ts_code`=VALUES(`ts_code`)'
        sql = f"""INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})
                  ON DUPLICATE KEY UPDATE {upd_str}"""
        inserted = 0
        for i in range(0, len(data_tuples), batch_size):
            batch = data_tuples[i:i + batch_size]
            self.cursor.executemany(sql, batch)
            self.conn.commit()
            inserted += len(batch)
        return inserted

    @staticmethod
    def clean_nan(df):
        return df.replace({np.nan: None}).where(pd.notnull(df), None)

    # ================================================================
    #  同步：日线行情
    # ================================================================
    def sync_daily(self):
        today = datetime.now().strftime('%Y%m%d')
        latest = self._get_latest_date('stock_daily_history')
        start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d') if latest else today
        if start > today:
            logger.info(f'日线行情:已是最新({latest})，跳过')
            return 0

        logger.info(f'[1/5] 同步日线行情 {start} ~ {today}')
        trade_dates = self._get_trading_dates(start, today)
        if not trade_dates:
            logger.info('无需同步的交易日')
            return 0

        total_rows = 0
        for td in trade_dates:
            try:
                df = self._call_with_retry(self.pro.daily, trade_date=td)
                if df is None or df.empty:
                    continue
                df = self.clean_nan(df)
                data = []
                for _, r in df.iterrows():
                    trade_d = datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None
                    data.append((r.get('ts_code'), trade_d, r.get('open'), r.get('high'), r.get('low'),
                                 r.get('close'), r.get('pre_close'), r.get('change'), r.get('pct_chg'),
                                 r.get('vol'), r.get('amount')))
                cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                        'pre_close', 'change_c', 'pct_chg', 'vol', 'amount']
                total_rows += self._batch_upsert('stock_daily_history', cols, data)
                logger.info(f'  {td}: +{len(data)}条')
            except Exception as e:
                logger.error(f'  {td} 错误: {e}')
                self.conn.rollback()
        logger.info(f'日线行情完成: +{total_rows} 条')
        return total_rows

    # ================================================================
    #  同步：复权因子
    # ================================================================
    def sync_adj_factor(self):
        today = datetime.now().strftime('%Y%m%d')
        latest = self._get_latest_date('stock_factor')
        start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d') if latest else today
        if start > today:
            logger.info(f'复权因子:已是最新({latest})，跳过')
            return 0

        logger.info(f'[2/5] 同步复权因子 {start} ~ {today}')
        trade_dates = self._get_trading_dates(start, today)
        total = 0
        for td in trade_dates:
            try:
                df = self._call_with_retry(self.pro.adj_factor, trade_date=td)
                if df is None or df.empty:
                    continue
                df = self.clean_nan(df)
                data = [(r.get('ts_code'), datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None,
                         r.get('adj_factor')) for _, r in df.iterrows()]
                sql = """INSERT INTO stock_factor (ts_code, trade_date, adj_factor) VALUES (%s,%s,%s)
                         ON DUPLICATE KEY UPDATE adj_factor=VALUES(adj_factor)"""
                for i in range(0, len(data), 5000):
                    self.cursor.executemany(sql, data[i:i+5000])
                    self.conn.commit()
                total += len(data)
                logger.info(f'  {td}: +{len(data)}条')
            except Exception as e:
                logger.error(f'  {td} 错误: {e}')
                self.conn.rollback()
        logger.info(f'复权因子完成: +{total} 条')
        return total

    # ================================================================
    #  同步：每日指标
    # ================================================================
    def sync_daily_basic(self):
        today = datetime.now().strftime('%Y%m%d')
        latest = self._get_latest_date('stock_daily_basic')
        start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d') if latest else today
        if start > today:
            logger.info(f'每日指标:已是最新({latest})，跳过')
            return 0

        logger.info(f'[3/5] 同步每日指标 {start} ~ {today}')
        trade_dates = self._get_trading_dates(start, today)
        fields = 'ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv'
        total = 0
        for td in trade_dates:
            try:
                df = self._call_with_retry(self.pro.daily_basic, trade_date=td, fields=fields)
                if df is None or df.empty:
                    continue
                df = self.clean_nan(df)
                data = []
                for _, r in df.iterrows():
                    td2 = datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None
                    data.append((r.get('ts_code'), td2, r.get('close'), r.get('turnover_rate'), r.get('turnover_rate_f'),
                                r.get('volume_ratio'), r.get('pe'), r.get('pe_ttm'), r.get('pb'), r.get('ps'), r.get('ps_ttm'),
                                r.get('dv_ratio'), r.get('dv_ttm'), r.get('total_share'), r.get('float_share'),
                                r.get('free_share'), r.get('total_mv'), r.get('circ_mv')))
                cols = ['ts_code','trade_date','close','turnover_rate','turnover_rate_f','volume_ratio','pe','pe_ttm','pb','ps','ps_ttm','dv_ratio','dv_ttm','total_share','float_share','free_share','total_mv','circ_mv']
                total += self._batch_upsert('stock_daily_basic', cols, data)
                logger.info(f'  {td}: +{len(data)}条')
            except Exception as e:
                logger.error(f'  {td} 错误: {e}')
                self.conn.rollback()
        logger.info(f'每日指标完成: +{total} 条')
        return total

    # ================================================================
    #  同步：资金流向
    # ================================================================
    def sync_moneyflow(self):
        today = datetime.now().strftime('%Y%m%d')
        latest = self._get_latest_date('stock_moneyflow')
        start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d') if latest else today
        if start > today:
            logger.info(f'资金流向:已是最新({latest})，跳过')
            return 0

        logger.info(f'[4/5] 同步资金流向 {start} ~ {today}')
        trade_dates = self._get_trading_dates(start, today)
        cols = ['ts_code','trade_date','buy_sm_vol','buy_sm_amount','sell_sm_vol','sell_sm_amount',
                'buy_md_vol','buy_md_amount','sell_md_vol','sell_md_amount','buy_lg_vol','buy_lg_amount',
                'sell_lg_vol','sell_lg_amount','buy_elg_vol','buy_elg_amount','sell_elg_vol','sell_elg_amount',
                'net_mf_vol','net_mf_amount']
        total = 0
        for td in trade_dates:
            try:
                df = self._call_with_retry(self.pro.moneyflow, trade_date=td)
                if df is None or df.empty:
                    continue
                df = self.clean_nan(df)
                data = []
                for _, r in df.iterrows():
                    td2 = datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None
                    data.append((r.get('ts_code'), td2, r.get('buy_sm_vol'), r.get('buy_sm_amount'), r.get('sell_sm_vol'), r.get('sell_sm_amount'),
                                r.get('buy_md_vol'), r.get('buy_md_amount'), r.get('sell_md_vol'), r.get('sell_md_amount'),
                                r.get('buy_lg_vol'), r.get('buy_lg_amount'), r.get('sell_lg_vol'), r.get('sell_lg_amount'),
                                r.get('buy_elg_vol'), r.get('buy_elg_amount'), r.get('sell_elg_vol'), r.get('sell_elg_amount'),
                                r.get('net_mf_vol'), r.get('net_mf_amount')))
                total += self._batch_upsert('stock_moneyflow', cols, data)
                logger.info(f'  {td}: +{len(data)}条')
            except Exception as e:
                logger.error(f'  {td} 错误: {e}')
                self.conn.rollback()
        logger.info(f'资金流向完成: +{total} 条')
        return total

    # ================================================================
    #  同步：北向资金
    # ================================================================
    def sync_hsgt(self):
        today = datetime.now().strftime('%Y%m%d')
        latest = self._get_latest_date('moneyflow_hsgt')
        start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d') if latest else today
        if start > today:
            logger.info(f'北向资金:已是最新({latest})，跳过')
            return 0

        logger.info(f'[5/5] 同步北向资金 {start} ~ {today}')
        df = self._call_with_retry(self.pro.moneyflow_hsgt, start_date=start, end_date=today)
        if df is None or df.empty:
            logger.info('无新数据')
            return 0
        df = self.clean_nan(df)
        cols = ['trade_date', 'ggt_ss', 'ggt_sz', 'hgt', 'sgt', 'north_money', 'south_money']
        data = []
        for _, r in df.iterrows():
            td = datetime.strptime(str(r['trade_date']), '%Y%m%d').date() if r.get('trade_date') else None
            data.append((td, r.get('ggt_ss'), r.get('ggt_sz'), r.get('hgt'), r.get('sgt'), r.get('north_money'), r.get('south_money')))
        inserted = self._batch_upsert('moneyflow_hsgt', cols, data)
        logger.info(f'北向资金完成: +{inserted} 条')
        return inserted

    # ================================================================
    #  补算技术指标
    # ================================================================
    def recalc_factors(self):
        """补算最近N天技术指标"""
        from scripts.backfill_factors_v2 import get_db_connection, get_stock_list, process_stock

        logger.info('[补算] 开始补算技术指标...')
        conn2 = get_db_connection()
        try:
            stock_list = get_stock_list(conn2)
            # 只处理近5天的数据（增量补算）
            start = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
            total = 0
            for i, ts_code in enumerate(stock_list, 1):
                inserted, skipped, err = process_stock(conn2, ts_code, start_date=start, end_date=None, force=True, dry_run=False, batch_size=3000)
                total += inserted
                if i % 1000 == 0:
                    logger.info(f'  补算进度: {i}/{len(stock_list)}, 新增{total}条')
            logger.info(f'技术指标补算完成: +{total} 条')
            return total
        finally:
            conn2.close()

    # ================================================================
    #  全量运行
    # ================================================================
    def run_all(self, quick=False):
        """执行全部更新"""
        t_start = time.time()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        logger.info('=' * 60)
        logger.info(f'  每日自动数据更新开始 | {now}')
        logger.info('=' * 60)

        results = {}
        results['daily'] = self.sync_daily()
        results['adj'] = self.sync_adj_factor()

        if not quick:
            results['basic'] = self.sync_daily_basic()
            results['moneyflow'] = self.sync_moneyflow()
            results['hsgt'] = self.sync_hsgt()

        # 总是补算技术指标
        results['factors'] = self.recalc_factors()

        elapsed = time.time() - t_start
        logger.info('=' * 60)
        logger.info(f'  更新完成! 耗时 {elapsed:.0f}s | API调用 {self._call_count}次')
        logger.info(f'  结果: {results}')
        logger.info('=' * 60)
        return results

    def close(self):
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='每日数据自动更新')
    parser.add_argument('--quick', action='store_true', help='快速模式: 仅日线+复权+指标(约2分钟)')
    args = parser.parse_args()

    updater = DailyAutoUpdater()
    try:
        updater.run_all(quick=args.quick)
    finally:
        updater.close()


if __name__ == '__main__':
    main()
