#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare 数据同步工具
===================
使用 Tushare Pro API 批量同步股票数据到 MySQL 数据库（增量模式）

支持的数据类型:
  basic          - 股票基础信息（全量替换）
  calendar       - 交易日历（全量替换）
  daily          - 日线行情（增量按日期）
  adj_factor     - 复权因子（增量按日期，写入 stock_factor 表）
  daily_basic    - 每日指标 PE/PB/换手率等（增量按日期）
  moneyflow      - 个股资金流向（增量按日期）
  moneyflow_hsgt - 沪深港通北向资金（增量按日期）
  all            - 依次同步以上所有类型

使用方式:
  # 首次全量同步（10年数据）
  python scripts/sync_tushare_data.py --type all --start 20160101

  # 仅同步日线行情
  python scripts/sync_tushare_data.py --type daily --start 20160101

  # 增量同步（自动从数据库最新日期开始）
  python scripts/sync_tushare_data.py --type daily

  # 先跑前10只股票测试
  python scripts/sync_tushare_data.py --type daily --start 20260101 --end 20260110

注意事项:
  - 请求频率约 180次/分钟，脚本内置 0.35s 间隔
  - 首次全量同步约需 2~4 小时，建议挂后台运行
  - 每日增量只需 3~5 次调用，秒级完成
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
import tushare as ts
from dotenv import load_dotenv

def _clean_nan(df):
    """彻底清理DataFrame中的NaN/None，确保MySQL兼容"""
    return df.replace({np.nan: None}).where(pd.notnull(df), None)

load_dotenv(override=True, encoding='utf-8')


