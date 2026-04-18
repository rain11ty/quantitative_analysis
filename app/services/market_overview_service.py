# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from loguru import logger

from app.utils.db_utils import DatabaseUtils


class MarketOverviewService:
    INDEX_ITEMS = [
        {'ts_code': '000001.SH', 'name': '\u4e0a\u8bc1\u6307\u6570'},
        {'ts_code': '399001.SZ', 'name': '\u6df1\u8bc1\u6210\u6307'},
        {'ts_code': '399006.SZ', 'name': '\u521b\u4e1a\u677f\u6307'},
    ]

    @staticmethod
    def _to_float(value, digits=2):
        if value is None or value == '':
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    @classmethod
    def ping_tushare(cls):
        try:
            pro = DatabaseUtils.init_tushare_api()
            today = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
            calendar = pro.trade_cal(exchange='', start_date=start_date, end_date=today)

            latest_trade_date = None
            if calendar is not None and not calendar.empty:
                latest_trade_date = str(calendar.iloc[-1].get('cal_date') or '')

            return {
                'success': True,
                'message': 'Tushare Pro connection is healthy.',
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': DatabaseUtils.get_tushare_proxy_url(),
                'latest_trade_date': latest_trade_date,
            }
        except Exception as exc:
            logger.error(f'Tushare ping failed: {exc}')
            return {
                'success': False,
                'message': f'Tushare Pro connection failed: {exc}',
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': DatabaseUtils.get_tushare_proxy_url(),
                'latest_trade_date': None,
            }

    @classmethod
    def get_market_overview(cls):
        try:
            pro = DatabaseUtils.init_tushare_api()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

            items = []
            latest_trade_date = None

            for index_item in cls.INDEX_ITEMS:
                df = pro.index_daily(ts_code=index_item['ts_code'], start_date=start_date, end_date=end_date)
                if df is None or df.empty:
                    items.append(
                        {
                            'ts_code': index_item['ts_code'],
                            'name': index_item['name'],
                            'trade_date': None,
                            'close': None,
                            'change': None,
                            'pct_chg': None,
                            'vol': None,
                            'amount': None,
                            'error': 'No data',
                            'kline': [],
                        }
                    )
                    continue

                df_sorted = df.sort_values('trade_date', ascending=True)
                latest = df_sorted.iloc[-1]
                close = cls._to_float(latest.get('close'))
                pre_close = cls._to_float(latest.get('pre_close'))
                change = cls._to_float(latest.get('change'))
                pct_chg = cls._to_float(latest.get('pct_chg'))

                if change is None and close is not None and pre_close is not None:
                    change = cls._to_float(close - pre_close)
                if pct_chg is None and change is not None and pre_close not in (None, 0):
                    pct_chg = cls._to_float(change / pre_close * 100)

                kline_data = []
                for _, row in df_sorted.iterrows():
                    kline_data.append({
                        'trade_date': str(row.get('trade_date') or ''),
                        'open': cls._to_float(row.get('open')),
                        'close': cls._to_float(row.get('close')),
                        'low': cls._to_float(row.get('low')),
                        'high': cls._to_float(row.get('high')),
                        'vol': cls._to_float(row.get('vol')),
                    })

                items.append(
                    {
                        'ts_code': index_item['ts_code'],
                        'name': index_item['name'],
                        'trade_date': str(latest.get('trade_date') or ''),
                        'close': close,
                        'change': change,
                        'pct_chg': pct_chg,
                        'vol': cls._to_float(latest.get('vol'), 0),
                        'amount': cls._to_float(latest.get('amount'), 0),
                        'error': None,
                        'kline': kline_data,
                    }
                )

            valid_items = [item for item in items if item.get('trade_date')]
            if valid_items:
                latest_trade_date = max(item['trade_date'] for item in valid_items)

            # 获取涨跌家数
            advancing = 0
            declining = 0
            flat = 0
            if latest_trade_date:
                daily_df = pro.daily(trade_date=latest_trade_date)
                if daily_df is not None and not daily_df.empty:
                    advancing = int((daily_df['pct_chg'] > 0).sum())
                    declining = int((daily_df['pct_chg'] < 0).sum())
                    flat = int((daily_df['pct_chg'] == 0).sum())

            return {
                'success': True,
                'message': 'Market overview loaded.',
                'source': 'tushare_pro',
                'trade_date': latest_trade_date,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': DatabaseUtils.get_tushare_proxy_url(),
                'items': items,
                'advancing': advancing,
                'declining': declining,
                'flat': flat
            }
        except Exception as exc:
            logger.error(f'Get market overview failed: {exc}')
            return {
                'success': False,
                'message': f'Get market overview failed: {exc}',
                'source': 'tushare_pro',
                'trade_date': None,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': DatabaseUtils.get_tushare_proxy_url(),
                'items': [],
                'advancing': 0,
                'declining': 0,
                'flat': 0
            }
