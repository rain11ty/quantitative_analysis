# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from loguru import logger

from app.services.akshare_service import AkshareService
from app.utils.cache_utils import cache as _cache
from app.utils.db_utils import DatabaseUtils


class MarketOverviewService:
    INDEX_ITEMS = [
        {'ts_code': '000001.SH', 'name': '上证指数'},
        {'ts_code': '399001.SZ', 'name': '深证成指'},
        {'ts_code': '399006.SZ', 'name': '创业板指'},
        {'ts_code': '000016.SH', 'name': '上证50'},
        {'ts_code': '000300.SH', 'name': '沪深300'},
        {'ts_code': '000905.SH', 'name': '中证500'},
        {'ts_code': '000688.SH', 'name': '科创50'},
    ]

    CACHE_TTL_OVERVIEW = 30   # 秒
    CACHE_TTL_KLINE = 60      # 秒

    @staticmethod
    def _to_float(value, digits=2):
        if value is None or value == '':
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    # ======================== 健康检查 ========================

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

    # ======================== 核心入口（带缓存）========================

    @classmethod
    def get_market_overview(cls):
        """获取市场概览数据（指数行情 + 涨跌家数），带30秒缓存"""
        cached = _cache.get('market_overview')
        if cached is not None:
            return cached

        # ① 优先尝试 Akshare
        ak_result = cls._fetch_from_akshare()
        if ak_result.get('success'):
            _cache.set('market_overview', ak_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ak_result

        # ② 降级到 Tushare
        logger.warning('Akshare market overview failed, fallback to Tushare')
        ts_result = cls._fetch_from_tushare()
        if ts_result.get('success'):
            _cache.set('market_overview', ts_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ts_result

        # ③ 最终降级：从本地数据库读取最近缓存数据
        logger.error('Both Akshare and Tushare failed, fallback to local database cache')
        local_result = cls._fetch_from_local_cache()
        _cache.set('market_overview', local_result, ttl=cls.CACHE_TTL_OVERVIEW)
        return local_result

    # ======================== 指数历史K线 ========================

    @classmethod
    def get_index_kline(cls, ts_code: str, period: str = '1Y') -> dict:
        """获取指数历史K线数据

        Args:
            ts_code: 指数代码，如 000001.SH
            period: 时间范围 1M/3M/6M/1Y/3Y
        """
        period_days = {'1M': 30, '3M': 90, '6M': 180, '1Y': 365, '3Y': 1095}
        days = period_days.get(period, 365)

        # 缓存键
        cache_key = f'index_kline_{ts_code}_{period}'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        result = cls._fetch_index_kline(ts_code, days)
        _cache.set(cache_key, result, ttl=cls.CACHE_TTL_KLINE)
        return result

    @classmethod
    def _fetch_index_kline(cls, ts_code: str, days: int) -> dict:
        """从本地数据库或Tushare获取指数K线"""
        # 先尝试本地数据库
        try:
            conn, cursor = DatabaseUtils.connect_to_mysql()
            start_date = (datetime.now() - timedelta(days=int(days * 1.5))).strftime('%Y%m%d')
            cursor.execute(
                "SELECT trade_date, open, high, low, close, vol, amount "
                "FROM stock_daily_history "
                "WHERE ts_code = %s AND trade_date >= %s "
                "ORDER BY trade_date ASC",
                (ts_code, start_date),
            )
            rows = cursor.fetchall()
            conn.close()

            if rows and len(rows) >= 10:
                kline = []
                for row in rows:
                    kline.append({
                        'trade_date': str(row[0]),
                        'open': cls._to_float(row[1]),
                        'high': cls._to_float(row[2]),
                        'low': cls._to_float(row[3]),
                        'close': cls._to_float(row[4]),
                        'vol': cls._to_float(row[5], 0),
                        'amount': cls._to_float(row[6], 0),
                    })
                return {
                    'success': True,
                    'ts_code': ts_code,
                    'source': 'local_db',
                    'kline': kline,
                    'count': len(kline),
                }
        except Exception as exc:
            logger.warning(f'Local DB index kline failed for {ts_code}: {exc}')

        # 降级到 Tushare index_daily
        try:
            pro = DatabaseUtils.init_tushare_api()
            end_date = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=int(days * 1.5))).strftime('%Y%m%d')

            # 指数用 index_daily 接口
            df = pro.index_daily(ts_code=ts_code, start_date=start, end_date=end_date)
            if df is not None and not df.empty:
                df = df.sort_values('trade_date', ascending=True)
                kline = []
                for _, row in df.iterrows():
                    kline.append({
                        'trade_date': str(row.get('trade_date', '')),
                        'open': cls._to_float(row.get('open')),
                        'high': cls._to_float(row.get('high')),
                        'low': cls._to_float(row.get('low')),
                        'close': cls._to_float(row.get('close')),
                        'vol': cls._to_float(row.get('vol'), 0),
                        'amount': cls._to_float(row.get('amount'), 0),
                    })
                return {
                    'success': True,
                    'ts_code': ts_code,
                    'source': 'tushare_index_daily',
                    'kline': kline,
                    'count': len(kline),
                }
        except Exception as exc:
            logger.error(f'Tushare index kline failed for {ts_code}: {exc}')

        return {
            'success': False,
            'ts_code': ts_code,
            'source': 'none',
            'kline': [],
            'count': 0,
            'message': f'无法获取 {ts_code} 的K线数据',
        }

    # ======================== Akshare 数据源 ========================

    @classmethod
    def _fetch_from_akshare(cls):
        """通过新浪快照获取大盘指数实时数据 + 涨跌统计"""
        try:
            index_data = AkshareService.get_index_spot()
            if not index_data.get('success') or not index_data.get('items'):
                return {'success': False, 'message': index_data.get('message', '新浪指数数据为空')}

            stats_data = AkshareService.get_market_stats()

            items = []
            for item in index_data['items']:
                ts_code = item['ts_code']
                matched = next((i for i in cls.INDEX_ITEMS if i['ts_code'] == ts_code), None)
                if not matched:
                    continue

                kline = cls._build_index_kline(ts_code, snapshot=item)
                items.append({
                    'ts_code': ts_code,
                    'name': matched['name'],
                    'trade_date': item.get('trade_date', ''),
                    'close': item.get('price'),
                    'change': item.get('change'),
                    'pct_chg': item.get('pct_chg'),
                    'vol': item.get('vol'),
                    'amount': item.get('amount'),
                    'error': None,
                    'kline': kline,
                })

            valid_items = [it for it in items if it.get('trade_date')]
            latest_trade_date = max(it['trade_date'] for it in valid_items) if valid_items else ''

            return {
                'success': True,
                'message': 'Market overview loaded (Sina snapshot).',
                'source': index_data.get('source', 'sina_index'),
                'trade_date': latest_trade_date,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': None,
                'items': items,
                'advancing': stats_data.get('advancing', 0),
                'declining': stats_data.get('declining', 0),
                'flat': stats_data.get('flat', 0),
            }
        except Exception as exc:
            logger.error(f'Get Akshare market overview failed: {exc}')
            return {'success': False, 'message': f'Akshare error: {exc}'}

    @classmethod
    def _merge_snapshot_into_kline(cls, kline: list, snapshot: dict | None = None) -> list:
        if not snapshot:
            return list(kline or [])

        trade_date = str(snapshot.get('trade_date') or '').strip()
        close = cls._to_float(snapshot.get('price'))
        if not trade_date or close is None:
            return list(kline or [])

        open_price = cls._to_float(snapshot.get('open'))
        pre_close = cls._to_float(snapshot.get('pre_close'))
        high = cls._to_float(snapshot.get('high'))
        low = cls._to_float(snapshot.get('low'))
        candidate_values = [value for value in [open_price, close, pre_close] if value is not None]
        fallback_high = max(candidate_values) if candidate_values else close
        fallback_low = min(candidate_values) if candidate_values else close

        current_candle = {
            'trade_date': trade_date,
            'open': open_price if open_price is not None else pre_close if pre_close is not None else close,
            'close': close,
            'high': high if high is not None else fallback_high,
            'low': low if low is not None else fallback_low,
            'vol': snapshot.get('vol'),
            'amount': snapshot.get('amount'),
        }

        merged = [dict(item) for item in (kline or [])]
        if merged and str(merged[-1].get('trade_date') or '').strip() == trade_date:
            merged[-1].update({key: value for key, value in current_candle.items() if value not in (None, '')})
        else:
            merged.append(current_candle)
        return merged

    @classmethod
    def _build_index_kline(cls, ts_code: str, snapshot: dict | None = None, days: int = 60) -> list:
        """从 Akshare 历史日线 + 新浪快照拼接实时日线"""
        code_part = ts_code.split('.')[0]
        symbol_map = {
            '000001': 'sh000001',
            '399001': 'sz399001',
            '399006': 'sz399006',
            '000016': 'sh000016',
            '000300': 'sh000300',
            '000905': 'sh000905',
            '000688': 'sh000688',
        }
        ak_symbol = symbol_map.get(code_part)
        if not ak_symbol:
            return cls._merge_snapshot_into_kline([], snapshot=snapshot)

        try:
            start = (datetime.now() - timedelta(days=int(days * 1.5))).strftime('%Y%m%d')
            hist = AkshareService.get_index_history(symbol=ak_symbol, start_date=start)
            return cls._merge_snapshot_into_kline(hist.get('data', []), snapshot=snapshot)
        except Exception as exc:
            logger.warning(f'Index kline fetch failed ({ts_code}): {exc}')
            return cls._merge_snapshot_into_kline([], snapshot=snapshot)

    # ======================== Tushare 数据源（降级兜底）========================

    @classmethod
    def _fetch_from_tushare(cls):
        """通过 Tushare Pro 获取市场概览（降级方案）"""
        try:
            pro = DatabaseUtils.init_tushare_api()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

            items = []
            latest_trade_date = None

            for index_item in cls.INDEX_ITEMS:
                df = pro.index_daily(ts_code=index_item['ts_code'], start_date=start_date, end_date=end_date)
                if df is None or df.empty:
                    items.append({
                        'ts_code': index_item['ts_code'],
                        'name': index_item['name'],
                        'trade_date': None,
                        'close': None, 'change': None, 'pct_chg': None,
                        'vol': None, 'amount': None,
                        'error': 'No data',
                        'kline': [],
                    })
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

                kline_data = [
                    {
                        'trade_date': str(row.get('trade_date') or ''),
                        'open': cls._to_float(row.get('open')),
                        'close': cls._to_float(row.get('close')),
                        'low': cls._to_float(row.get('low')),
                        'high': cls._to_float(row.get('high')),
                        'vol': cls._to_float(row.get('vol')),
                    }
                    for _, row in df_sorted.iterrows()
                ]

                items.append({
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
                })

            valid_items = [item for item in items if item.get('trade_date')]
            if valid_items:
                latest_trade_date = max(item['trade_date'] for item in valid_items)

            # 涨跌家数
            advancing = declining = flat = 0
            if latest_trade_date:
                daily_df = pro.daily(trade_date=latest_trade_date)
                if daily_df is not None and not daily_df.empty:
                    advancing = int((daily_df['pct_chg'] > 0).sum())
                    declining = int((daily_df['pct_chg'] < 0).sum())
                    flat = int((daily_df['pct_chg'] == 0).sum())

            return {
                'success': True,
                'message': 'Market overview loaded (Tushare fallback).',
                'source': 'tushare_pro',
                'trade_date': latest_trade_date,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': DatabaseUtils.get_tushare_proxy_url(),
                'items': items,
                'advancing': advancing,
                'declining': declining,
                'flat': flat,
            }
        except Exception as exc:
            logger.error(f'Get market overview from Tushare failed: {exc}')
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
                'flat': 0,
            }

    # ======================== 本地数据库降级（第三级兜底）========================

    @classmethod
    def _fetch_from_local_cache(cls):
        """第三级降级：从本地 MySQL 读取最近缓存的指数/大盘数据"""
        try:
            conn, cursor = DatabaseUtils.connect_to_mysql()
            items = []
            latest_trade_date = None

            for index_item in cls.INDEX_ITEMS:
                ts_code = index_item['ts_code']

                try:
                    cursor.execute(
                        "SELECT trade_date, open, high, low, close, pre_close, pct_chg, vol, amount "
                        "FROM stock_daily_history "
                        "WHERE ts_code = %s "
                        "ORDER BY trade_date DESC LIMIT 60",
                        (ts_code,),
                    )
                    rows = cursor.fetchall()

                    if not rows:
                        fallback_codes = {
                            '000001.SH': '000001.SZ',
                            '399001.SZ': '000001.SZ',
                            '399006.SZ': '300750.SZ',
                        }
                        fb_code = fallback_codes.get(ts_code)
                        if fb_code:
                            cursor.execute(
                                "SELECT trade_date, open, high, low, close, pre_close, pct_chg, vol, amount "
                                "FROM stock_daily_history "
                                "WHERE ts_code = %s "
                                "ORDER BY trade_date DESC LIMIT 60",
                                (fb_code,),
                            )
                            rows = cursor.fetchall()

                    kline_data = []
                    for row in rows:
                        kline_data.append({
                            'trade_date': str(row[0]) if row[0] else '',
                            'open': cls._to_float(row[1]),
                            'high': cls._to_float(row[2]),
                            'low': cls._to_float(row[3]),
                            'close': cls._to_float(row[4]),
                            'vol': cls._to_float(row[7], 0),
                        })

                    if rows:
                        first = rows[0]
                        close_val = cls._to_float(first[4])
                        pre_close_val = cls._to_float(first[5])
                        pct_chg_val = cls._to_float(first[6])
                        change_val = None
                        if close_val is not None and pre_close_val is not None:
                            change_val = cls._to_float(close_val - pre_close_val)
                        if pct_chg_val is None and change_val is not None and pre_close_val not in (None, 0):
                            pct_chg_val = cls._to_float(change_val / pre_close_val * 100)

                        trade_dt = str(first[0]) if first[0] else ''
                        items.append({
                            'ts_code': ts_code,
                            'name': index_item['name'],
                            'trade_date': trade_dt,
                            'close': close_val,
                            'change': change_val,
                            'pct_chg': pct_chg_val,
                            'vol': cls._to_float(first[7], 0),
                            'amount': cls._to_float(first[8], 0),
                            'error': None,
                            'kline': kline_data,
                            '_is_fallback': True,
                        })
                        if trade_dt and (latest_trade_date is None or trade_dt > latest_trade_date):
                            latest_trade_date = trade_dt
                    else:
                        items.append({
                            'ts_code': ts_code,
                            'name': index_item['name'],
                            'trade_date': None,
                            'close': None, 'change': None, 'pct_chg': None,
                            'vol': None, 'amount': None,
                            'error': '无本地缓存数据',
                            'kline': [],
                            '_is_fallback': True,
                        })
                except Exception as inner_exc:
                    logger.warning(f'Local cache query failed for {ts_code}: {inner_exc}')
                    items.append({
                        'ts_code': ts_code,
                        'name': index_item['name'],
                        'trade_date': None,
                        'close': None, 'change': None, 'pct_chg': None,
                        'vol': None, 'amount': None,
                        'error': f'本地查询失败: {inner_exc}',
                        'kline': [],
                        '_is_fallback': True,
                    })

            conn.close()

            valid_items = [it for it in items if it.get('trade_date')]
            if valid_items:
                latest_trade_date = max(it['trade_date'] for it in valid_items)

            return {
                'success': True,
                'message': f'Market overview loaded (local cache, trade_date={latest_trade_date or "N/A"}). '
                           f'数据源暂时不可用，当前展示为本地缓存的历史数据。',
                'source': 'local_cache',
                'trade_date': latest_trade_date,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': None,
                'items': items,
                'advancing': 0,
                'declining': 0,
                'flat': 0,
                'degraded': True,
            }
        except Exception as exc:
            logger.error(f'Local database fallback also failed: {exc}')
            return {
                'success': True,
                'message': f'所有数据源均不可用(Akshare/Tushare/本地数据库)，请检查网络或联系管理员。错误: {exc}',
                'source': 'none',
                'trade_date': None,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'proxy_url': None,
                'items': [],
                'advancing': 0,
                'declining': 0,
                'flat': 0,
                'degraded': True,
            }