class TushareDataSync:
    """Tushare 数据同步器"""

    # 请求频率限制：180次/分钟 → 每次间隔 0.35s（留余量）
    RATE_LIMIT_INTERVAL = 0.35

    def __init__(self):
        self.token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
        self.proxy_url = (os.getenv('TUSHARE_PROXY_URL', 'http://tsy.xiaodefa.cn') or '').strip()
        self.pro = self._init_pro()
        self.conn, self.cursor = self._init_db()
        self._call_count = 0
        self._start_time = time.time()

    def _init_pro(self):
        """初始化 Tushare Pro API（常规接口）"""
        if not self.token:
            raise ValueError('TUSHARE_TOKEN 未设置，请检查 .env 文件')

        ts.set_token(self.token)
        pro = ts.pro_api()
        if self.proxy_url:
            pro._DataApi__http_url = self.proxy_url
        return pro

    def _init_db(self):
        """初始化 MySQL 连接"""
        import pymysql
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', 'root'),
            database=os.getenv('DB_NAME', 'stock_cursor'),
            charset=os.getenv('DB_CHARSET', 'utf8mb4'),
        )
        cursor = conn.cursor()
        return conn, cursor

    def _rate_limit(self):
        """请求频率限制"""
        self._call_count += 1
        time.sleep(self.RATE_LIMIT_INTERVAL)

    def _print_progress(self, current, total, prefix=''):
        """打印进度"""
        pct = current / total * 100 if total > 0 else 0
        bar_len = 30
        filled = int(bar_len * current / total) if total > 0 else 0
        bar = '=' * filled + '>' * (1 if filled < bar_len else 0) + '.' * max(bar_len - filled - 1, 0)
        elapsed = time.time() - self._start_time
        rate = self._call_count / (elapsed / 60) if elapsed > 0 else 0
        msg = f"\r  [{bar}] {current}/{total} ({pct:.1f}%) | API调用: {self._call_count}次 ({rate:.0f}次/分)"
        if prefix:
            msg = f"  {prefix} " + msg
        print(msg, end='', flush=True)

    def _batch_upsert(self, table, columns, data_tuples, batch_size=5000):
        """批量写入数据库（INSERT ... ON DUPLICATE KEY UPDATE）"""
        if not data_tuples:
            return 0

        pk_cols = {'ts_code', 'trade_date', 'cal_date', 'exchange'}
        update_cols = [c for c in columns if c not in pk_cols]
        columns_str = ', '.join(f'`{c}`' for c in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        update_str = ', '.join(f'`{c}`=VALUES(`{c}`)' for c in update_cols) if update_cols else '`ts_code`=VALUES(`ts_code`)'

        sql = f"""INSERT INTO `{table}` ({columns_str}) VALUES ({placeholders})
                  ON DUPLICATE KEY UPDATE {update_str}"""

        inserted = 0
        for i in range(0, len(data_tuples), batch_size):
            batch = data_tuples[i:i + batch_size]
            self.cursor.executemany(sql, batch)
            self.conn.commit()
            inserted += len(batch)
        return inserted

    def _get_trading_dates(self, start_date, end_date):
        """从交易日历获取交易日期列表"""
        start_fmt = start_date if isinstance(start_date, str) and len(start_date) == 8 else start_date
        end_fmt = end_date if isinstance(end_date, str) and len(end_date) == 8 else end_date

        self.cursor.execute("""
            SELECT DATE_FORMAT(cal_date, '%%Y%%m%%d') FROM stock_trade_calendar
            WHERE is_open = 1 AND cal_date >= %s AND cal_date <= %s
            ORDER BY cal_date
        """, (start_fmt, end_fmt))
        return [row[0] for row in self.cursor.fetchall()]

    def _get_latest_date(self, table, date_col='trade_date'):
        """获取表中最新交易日期"""
        self.cursor.execute(f"SELECT MAX(`{date_col}`) FROM `{table}`")
        result = self.cursor.fetchone()
        if result and result[0]:
            if isinstance(result[0], str):
                return result[0]
            return result[0].strftime('%Y%m%d')
        return None

    # ================================================================
    #  同步：股票基础信息
    # ================================================================
    def sync_stock_basic(self):
        """同步股票基础信息（全量替换）"""
        print("\n" + "=" * 60)
        print("  同步股票基础信息 (stock_basic)")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_basic` (
                  `ts_code` varchar(20) NOT NULL COMMENT 'TS代码',
                  `symbol` varchar(20) DEFAULT NULL COMMENT '股票代码',
                  `name` varchar(100) DEFAULT NULL COMMENT '股票名称',
                  `area` varchar(100) DEFAULT NULL COMMENT '地域',
                  `industry` varchar(100) DEFAULT NULL COMMENT '所属行业',
                  `list_date` date DEFAULT NULL COMMENT '上市日期',
                  PRIMARY KEY (`ts_code`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            self._rate_limit()
            df = self.pro.stock_basic(exchange='', list_status='L',
                                      fields='ts_code,symbol,name,area,industry,list_date')

            if df is None or df.empty:
                print("  未获取到数据")
                return

            df = _clean_nan(df)
            data = []
            for _, row in df.iterrows():
                list_date = None
                if row.get('list_date') and str(row['list_date']) != 'None':
                    try:
                        list_date = datetime.strptime(str(row['list_date']), '%Y%m%d').date()
                    except (ValueError, TypeError):
                        pass
                data.append((
                    row.get('ts_code'),
                    row.get('symbol'),
                    row.get('name'),
                    row.get('area'),
                    row.get('industry'),
                    list_date,
                ))

            self.cursor.execute("TRUNCATE TABLE stock_basic")
            self.conn.commit()

            columns = ['ts_code', 'symbol', 'name', 'area', 'industry', 'list_date']
            inserted = self._batch_upsert('stock_basic', columns, data)
            print(f"\n  完成！共写入 {inserted} 条股票基础信息")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：交易日历
    # ================================================================
    def sync_trade_calendar(self, start_date='20150101', end_date=None):
        """同步交易日历（全量替换）"""
        if not end_date:
            end_date = (datetime.now() + timedelta(days=365)).strftime('%Y%m%d')

        print("\n" + "=" * 60)
        print(f"  同步交易日历 (trade_calendar) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_trade_calendar` (
                  `exchange` varchar(20) NOT NULL COMMENT '交易所',
                  `cal_date` date NOT NULL COMMENT '日历日期',
                  `is_open` int DEFAULT NULL COMMENT '是否交易日',
                  `pretrade_date` date DEFAULT NULL COMMENT '上一交易日',
                  PRIMARY KEY (`exchange`,`cal_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            self._rate_limit()
            df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)

            if df is None or df.empty:
                print("  未获取到数据")
                return

            df = _clean_nan(df)
            data = []
            for _, row in df.iterrows():
                cal_date = datetime.strptime(str(row['cal_date']), '%Y%m%d').date() if row.get('cal_date') else None
                pretrade_date = None
                if row.get('pretrade_date') and str(row['pretrade_date']) != 'None':
                    try:
                        pretrade_date = datetime.strptime(str(row['pretrade_date']), '%Y%m%d').date()
                    except (ValueError, TypeError):
                        pass
                data.append((row.get('exchange'), cal_date, row.get('is_open'), pretrade_date))

            self.cursor.execute("TRUNCATE TABLE stock_trade_calendar")
            self.conn.commit()

            columns = ['exchange', 'cal_date', 'is_open', 'pretrade_date']
            inserted = self._batch_upsert('stock_trade_calendar', columns, data)
            print(f"\n  完成！共写入 {inserted} 条交易日历")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：日线行情
    # ================================================================
    def sync_daily_history(self, start_date=None, end_date=None):
        """同步日线行情（增量按日期）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        # 增量：从数据库最新日期的下一天开始
        if not start_date:
            latest = self._get_latest_date('stock_daily_history')
            if latest:
                next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                start_date = next_day
                print(f"\n  增量模式：从 {start_date} 开始（数据库已有至 {latest}）")
            else:
                start_date = '20160101'
                print(f"\n  全量模式：从 {start_date} 开始")

        print("\n" + "=" * 60)
        print(f"  同步日线行情 (stock_daily_history) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_daily_history` (
                  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
                  `trade_date` date NOT NULL COMMENT '交易日期',
                  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘价',
                  `high` decimal(10,4) DEFAULT NULL COMMENT '最高价',
                  `low` decimal(10,4) DEFAULT NULL COMMENT '最低价',
                  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘价',
                  `pre_close` decimal(10,4) DEFAULT NULL COMMENT '昨收价',
                  `change_c` decimal(10,4) DEFAULT NULL COMMENT '涨跌额',
                  `pct_chg` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅',
                  `vol` bigint DEFAULT NULL COMMENT '成交量（手）',
                  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额（千元）',
                  PRIMARY KEY (`ts_code`,`trade_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            trade_dates = self._get_trading_dates(start_date, end_date)
            if not trade_dates:
                print("  无需同步的交易日")
                return

            total = len(trade_dates)
            total_rows = 0
            columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                        'pre_close', 'change_c', 'pct_chg', 'vol', 'amount']

            self._start_time = time.time()
            for idx, trade_date in enumerate(trade_dates, 1):
                try:
                    self._rate_limit()
                    df = self.pro.daily(trade_date=trade_date)

                    if df is None or df.empty:
                        self._print_progress(idx, total, f'日期{trade_date}: 无数据')
                        continue

                    df = _clean_nan(df)
                    data = []
                    for _, row in df.iterrows():
                        td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                        data.append((
                            row.get('ts_code'), td,
                            row.get('open'), row.get('high'), row.get('low'),
                            row.get('close'), row.get('pre_close'),
                            row.get('change'),   # Tushare 'change' → DB 'change_c'
                            row.get('pct_chg'), row.get('vol'), row.get('amount'),
                        ))

                    inserted = self._batch_upsert('stock_daily_history', columns, data)
                    total_rows += inserted
                    self._print_progress(idx, total, f'{trade_date}: +{len(data)}条')

                except Exception as e:
                    print(f"\n  日期 {trade_date} 错误: {e}")
                    self.conn.rollback()
                    continue

            elapsed = time.time() - self._start_time
            print(f"\n\n  完成！共写入 {total_rows} 条日线数据，耗时 {elapsed:.0f}s，API调用 {self._call_count}次")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：复权因子
    # ================================================================
    def sync_adj_factor(self, start_date=None, end_date=None):
        """同步复权因子（增量按日期，写入 stock_factor 表）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if not start_date:
            latest = self._get_latest_date('stock_factor')
            if latest:
                next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                start_date = next_day
            else:
                start_date = '20160101'

        print("\n" + "=" * 60)
        print(f"  同步复权因子 (adj_factor → stock_factor) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            # 确保 stock_factor 表存在
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_factor` (
                  `ts_code` varchar(20) NOT NULL,
                  `trade_date` date NOT NULL,
                  `close` decimal(10,2) DEFAULT NULL,
                  `open` decimal(10,2) DEFAULT NULL,
                  `high` decimal(10,2) DEFAULT NULL,
                  `low` decimal(10,2) DEFAULT NULL,
                  `pre_close` decimal(10,2) DEFAULT NULL,
                  `change` decimal(10,2) DEFAULT NULL,
                  `pct_change` decimal(10,2) DEFAULT NULL,
                  `vol` decimal(20,2) DEFAULT NULL,
                  `amount` decimal(20,2) DEFAULT NULL,
                  `adj_factor` decimal(10,6) DEFAULT NULL COMMENT '复权因子',
                  `open_hfq` decimal(10,2) DEFAULT NULL,
                  `open_qfq` decimal(10,2) DEFAULT NULL,
                  `close_hfq` decimal(10,2) DEFAULT NULL,
                  `close_qfq` decimal(10,2) DEFAULT NULL,
                  `high_hfq` decimal(10,2) DEFAULT NULL,
                  `high_qfq` decimal(10,2) DEFAULT NULL,
                  `low_hfq` decimal(10,2) DEFAULT NULL,
                  `low_qfq` decimal(10,2) DEFAULT NULL,
                  `pre_close_hfq` decimal(10,2) DEFAULT NULL,
                  `pre_close_qfq` decimal(10,2) DEFAULT NULL,
                  `macd_dif` decimal(10,2) DEFAULT NULL,
                  `macd_dea` decimal(10,2) DEFAULT NULL,
                  `macd` decimal(10,2) DEFAULT NULL,
                  `kdj_k` decimal(10,2) DEFAULT NULL,
                  `kdj_d` decimal(10,2) DEFAULT NULL,
                  `kdj_j` decimal(10,2) DEFAULT NULL,
                  `rsi_6` decimal(10,2) DEFAULT NULL,
                  `rsi_12` decimal(10,2) DEFAULT NULL,
                  `rsi_24` decimal(10,2) DEFAULT NULL,
                  `boll_upper` decimal(10,2) DEFAULT NULL,
                  `boll_mid` decimal(10,2) DEFAULT NULL,
                  `boll_lower` decimal(10,2) DEFAULT NULL,
                  `cci` decimal(10,2) DEFAULT NULL,
                  PRIMARY KEY (`ts_code`,`trade_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            trade_dates = self._get_trading_dates(start_date, end_date)
            if not trade_dates:
                print("  无需同步的交易日")
                return

            total = len(trade_dates)
            total_rows = 0

            self._start_time = time.time()
            for idx, trade_date in enumerate(trade_dates, 1):
                try:
                    self._rate_limit()
                    df = self.pro.adj_factor(trade_date=trade_date)

                    if df is None or df.empty:
                        self._print_progress(idx, total, f'{trade_date}: 无数据')
                        continue

                    df = _clean_nan(df)
                    data = []
                    for _, row in df.iterrows():
                        td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                        data.append((row.get('ts_code'), td, row.get('adj_factor')))

                    # 仅更新 adj_factor 列
                    sql = """INSERT INTO `stock_factor` (`ts_code`, `trade_date`, `adj_factor`)
                             VALUES (%s, %s, %s)
                             ON DUPLICATE KEY UPDATE `adj_factor`=VALUES(`adj_factor`)"""
                    for i in range(0, len(data), 5000):
                        batch = data[i:i + 5000]
                        self.cursor.executemany(sql, batch)
                        self.conn.commit()

                    total_rows += len(data)
                    self._print_progress(idx, total, f'{trade_date}: +{len(data)}条')

                except Exception as e:
                    print(f"\n  日期 {trade_date} 错误: {e}")
                    self.conn.rollback()
                    continue

            elapsed = time.time() - self._start_time
            print(f"\n\n  完成！共写入 {total_rows} 条复权因子，耗时 {elapsed:.0f}s")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：每日指标
    # ================================================================
    def sync_daily_basic(self, start_date=None, end_date=None):
        """同步每日指标 PE/PB/换手率等（增量按日期）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if not start_date:
            latest = self._get_latest_date('stock_daily_basic')
            if latest:
                next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                start_date = next_day
            else:
                start_date = '20160101'

        print("\n" + "=" * 60)
        print(f"  同步每日指标 (stock_daily_basic) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_daily_basic` (
                  `ts_code` varchar(20) NOT NULL,
                  `trade_date` date NOT NULL,
                  `close` decimal(10,2) DEFAULT NULL,
                  `turnover_rate` decimal(10,4) DEFAULT NULL,
                  `turnover_rate_f` decimal(10,4) DEFAULT NULL,
                  `volume_ratio` decimal(10,4) DEFAULT NULL,
                  `pe` decimal(10,4) DEFAULT NULL,
                  `pe_ttm` decimal(10,4) DEFAULT NULL,
                  `pb` decimal(10,4) DEFAULT NULL,
                  `ps` decimal(10,4) DEFAULT NULL,
                  `ps_ttm` decimal(10,4) DEFAULT NULL,
                  `dv_ratio` decimal(10,4) DEFAULT NULL,
                  `dv_ttm` decimal(10,4) DEFAULT NULL,
                  `total_share` decimal(20,4) DEFAULT NULL,
                  `float_share` decimal(20,4) DEFAULT NULL,
                  `free_share` decimal(20,4) DEFAULT NULL,
                  `total_mv` decimal(20,4) DEFAULT NULL,
                  `circ_mv` decimal(20,4) DEFAULT NULL,
                  PRIMARY KEY (`ts_code`,`trade_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            trade_dates = self._get_trading_dates(start_date, end_date)
            if not trade_dates:
                print("  无需同步的交易日")
                return

            total = len(trade_dates)
            total_rows = 0
            columns = ['ts_code', 'trade_date', 'close', 'turnover_rate', 'turnover_rate_f',
                        'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
                        'dv_ratio', 'dv_ttm', 'total_share', 'float_share',
                        'free_share', 'total_mv', 'circ_mv']

            self._start_time = time.time()
            for idx, trade_date in enumerate(trade_dates, 1):
                try:
                    self._rate_limit()
                    df = self.pro.daily_basic(trade_date=trade_date,
                                              fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv')

                    if df is None or df.empty:
                        self._print_progress(idx, total, f'{trade_date}: 无数据')
                        continue

                    df = _clean_nan(df)
                    data = []
                    for _, row in df.iterrows():
                        td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                        data.append((
                            row.get('ts_code'), td,
                            row.get('close'), row.get('turnover_rate'), row.get('turnover_rate_f'),
                            row.get('volume_ratio'), row.get('pe'), row.get('pe_ttm'),
                            row.get('pb'), row.get('ps'), row.get('ps_ttm'),
                            row.get('dv_ratio'), row.get('dv_ttm'),
                            row.get('total_share'), row.get('float_share'),
                            row.get('free_share'), row.get('total_mv'), row.get('circ_mv'),
                        ))

                    inserted = self._batch_upsert('stock_daily_basic', columns, data)
                    total_rows += inserted
                    self._print_progress(idx, total, f'{trade_date}: +{len(data)}条')

                except Exception as e:
                    print(f"\n  日期 {trade_date} 错误: {e}")
                    self.conn.rollback()
                    continue

            elapsed = time.time() - self._start_time
            print(f"\n\n  完成！共写入 {total_rows} 条每日指标，耗时 {elapsed:.0f}s")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：个股资金流向
    # ================================================================
    def sync_moneyflow(self, start_date=None, end_date=None):
        """同步个股资金流向（增量按日期）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if not start_date:
            latest = self._get_latest_date('stock_moneyflow')
            if latest:
                next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                start_date = next_day
            else:
                start_date = '20160101'

        print("\n" + "=" * 60)
        print(f"  同步个股资金流向 (stock_moneyflow) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_moneyflow` (
                  `ts_code` varchar(20) NOT NULL,
                  `trade_date` date NOT NULL,
                  `buy_sm_vol` bigint DEFAULT NULL COMMENT '小单买入量',
                  `buy_sm_amount` decimal(20,4) DEFAULT NULL COMMENT '小单买入金额',
                  `sell_sm_vol` bigint DEFAULT NULL COMMENT '小单卖出量',
                  `sell_sm_amount` decimal(20,4) DEFAULT NULL COMMENT '小单卖出金额',
                  `buy_md_vol` bigint DEFAULT NULL COMMENT '中单买入量',
                  `buy_md_amount` decimal(20,4) DEFAULT NULL COMMENT '中单买入金额',
                  `sell_md_vol` bigint DEFAULT NULL COMMENT '中单卖出量',
                  `sell_md_amount` decimal(20,4) DEFAULT NULL COMMENT '中单卖出金额',
                  `buy_lg_vol` bigint DEFAULT NULL COMMENT '大单买入量',
                  `buy_lg_amount` decimal(20,4) DEFAULT NULL COMMENT '大单买入金额',
                  `sell_lg_vol` bigint DEFAULT NULL COMMENT '大单卖出量',
                  `sell_lg_amount` decimal(20,4) DEFAULT NULL COMMENT '大单卖出金额',
                  `buy_elg_vol` bigint DEFAULT NULL COMMENT '特大单买入量',
                  `buy_elg_amount` decimal(20,4) DEFAULT NULL COMMENT '特大单买入金额',
                  `sell_elg_vol` bigint DEFAULT NULL COMMENT '特大单卖出量',
                  `sell_elg_amount` decimal(20,4) DEFAULT NULL COMMENT '特大单卖出金额',
                  `net_mf_vol` bigint DEFAULT NULL COMMENT '净流入量',
                  `net_mf_amount` decimal(20,4) DEFAULT NULL COMMENT '净流入额',
                  PRIMARY KEY (`ts_code`,`trade_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            trade_dates = self._get_trading_dates(start_date, end_date)
            if not trade_dates:
                print("  无需同步的交易日")
                return

            total = len(trade_dates)
            total_rows = 0
            columns = ['ts_code', 'trade_date', 'buy_sm_vol', 'buy_sm_amount',
                        'sell_sm_vol', 'sell_sm_amount', 'buy_md_vol', 'buy_md_amount',
                        'sell_md_vol', 'sell_md_amount', 'buy_lg_vol', 'buy_lg_amount',
                        'sell_lg_vol', 'sell_lg_amount', 'buy_elg_vol', 'buy_elg_amount',
                        'sell_elg_vol', 'sell_elg_amount', 'net_mf_vol', 'net_mf_amount']

            self._start_time = time.time()
            for idx, trade_date in enumerate(trade_dates, 1):
                try:
                    self._rate_limit()
                    df = self.pro.moneyflow(trade_date=trade_date)

                    if df is None or df.empty:
                        self._print_progress(idx, total, f'{trade_date}: 无数据')
                        continue

                    df = _clean_nan(df)
                    data = []
                    for _, row in df.iterrows():
                        td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                        data.append((
                            row.get('ts_code'), td,
                            row.get('buy_sm_vol'), row.get('buy_sm_amount'),
                            row.get('sell_sm_vol'), row.get('sell_sm_amount'),
                            row.get('buy_md_vol'), row.get('buy_md_amount'),
                            row.get('sell_md_vol'), row.get('sell_md_amount'),
                            row.get('buy_lg_vol'), row.get('buy_lg_amount'),
                            row.get('sell_lg_vol'), row.get('sell_lg_amount'),
                            row.get('buy_elg_vol'), row.get('buy_elg_amount'),
                            row.get('sell_elg_vol'), row.get('sell_elg_amount'),
                            row.get('net_mf_vol'), row.get('net_mf_amount'),
                        ))

                    inserted = self._batch_upsert('stock_moneyflow', columns, data)
                    total_rows += inserted
                    self._print_progress(idx, total, f'{trade_date}: +{len(data)}条')

                except Exception as e:
                    print(f"\n  日期 {trade_date} 错误: {e}")
                    self.conn.rollback()
                    continue

            elapsed = time.time() - self._start_time
            print(f"\n\n  完成！共写入 {total_rows} 条资金流向，耗时 {elapsed:.0f}s")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步：沪深港通资金流向（15000积分接口）
    # ================================================================
    def sync_moneyflow_hsgt(self, start_date=None, end_date=None):
        """同步沪深港通北向资金（增量）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        if not start_date:
            latest = self._get_latest_date('moneyflow_hsgt')
            if latest:
                next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                start_date = next_day
            else:
                start_date = '20160101'

        print("\n" + "=" * 60)
        print(f"  同步沪深港通资金流向 (moneyflow_hsgt) {start_date} ~ {end_date}")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `moneyflow_hsgt` (
                  `trade_date` date NOT NULL,
                  `ggt_ss` decimal(20,4) DEFAULT NULL COMMENT '港股通（沪）',
                  `ggt_sz` decimal(20,4) DEFAULT NULL COMMENT '港股通（深）',
                  `hgt` decimal(20,4) DEFAULT NULL COMMENT '沪股通',
                  `sgt` decimal(20,4) DEFAULT NULL COMMENT '深股通',
                  `north_money` decimal(20,4) DEFAULT NULL COMMENT '北向资金',
                  `south_money` decimal(20,4) DEFAULT NULL COMMENT '南向资金',
                  PRIMARY KEY (`trade_date`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            # moneyflow_hsgt 支持按日期范围一次拉取
            self._rate_limit()
            df = self.pro.moneyflow_hsgt(start_date=start_date, end_date=end_date)

            if df is None or df.empty:
                print("  未获取到数据")
                return

            df = _clean_nan(df)
            columns = ['trade_date', 'ggt_ss', 'ggt_sz', 'hgt', 'sgt', 'north_money', 'south_money']
            data = []
            for _, row in df.iterrows():
                td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                data.append((
                    td,
                    row.get('ggt_ss'), row.get('ggt_sz'),
                    row.get('hgt'), row.get('sgt'),
                    row.get('north_money'), row.get('south_money'),
                ))

            inserted = self._batch_upsert('moneyflow_hsgt', columns, data)
            print(f"  完成！共写入 {inserted} 条沪深港通资金数据")

        except Exception as e:
            self.conn.rollback()
            print(f"  错误: {e}")

    # ================================================================
    #  同步：每日筹码分布
    # ================================================================
    def sync_cyq_chips(self, start_date=None, end_date=None, stock_list=None):
        """同步每日筹码分布（cyq_chips，增量按股票代码+日期）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        # 获取股票列表
        if not stock_list:
            self.cursor.execute("SELECT ts_code FROM stock_basic WHERE ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ' ORDER BY ts_code")
            stock_list = [row[0] for row in self.cursor.fetchall()]

        total_stocks = len(stock_list)
        total_rows = 0
        columns = ['ts_code', 'trade_date', 'price', 'percent']

        print("\n" + "=" * 60)
        print(f"  同步每日筹码分布 (stock_cyq_chips) {start_date or '增量'} ~ {end_date}")
        print(f"  共 {total_stocks} 只股票")
        print("=" * 60)

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `stock_cyq_chips` (
                  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
                  `trade_date` date NOT NULL COMMENT '交易日期',
                  `price` decimal(10,2) NOT NULL COMMENT '成本价格',
                  `percent` decimal(10,4) DEFAULT NULL COMMENT '价格占比（%）',
                  PRIMARY KEY (`ts_code`,`trade_date`,`price`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            self.conn.commit()

            self._start_time = time.time()
            for idx, ts_code in enumerate(stock_list, 1):
                try:
                    # 增量：查询该股票最新日期
                    if not start_date:
                        self.cursor.execute(
                            "SELECT MAX(trade_date) FROM stock_cyq_chips WHERE ts_code = %s", (ts_code,))
                        result = self.cursor.fetchone()
                        if result and result[0]:
                            if isinstance(result[0], str):
                                latest = result[0]
                            else:
                                latest = result[0].strftime('%Y%m%d')
                            next_day = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                            sd = next_day
                        else:
                            sd = '20180101'
                    else:
                        sd = start_date

                    if sd > end_date:
                        self._print_progress(idx, total_stocks, f'{ts_code}: 已是最新')
                        continue

                    # 按日期分段拉取，每次最多覆盖一段时间（单次最多2000条）
                    current_start = sd
                    while current_start <= end_date:
                        # 每次最多拉3个月的量，避免超过2000条限制
                        current_end_dt = datetime.strptime(current_start, '%Y%m%d') + timedelta(days=90)
                        current_end = min(end_date, current_end_dt.strftime('%Y%m%d'))

                        self._rate_limit()
                        df = self.pro.cyq_chips(ts_code=ts_code,
                                                start_date=current_start,
                                                end_date=current_end)

                        if df is not None and not df.empty:
                            df = _clean_nan(df)
                            data = []
                            for _, row in df.iterrows():
                                td = datetime.strptime(str(row['trade_date']), '%Y%m%d').date() if row.get('trade_date') else None
                                data.append((
                                    row.get('ts_code'), td,
                                    row.get('price'), row.get('percent'),
                                ))
                            inserted = self._batch_upsert('stock_cyq_chips', columns, data, batch_size=2000)
                            total_rows += inserted

                        current_start = (current_end_dt + timedelta(days=1)).strftime('%Y%m%d')

                    self._print_progress(idx, total_stocks, f'{ts_code}')

                except Exception as e:
                    print(f"\n  {ts_code} 错误: {e}")
                    self.conn.rollback()
                    continue

            elapsed = time.time() - self._start_time
            print(f"\n\n  完成！共写入 {total_rows} 条筹码分布数据，耗时 {elapsed:.0f}s，API调用 {self._call_count}次")

        except Exception as e:
            self.conn.rollback()
            print(f"\n  错误: {e}")

    # ================================================================
    #  同步所有
    # ================================================================
    def sync_all(self, start_date=None, end_date=None):
        """依次同步所有数据"""
        print("\n" + "=" * 60)
        print("  全量数据同步")
        print(f"  日期范围: {start_date or '自动增量'} ~ {end_date or '今天'}")
        print("=" * 60)

        # 基础数据（无日期依赖）
        self.sync_stock_basic()
        self.sync_trade_calendar(start_date='20150101', end_date=end_date or (datetime.now() + timedelta(days=365)).strftime('%Y%m%d'))

        # 行情数据（增量）
        self.sync_daily_history(start_date=start_date, end_date=end_date)
        self.sync_adj_factor(start_date=start_date, end_date=end_date)
        self.sync_daily_basic(start_date=start_date, end_date=end_date)

        # 资金数据（增量）
        self.sync_moneyflow(start_date=start_date, end_date=end_date)
        self.sync_moneyflow_hsgt(start_date=start_date, end_date=end_date)

        # 筹码分布（增量）
        self.sync_cyq_chips(start_date=start_date, end_date=end_date)

        print("\n" + "=" * 60)
        print("  全量同步完成！")
        print("  下一步：运行 python scripts/backfill_factors.py 补算技术指标")
        print("=" * 60)

    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Tushare 数据同步工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 首次全量同步（10年数据）
  python scripts/sync_tushare_data.py --type all --start 20160101

  # 仅同步日线行情
  python scripts/sync_tushare_data.py --type daily --start 20160101

  # 增量同步（自动从数据库最新日期开始）
  python scripts/sync_tushare_data.py --type daily

  # 测试：同步几天的数据
  python scripts/sync_tushare_data.py --type daily --start 20260101 --end 20260110
        """,
    )
    parser.add_argument('--type', required=True,
                        choices=['basic', 'calendar', 'daily', 'adj_factor',
                                 'daily_basic', 'moneyflow', 'moneyflow_hsgt',
                                 'cyq_chips', 'all'],
                        help='同步的数据类型')
    parser.add_argument('--start', default=None,
                        help='起始日期 YYYYMMDD（不指定则自动增量）')
    parser.add_argument('--end', default=None,
                        help='结束日期 YYYYMMDD（不指定则到今天）')

    args = parser.parse_args()

    sync = TushareDataSync()
    try:
        type_map = {
            'basic': sync.sync_stock_basic,
            'calendar': sync.sync_trade_calendar,
            'daily': sync.sync_daily_history,
            'adj_factor': sync.sync_adj_factor,
            'daily_basic': sync.sync_daily_basic,
            'moneyflow': sync.sync_moneyflow,
            'moneyflow_hsgt': sync.sync_moneyflow_hsgt,
            'cyq_chips': sync.sync_cyq_chips,
            'all': sync.sync_all,
        }

        handler = type_map[args.type]
        if args.type in ('basic',):
            handler()
        elif args.type in ('calendar',):
            handler(start_date=args.start or '20150101', end_date=args.end)
        else:
            handler(start_date=args.start, end_date=args.end)

    finally:
        sync.close()


if __name__ == '__main__':
    main()
