# -*- coding: utf-8 -*-
import json as _json
import re as _re
from datetime import datetime, timedelta

import pandas as pd
import requests
from loguru import logger
from sqlalchemy import text

from app.extensions import db
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

    CACHE_TTL_OVERVIEW = 120  # 秒（必须 > 任务间隔 30s，否则缓存过期导致 API 无数据）
    CACHE_TTL_KLINE = 120     # 秒
    CACHE_TTL_BOARDS = 120    # 秒（必须 > 任务间隔 60s）
    CACHE_TTL_SECTOR_FLOW = 180  # 秒

    # 排除的板块名称（AKShare概念板块中的统计类条目，非真实行业/概念板块）
    EXCLUDE_BOARDS = {
        '昨日首板', '昨日涨停', '昨日连板',
        '今日首板', '今日涨停', '今日连板',
        '首板', '连板', '涨停', '跌停',
        '昨日跌停', '今日跌停',
        '首板次日', '连板次日',
    }

    @staticmethod
    def _to_float(value, digits=2):
        if value is None or value == '':
            return None
        try:
            f = float(value)
            if f != f:  # NaN check (NaN != NaN)
                return None
            return round(f, digits)
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
    def get_market_overview(cls, cache_only=False):
        """获取市场概览数据（指数行情 + 涨跌家数），带30秒缓存"""
        cached = _cache.get('market_overview')
        if cached is not None:
            if 'total_amount' not in cached:
                cls._attach_market_totals(cached)
            return cached

        # 纯读缓存模式：缓存未命中时直接返回空数据，不触发外部爬取
        if cache_only:
            return {
                'success': False,
                'message': '数据暂未就绪，请等待后台任务预热缓存。',
                'source': 'none',
                'trade_date': None,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'items': [],
                'advancing': 0,
                'declining': 0,
                'flat': 0,
            }

        # ① 优先尝试 Akshare
        ak_result = cls._fetch_from_akshare()
        if ak_result.get('success'):
            cls._attach_market_totals(ak_result)
            _cache.set('market_overview', ak_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ak_result

        # ② 降级到 Tushare
        logger.warning('Akshare market overview failed, fallback to Tushare')
        ts_result = cls._fetch_from_tushare()
        if ts_result.get('success'):
            cls._attach_market_totals(ts_result)
            _cache.set('market_overview', ts_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ts_result

        # ③ 最终降级：从本地数据库读取最近缓存数据
        logger.error('Both Akshare and Tushare failed, fallback to local database cache')
        local_result = cls._fetch_from_local_cache()
        cls._attach_market_totals(local_result)
        if local_result.get('success') or local_result.get('items'):
            _cache.set('market_overview', local_result, ttl=cls.CACHE_TTL_OVERVIEW)
        return local_result

    @classmethod
    def fetch_fresh_overview(cls):
        """直接从数据源获取最新市场概览（绕过缓存），供 Celery 定时任务使用。

        与 get_market_overview() 的区别：本方法始终从外部 API 获取最新数据，
        不读取 Redis 缓存，确保每次调用都能拿到实时行情。
        """
        # ① 优先尝试 Akshare（新浪快照）
        ak_result = cls._fetch_from_akshare()
        if ak_result.get('success'):
            cls._attach_market_totals(ak_result)
            _cache.set('market_overview', ak_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ak_result

        # ② 降级到 Tushare
        logger.warning('[Celery] Akshare fresh fetch failed, fallback to Tushare')
        ts_result = cls._fetch_from_tushare()
        if ts_result.get('success'):
            cls._attach_market_totals(ts_result)
            _cache.set('market_overview', ts_result, ttl=cls.CACHE_TTL_OVERVIEW)
            return ts_result

        # ③ 最终降级：本地数据库
        logger.error('[Celery] Both Akshare and Tushare failed, fallback to local cache')
        local_result = cls._fetch_from_local_cache()
        cls._attach_market_totals(local_result)
        if local_result.get('success') or local_result.get('items'):
            _cache.set('market_overview', local_result, ttl=cls.CACHE_TTL_OVERVIEW)
        return local_result

    @classmethod
    def _attach_market_totals(cls, result: dict):
        """从数据库查询全市场总成交额(千元)和总成交量(手)，附加到 result 中"""
        conn = None
        try:
            conn, cursor = DatabaseUtils.connect_to_mysql()
            cursor.execute(
                "SELECT SUM(amount), SUM(vol) FROM stock_daily_history "
                "WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily_history)"
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                result['total_amount'] = cls._to_float(row[0], 0)  # 千元
                result['total_vol'] = cls._to_float(row[1], 0)     # 手
            else:
                result['total_amount'] = 0
                result['total_vol'] = 0
        except Exception as exc:
            logger.warning(f'Failed to query market totals: {exc}')
            result['total_amount'] = 0
            result['total_vol'] = 0
        finally:
            if conn:
                conn.close()

    # ======================== 指数历史K线 ========================

    @classmethod
    def get_index_kline(cls, ts_code: str, period: str = '1Y', cache_only: bool = False) -> dict:
        """获取指数历史K线数据

        Args:
            ts_code: 指数代码，如 000001.SH
            period: 时间范围 1M/3M/6M/1Y/3Y
            cache_only: 是否仅读缓存，不触发外部爬取
        """
        period_days = {'1M': 30, '3M': 90, '6M': 180, '1Y': 365, '3Y': 1095}
        days = period_days.get(period, 365)

        # 缓存键
        cache_key = f'index_kline_{ts_code}_{period}'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        # 纯读缓存模式：缓存未命中时直接返回空数据
        if cache_only:
            return {
                'success': False,
                'ts_code': ts_code,
                'source': 'none',
                'kline': [],
                'count': 0,
                'message': 'K线数据暂未就绪，请等待后台任务预热缓存。',
            }

        result = cls._fetch_index_kline(ts_code, days)
        _cache.set(cache_key, result, ttl=cls.CACHE_TTL_KLINE)
        return result

    @classmethod
    def _fetch_index_kline(cls, ts_code: str, days: int) -> dict:
        """从本地数据库或Tushare获取指数K线"""
        # 先尝试本地数据库
        conn = None
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
        finally:
            if conn:
                conn.close()

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

            # 验证数据是否为今天（交易时间内）或最近交易日
            today = datetime.now().strftime('%Y%m%d')
            valid_items_check = [it for it in index_data['items'] if it.get('trade_date')]
            if valid_items_check:
                latest_trade_date_check = max(it['trade_date'] for it in valid_items_check)
                # 标准化日期格式（可能是 2026-05-08 或 20260508）
                normalized_date = latest_trade_date_check.replace('-', '')
                if normalized_date < today:
                    # 数据不是今天的，检查是否是最近交易日（可能周末/节假日）
                    # 允许最多 3 天的差距（覆盖周末 + 节假日）
                    try:
                        data_date = datetime.strptime(normalized_date, '%Y%m%d')
                        today_date = datetime.strptime(today, '%Y%m%d')
                        days_diff = (today_date - data_date).days
                        if days_diff > 3:
                            logger.warning(f'[Akshare] 数据过旧: {latest_trade_date_check} (今天: {today}), 差{days_diff}天，降级到Tushare')
                            return {'success': False, 'message': f'数据过旧: {latest_trade_date_check}'}
                    except ValueError:
                        pass

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
        """第三级降级：从本地 MySQL 读取最近缓存的指数/大盘数据（单次批量查询优化）"""
        conn = None
        try:
            conn, cursor = DatabaseUtils.connect_to_mysql()

            # 构建 ts_code -> name 映射，以及 ts_code -> fallback_code 映射
            index_map = {item['ts_code']: item['name'] for item in cls.INDEX_ITEMS}
            fallback_codes = {
                '000001.SH': '000001.SZ',
                '399001.SZ': '000001.SZ',
                '399006.SZ': '300750.SZ',
            }
            # 收集所有需要查询的 ts_code（主码 + 回退码）
            all_codes = list(index_map.keys()) + list(set(fallback_codes.values()))

            # 单次查询获取所有相关指数的最近行情
            placeholders = ', '.join(['%s'] * len(all_codes))
            sql = (
                "SELECT ts_code, trade_date, open, high, low, close, pre_close, pct_chg, vol, amount "
                "FROM stock_daily_history "
                f"WHERE ts_code IN ({placeholders}) "
                "ORDER BY ts_code, trade_date DESC"
            )
            cursor.execute(sql, all_codes)
            all_rows = cursor.fetchall()

            # 按 ts_code 分组，每个组最多保留最近 60 条
            rows_by_code = {}
            current_code = None
            count = 0
            for row in all_rows:
                code = row[0]
                if code != current_code:
                    current_code = code
                    count = 0
                if count < 60:
                    rows_by_code.setdefault(code, []).append(row)
                    count += 1

            # 为每个 INDEX_ITEM 构建结果
            items = []
            latest_trade_date = None

            for index_item in cls.INDEX_ITEMS:
                ts_code = index_item['ts_code']
                # 主码有数据则用主码，否则查回退码
                rows = rows_by_code.get(ts_code, [])
                if not rows:
                    fb_code = fallback_codes.get(ts_code)
                    if fb_code:
                        rows = rows_by_code.get(fb_code, [])

                kline_data = [
                    {
                        'trade_date': str(row[1]) if row[1] else '',
                        'open': cls._to_float(row[2]),
                        'high': cls._to_float(row[3]),
                        'low': cls._to_float(row[4]),
                        'close': cls._to_float(row[5]),
                        'vol': cls._to_float(row[8], 0),
                    }
                    for row in rows
                ]

                if rows:
                    first = rows[0]
                    close_val = cls._to_float(first[5])
                    pre_close_val = cls._to_float(first[6])
                    pct_chg_val = cls._to_float(first[7])
                    change_val = None
                    if close_val is not None and pre_close_val is not None:
                        change_val = cls._to_float(close_val - pre_close_val)
                    if pct_chg_val is None and change_val is not None and pre_close_val not in (None, 0):
                        pct_chg_val = cls._to_float(change_val / pre_close_val * 100)

                    trade_dt = str(first[1]) if first[1] else ''
                    items.append({
                        'ts_code': ts_code,
                        'name': index_item['name'],
                        'trade_date': trade_dt,
                        'close': close_val,
                        'change': change_val,
                        'pct_chg': pct_chg_val,
                        'vol': cls._to_float(first[8], 0),
                        'amount': cls._to_float(first[9], 0),
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
                'success': False,
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
        finally:
            if conn:
                conn.close()

    # ======================== 热门板块排行 ========================

    @classmethod
    def get_hot_boards(cls, board_type: str = 'industry', limit: int = 10, cache_only: bool = False) -> dict:
        """获取热门板块排行数据

        Args:
            board_type: 'industry' 行业板块 / 'concept' 概念板块
            limit: 返回条数，默认 10
            cache_only: 是否仅读缓存
        """
        cache_key = f'hot_boards_{board_type}'
        cached = _cache.get(cache_key)
        if cached is not None:
            result = dict(cached)
            result['items'] = result.get('items', [])[:limit]
            return result

        if cache_only:
            return {
                'success': False,
                'message': '板块数据暂未就绪，请等待后台任务预热缓存。',
                'board_type': board_type,
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        # 缓存时取 50 条，API 层按需裁剪（支持分页）
        result = cls._fetch_board_ranking(board_type=board_type, limit=50)
        _cache.set(cache_key, result, ttl=cls.CACHE_TTL_BOARDS)
        result['items'] = result.get('items', [])[:limit]
        return result

    # 新浪板块数据 API 地址
    _SINA_INDUSTRY_URL = 'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php'
    _SINA_CONCEPT_URL = 'https://money.finance.sina.com.cn/q/view/newFLJK.php?param=class'
    _SINA_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://finance.sina.com.cn',
    }

    @classmethod
    def _fetch_sina_board_data(cls, url: str) -> list:
        """从新浪财经板块接口获取原始数据

        新浪返回 JS 变量赋值格式：var S_Finance_bankuai_xxx = {"key":"val1,val2,...", ...}
        每条记录包含 13 个逗号分隔字段：
          [0] 板块代码  [1] 板块名称  [2] 成分股数量  [3] 均价
          [4] 涨跌额    [5] 涨跌幅(%)  [6] 成交量(手)  [7] 成交额(元)
          [8] 领涨股代码 [9] 领涨股涨幅(%) [10] 领涨股现价 [11] 领涨股涨跌额
          [12] 领涨股名称

        Returns:
            list[dict]: 解析后的板块列表
        """
        try:
            from app.services.akshare_service import call_with_no_proxy

            def _do_fetch():
                resp = requests.get(url, headers=cls._SINA_HEADERS, timeout=15)
                resp.encoding = 'gbk'
                return resp

            resp = call_with_no_proxy(_do_fetch)
            raw_text = resp.text or ''
            match = _re.search(r'\{.*\}', raw_text, _re.DOTALL)
            if not match:
                logger.warning(f'Sina board API returned no JSON data from {url}')
                return []

            raw = _json.loads(match.group())
            boards = []
            for key, val in raw.items():
                parts = str(val).split(',')
                if len(parts) < 13:
                    continue
                boards.append({
                    'code': parts[0].strip(),
                    'name': parts[1].strip(),
                    'stock_count': cls._to_int(parts[2]),
                    'price': cls._to_float(parts[3]),       # 板块均价
                    'change': cls._to_float(parts[4]),       # 涨跌额
                    'pct_change': cls._to_float(parts[5]),   # 涨跌幅(%)
                    'volume': cls._to_float(parts[6], 0),    # 成交量
                    'amount': cls._to_float(parts[7], 0),    # 成交额
                    'lead_stock_code': parts[8].strip(),
                    'lead_stock_pct': cls._to_float(parts[9]),
                    'lead_stock_price': cls._to_float(parts[10]),
                    'lead_stock_change': cls._to_float(parts[11]),
                    'lead_stock': parts[12].strip(),
                })
            return boards
        except Exception as exc:
            logger.error(f'Sina board data fetch failed ({url}): {exc}')
            return []

    @classmethod
    def _fetch_eastmoney_board_ranking(cls, board_type: str = 'industry', limit: int = 50) -> list:
        """直接调用东方财富 HTTP API 获取板块排行（不通过 AKShare）

        作为新浪接口不可用时的降级方案。

        Returns:
            list[dict]: 解析后的板块列表，格式与新浪接口一致
        """
        try:
            from app.services.akshare_service import call_with_no_proxy

            # fs 参数：m:90+t:2 表示行业板块，m:90+t:3 表示概念板块
            fs = 'm:90+t:2+f:!50' if board_type == 'industry' else 'm:90+t:3+f:!50'
            url = 'https://push2.eastmoney.com/api/qt/clist/get'
            params = {
                'pn': 1,
                'pz': limit,
                'po': 1,
                'np': 1,
                'fltt': 2,
                'invt': 2,
                'fid': 'f3',
                'fs': fs,
                'fields': 'f2,f3,f4,f8,f12,f14,f104,f105,f128,f136,f115,f140,f141',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://data.eastmoney.com/',
                'Accept': '*/*',
            }

            def _do_fetch():
                return requests.get(url, params=params, headers=headers, timeout=15)

            resp = call_with_no_proxy(_do_fetch)
            data = resp.json()
            diff = (data.get('data') or {}).get('diff') or []
            if not diff:
                return []

            boards = []
            for item in diff:
                boards.append({
                    'code': str(item.get('f12', '')),
                    'name': str(item.get('f14', '')),
                    'stock_count': cls._to_int(item.get('f104', 0)) + cls._to_int(item.get('f105', 0)),
                    'price': cls._to_float(item.get('f2')),
                    'change': cls._to_float(item.get('f4')),
                    'pct_change': cls._to_float(item.get('f3')),
                    'volume': None,
                    'amount': None,
                    'lead_stock_code': str(item.get('f140', '')),
                    'lead_stock_pct': cls._to_float(item.get('f136')),
                    'lead_stock_price': cls._to_float(item.get('f141')),
                    'lead_stock_change': None,
                    'lead_stock': str(item.get('f128', '')),
                    'turnover_rate': cls._to_float(item.get('f8')),
                    'up_count': cls._to_int(item.get('f104')),
                    'down_count': cls._to_int(item.get('f105')),
                    'lead_stock_pct_raw': cls._to_float(item.get('f115')),
                })
            return boards
        except Exception as exc:
            logger.warning(f'EastMoney board ranking fallback failed ({board_type}): {exc}')
            return []

    @classmethod
    def _fetch_board_ranking(cls, board_type: str = 'industry', limit: int = 10) -> dict:
        """获取板块排行数据（新浪财经为主，东方财富 HTTP API 为降级）

        数据源优先级：
          1. 新浪财经板块接口（免费、稳定）
          2. 东方财富 HTTP API（直接调用，不通过 AKShare）

        返回字段与原有接口保持一致，前端无需修改。
        """
        try:
            # ① 优先使用新浪财经接口
            url = cls._SINA_CONCEPT_URL if board_type == 'concept' else cls._SINA_INDUSTRY_URL
            boards = cls._fetch_sina_board_data(url)
            source = 'sina_finance'

            # ② 降级：如果新浪接口无数据，尝试东方财富 HTTP API
            if not boards:
                logger.info(f'Sina {board_type} board data empty, fallback to EastMoney HTTP API')
                boards = cls._fetch_eastmoney_board_ranking(board_type=board_type, limit=50)
                source = 'eastmoney_http'

            if not boards:
                return {
                    'success': False,
                    'message': f'{board_type} 板块数据为空（新浪和东方财富均无数据）',
                    'board_type': board_type,
                    'items': [],
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }

            # 过滤掉统计类条目
            boards = [b for b in boards if b.get('name') not in cls.EXCLUDE_BOARDS]

            # 按涨跌幅降序排列
            boards.sort(key=lambda x: x.get('pct_change') if x.get('pct_change') is not None else -9999, reverse=True)

            items = []
            for b in boards[:limit]:
                items.append({
                    'name': cls._to_float_text(b.get('name', '')),
                    'code': cls._to_float_text(b.get('code', '')),
                    'price': cls._to_float(b.get('price')),
                    'pct_change': cls._to_float(b.get('pct_change')),
                    'change': cls._to_float(b.get('change')),
                    'total_market_cap': cls._to_float(b.get('total_market_cap'), 0),
                    'turnover_rate': cls._to_float(b.get('turnover_rate')),
                    'up_count': cls._to_int(b.get('up_count')),
                    'down_count': cls._to_int(b.get('down_count')),
                    'stock_count': cls._to_int(b.get('stock_count')),  # 新浪接口提供成分股数量
                    'lead_stock': cls._to_float_text(b.get('lead_stock', '')),
                    'lead_stock_pct': cls._to_float(b.get('lead_stock_pct')),
                })

            board_label = '行业' if board_type == 'industry' else '概念'
            return {
                'success': True,
                'message': f'热门{board_label}板块已加载（数据源: {source}）。',
                'board_type': board_type,
                'source': source,
                'items': items,
                'total': len(boards),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as exc:
            logger.error(f'获取{board_type}板块排行失败: {exc}')
            return {
                'success': False,
                'message': f'板块数据获取失败: {exc}',
                'board_type': board_type,
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

    @staticmethod
    def _to_float_text(value) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ''
        return str(value).strip()

    @staticmethod
    def _to_int(value) -> int:
        if value is None:
            return 0
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    # ======================== 板块资金流向排名 ========================

    @classmethod
    def get_sector_fund_flow_rank(cls, limit: int = 20, cache_only: bool = False) -> dict:
        """获取板块资金流向排名数据

        Args:
            limit: 返回条数，默认 20
            cache_only: 是否仅读缓存
        """
        cache_key = 'sector_fund_flow_rank'
        cached = _cache.get(cache_key)
        if cached is not None:
            result = dict(cached)
            result['items'] = result.get('items', [])[:limit]
            return result

        if cache_only:
            return {
                'success': False,
                'message': '板块资金流向数据暂未就绪，请等待后台任务预热缓存。',
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        result = cls._fetch_sector_fund_flow_rank()
        # 只缓存成功的结果，避免缓存错误信息
        if result.get('success'):
            _cache.set(cache_key, result, ttl=cls.CACHE_TTL_SECTOR_FLOW)
        result['items'] = result.get('items', [])[:limit]
        return result

    # ======================== 全球主要指数 ========================

    # 新浪全球指数代码列表
    GLOBAL_INDEX_CODES = [
        's_sh000001',   # 上证指数
        's_sz399001',   # 深证成指
        's_sz399006',   # 创业板指
        'int_hangseng',  # 恒生指数
        'int_nasdaq',    # 纳斯达克
        'int_dji',       # 道琼斯
        'int_sp500',     # 标普500
        'int_nikkei',    # 日经225
        'int_ftse',      # 富时100
        'int_dax',       # 德国DAX
    ]

    GLOBAL_INDEX_CACHE_TTL = 60  # 秒

    @classmethod
    def get_global_indices(cls, cache_only: bool = False) -> dict:
        """获取全球主要指数数据（新浪接口），带60秒缓存"""
        cache_key = 'global_indices'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        if cache_only:
            return {
                'success': False,
                'message': '全球指数数据暂未就绪。',
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        result = cls._fetch_global_indices_from_sina()
        if result.get('success'):
            _cache.set(cache_key, result, ttl=cls.GLOBAL_INDEX_CACHE_TTL)
        return result

    @classmethod
    def _fetch_global_indices_from_sina(cls) -> dict:
        """通过新浪 hq.sinajs.cn 接口获取全球主要指数实时数据"""
        from app.services.akshare_service import call_with_no_proxy

        codes_str = ','.join(cls.GLOBAL_INDEX_CODES)
        url = f'https://hq.sinajs.cn/list={codes_str}'
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        try:
            def _do_fetch():
                resp = requests.get(url, headers=headers, timeout=8)
                resp.encoding = 'gbk'
                return resp

            resp = call_with_no_proxy(_do_fetch)
            raw_text = resp.text
        except Exception as exc:
            logger.error(f'获取新浪全球指数失败: {exc}')
            return {
                'success': False,
                'message': f'获取全球指数数据失败: {exc}',
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        items = []
        for line in raw_text.strip().split('\n'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            # 解析 var hq_str_s_sh000001="上证指数,3261.5561,28.933,0.89,3936465,39778432";
            try:
                var_part, data_part = line.split('=', 1)
                # 提取代码
                code = var_part.split('hq_str_')[-1].strip()
                # 提取引号内的数据
                data_str = data_part.strip().rstrip(';').strip('"').strip()
                if not data_str:
                    continue

                fields = data_str.split(',')
                if len(fields) < 4:
                    continue

                name = fields[0].strip()
                price = cls._to_float(fields[1])
                change = cls._to_float(fields[2])
                pct_chg = cls._to_float(fields[3])

                if price is None:
                    continue

                items.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'change': change,
                    'pct_chg': pct_chg,
                })
            except Exception as exc:
                logger.warning(f'解析新浪指数行失败: {line}, 错误: {exc}')
                continue

        return {
            'success': True,
            'message': '全球指数数据已加载。',
            'items': items,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    # 东方财富板块资金流向 API（直接 HTTP 调用，不通过 AKShare）
    _EM_FUND_FLOW_URL = 'https://push2.eastmoney.com/api/qt/clist/get'
    _EM_FUND_FLOW_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://data.eastmoney.com/',
        'Accept': '*/*',
    }

    @classmethod
    def _fetch_sector_fund_flow_rank(cls, limit: int = 0) -> dict:
        """获取板块资金流向排名数据

        数据源优先级：
          1. Tushare moneyflow_ind_dc 接口（盘后更新，稳定可靠）
          2. 东方财富 HTTP API（直接调用，实时数据）

        Args:
            limit: 返回条数，0 表示返回全部（默认返回全部，由 API 层按需分页裁剪）
        """
        try:
            from app.services.akshare_service import call_with_no_proxy

            # ① 优先使用 Tushare moneyflow_ind_dc 接口
            source = 'tushare'
            items = cls._fetch_fund_flow_from_tushare(limit)

            # ② 降级：如果 Tushare 无数据，尝试东方财富 HTTP API
            if not items:
                logger.info('Tushare fund flow data empty, fallback to EastMoney HTTP API')
                items = cls._fetch_fund_flow_from_eastmoney(limit)
                source = 'eastmoney_http'

            if not items:
                return {
                    'success': False,
                    'message': '板块资金流向数据暂不可用（数据源维护中）',
                    'items': [],
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }

            return {
                'success': True,
                'message': f'板块资金流向排名已加载（数据源: {source}）。',
                'source': source,
                'items': items,
                'total': len(items),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as exc:
            logger.error(f'获取板块资金流向排名失败: {exc}')
            return {
                'success': False,
                'message': '板块资金流向数据暂不可用（数据源维护中，请稍后再试）',
                'items': [],
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

    @classmethod
    def _fetch_fund_flow_from_tushare(cls, limit: int = 0) -> list:
        """通过 Tushare moneyflow_ind_dc 获取板块资金流向"""
        try:
            import threading

            def _do_fetch():
                pro = DatabaseUtils.init_tushare_api()
                trade_date = datetime.now().strftime('%Y%m%d')
                df = pro.moneyflow_ind_dc(trade_date=trade_date, content_type='行业')
                if df is None or df.empty:
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                    df = pro.moneyflow_ind_dc(trade_date=yesterday, content_type='行业')
                return df

            # 在独立线程中执行，绕过 eventlet 的阻塞检测
            result_box = [None]
            err_box = [None]
            def _thread_target():
                try:
                    result_box[0] = _do_fetch()
                except Exception as e:
                    err_box[0] = e
            t = threading.Thread(target=_thread_target, daemon=True)
            t.start()
            t.join(timeout=30)
            if err_box[0]:
                raise err_box[0]
            df = result_box[0]

            if df is None or df.empty:
                return []

            # 按主力净流入降序排列
            df = df.sort_values('net_amount', ascending=False, na_position='last')

            rows = df.head(limit).iterrows() if limit > 0 else df.iterrows()
            items = []
            for _, row in rows:
                items.append({
                    'name': cls._to_float_text(row.get('name', '')),
                    'pct_change': cls._to_float(row.get('pct_change')),
                    'main_net_inflow': cls._to_float(row.get('net_amount'), 0),
                    'main_net_pct': cls._to_float(row.get('net_amount_rate')),
                    'super_large_net_inflow': cls._to_float(row.get('buy_elg_amount'), 0),
                    'super_large_net_pct': cls._to_float(row.get('buy_elg_amount_rate')),
                    'large_net_inflow': cls._to_float(row.get('buy_lg_amount'), 0),
                    'large_net_pct': cls._to_float(row.get('buy_lg_amount_rate')),
                    'mid_net_inflow': cls._to_float(row.get('buy_md_amount'), 0),
                    'mid_net_pct': cls._to_float(row.get('buy_md_amount_rate')),
                    'small_net_inflow': cls._to_float(row.get('buy_sm_amount'), 0),
                    'small_net_pct': cls._to_float(row.get('buy_sm_amount_rate')),
                    'lead_stock': cls._to_float_text(row.get('buy_sm_amount_stock', '')),
                })
            return items
        except Exception as exc:
            logger.warning(f'Tushare fund flow fetch failed: {exc}')
            return []

    @classmethod
    def _fetch_fund_flow_from_eastmoney(cls, limit: int = 0) -> list:
        """通过东方财富 HTTP API 获取板块资金流向（备用方案）"""
        try:
            import threading

            params = {
                'pn': 1, 'pz': 500, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2,
                'fid': 'f62', 'fs': 'm:90+t:2+f:!50',
                'fields': 'f2,f3,f4,f12,f14,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124,f128,f115',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            }

            def _do_fetch():
                resp = requests.get(cls._EM_FUND_FLOW_URL, params=params, headers=cls._EM_FUND_FLOW_HEADERS, timeout=15)
                if resp.status_code != 200:
                    return None
                return resp.json()

            result_box = [None]
            err_box = [None]
            def _thread_target():
                try:
                    result_box[0] = _do_fetch()
                except Exception as e:
                    err_box[0] = e
            t = threading.Thread(target=_thread_target, daemon=True)
            t.start()
            t.join(timeout=20)
            if err_box[0]:
                raise err_box[0]
            data = result_box[0]

            if not data:
                return []
            diff = (data.get('data') or {}).get('diff') or []
            if not diff:
                return []

            diff.sort(key=lambda x: x.get('f62') if x.get('f62') is not None else -float('inf'), reverse=True)

            rows = diff[:limit] if limit > 0 else diff
            items = []
            for item in rows:
                items.append({
                    'name': cls._to_float_text(item.get('f14', '')),
                    'pct_change': cls._to_float(item.get('f3')),
                    'main_net_inflow': cls._to_float(item.get('f62'), 0),
                    'main_net_pct': cls._to_float(item.get('f184')),
                    'super_large_net_inflow': cls._to_float(item.get('f66'), 0),
                    'super_large_net_pct': cls._to_float(item.get('f69')),
                    'large_net_inflow': cls._to_float(item.get('f72'), 0),
                    'large_net_pct': cls._to_float(item.get('f75')),
                    'mid_net_inflow': cls._to_float(item.get('f78'), 0),
                    'mid_net_pct': cls._to_float(item.get('f81')),
                    'small_net_inflow': cls._to_float(item.get('f84'), 0),
                    'small_net_pct': cls._to_float(item.get('f87')),
                    'lead_stock': cls._to_float_text(item.get('f128', '')),
                })
            return items
        except Exception as exc:
            logger.warning(f'EastMoney fund flow fetch failed: {exc}')
            return []
