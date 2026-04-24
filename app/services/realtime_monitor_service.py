# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import tushare as ts
import pandas as pd
from loguru import logger

from app.models import StockBasic, UserWatchlist
from app.services.akshare_service import AkshareService
from app.services.market_overview_service import MarketOverviewService
from app.services.stock_service import StockService
from app.utils.cache_utils import cache as _cache
from app.utils.db_utils import DatabaseUtils


class RealtimeMonitorService:
    DEFAULT_CODES = ['000001.SZ', '600519.SH', '300750.SZ']
    # 市场指数代码，在监控面板顶部展示（与 MarketOverviewService.INDEX_ITEMS 同步）
    MARKET_INDEX_CODES = ['000001.SH', '399001.SZ', '399006.SZ', '000016.SH', '000300.SH', '000905.SH', '000688.SH']
    MAX_CODES = 12
    SUPPORTED_FREQS = {'daily'}

    # 缓存 TTL
    CACHE_TTL_QUOTES = 15   # 秒（监控页面缓存更短，保证实时性）
    CACHE_TTL_RANKING = 60  # 秒（排名数据缓存更长，减少请求频率）

    @classmethod
    def normalize_ts_code(cls, value: str) -> str:
        code = (value or '').strip().upper()
        if not code:
            return ''
        if '.' in code:
            return code
        if code.startswith(('6', '9')):
            return f'{code}.SH'
        if code.startswith(('0', '2', '3')):
            return f'{code}.SZ'
        if code.startswith(('4', '8')):
            return f'{code}.BJ'
        return code

    @classmethod
    def parse_codes(cls, raw_codes: str) -> List[str]:
        if not raw_codes:
            return []
        normalized: List[str] = []
        for chunk in str(raw_codes).replace('，', ',').replace(';', ',').replace('\n', ',').split(','):
            code = cls.normalize_ts_code(chunk)
            if code and code not in normalized:
                normalized.append(code)
            if len(normalized) >= cls.MAX_CODES:
                break
        return normalized

    @classmethod
    def _create_tushare_client(cls):
        return DatabaseUtils.init_tushare_api()

    @staticmethod
    def _safe_float(value: Any, digits: Optional[int] = 2) -> Optional[float]:
        if value in (None, ''):
            return None
        try:
            number = float(value)
            return round(number, digits) if digits is not None else number
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_text(value: Any) -> str:
        return '' if value is None else str(value).strip()

    @classmethod
    def _get_name_map(cls, codes: List[str]) -> Dict[str, str]:
        if not codes:
            return {}
        stocks = StockBasic.query.filter(StockBasic.ts_code.in_(codes)).all()
        name_map = {stock.ts_code: stock.name for stock in stocks}
        # 补充指数名称
        index_names = {item['ts_code']: item['name'] for item in MarketOverviewService.INDEX_ITEMS}
        for code in codes:
            if code not in name_map and code in index_names:
                name_map[code] = index_names[code]
        return name_map

    @classmethod
    def _get_user_watchlist(cls, user_id: Optional[int]) -> List[UserWatchlist]:
        if not user_id:
            return []
        return (
            UserWatchlist.query.filter_by(user_id=user_id)
            .order_by(UserWatchlist.created_at.desc())
            .limit(cls.MAX_CODES)
            .all()
        )

    @classmethod
    def _pick_codes(cls, user_id: Optional[int], raw_codes: str = '') -> List[str]:
        requested_codes = cls.parse_codes(raw_codes)
        if requested_codes:
            return requested_codes
        watchlist = cls._get_user_watchlist(user_id)
        if watchlist:
            return [item.ts_code for item in watchlist[: cls.MAX_CODES]]
        return list(cls.DEFAULT_CODES)

    @classmethod
    def _first_value(cls, row: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in (None, ''):
                return row[key]
        return None

    @classmethod
    def _build_quote_item(
        cls,
        ts_code: str,
        name: str,
        price: Any,
        pre_close: Any,
        open_price: Any,
        high: Any,
        low: Any,
        volume: Any,
        amount: Any,
        trade_date: Any,
        trade_time: Any,
        turnover_rate: Any = None,
        source: str = 'realtime_quote',
    ) -> Dict[str, Any]:
        price_value = cls._safe_float(price)
        pre_close_value = cls._safe_float(pre_close)
        open_value = cls._safe_float(open_price)
        high_value = cls._safe_float(high)
        low_value = cls._safe_float(low)
        volume_value = cls._safe_float(volume, 0)
        amount_value = cls._safe_float(amount, 0)
        turnover_value = cls._safe_float(turnover_rate)

        change = None
        pct_chg = None
        if price_value is not None and pre_close_value not in (None, 0):
            change = round(price_value - pre_close_value, 2)
            pct_chg = round(change / pre_close_value * 100, 2)

        amplitude = None
        if high_value is not None and low_value is not None and pre_close_value not in (None, 0):
            amplitude = round((high_value - low_value) / pre_close_value * 100, 2)

        return {
            'ts_code': ts_code,
            'name': name or ts_code,
            'price': price_value,
            'pre_close': pre_close_value,
            'open': open_value,
            'high': high_value,
            'low': low_value,
            'change': change,
            'pct_chg': pct_chg,
            'amplitude': amplitude,
            'volume': volume_value,
            'amount': amount_value,
            'turnover_rate': turnover_value,
            'trade_date': cls._safe_text(trade_date),
            'trade_time': cls._safe_text(trade_time),
            'source': source,
        }

    @classmethod
    def _normalize_realtime_quotes(cls, rows: List[Dict[str, Any]], codes: List[str]) -> List[Dict[str, Any]]:
        name_map = cls._get_name_map(codes)
        row_map: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            ts_code = cls._safe_text(cls._first_value(row, 'TS_CODE', 'ts_code'))
            if not ts_code:
                raw_code = cls._safe_text(cls._first_value(row, 'CODE', 'code', 'symbol'))
                if raw_code:
                    matched_code = next((code for code in codes if code.startswith(raw_code)), '')
                    ts_code = matched_code or cls.normalize_ts_code(raw_code)
            if not ts_code:
                continue
            row_map[ts_code] = row

        quotes: List[Dict[str, Any]] = []
        for code in codes:
            row = row_map.get(code, {})
            quotes.append(
                cls._build_quote_item(
                    ts_code=code,
                    name=cls._safe_text(cls._first_value(row, 'NAME', 'name')) or name_map.get(code, code),
                    price=cls._first_value(row, 'PRICE', 'price', 'current'),
                    pre_close=cls._first_value(row, 'PRE_CLOSE', 'pre_close', 'close_yesterday'),
                    open_price=cls._first_value(row, 'OPEN', 'open'),
                    high=cls._first_value(row, 'HIGH', 'high'),
                    low=cls._first_value(row, 'LOW', 'low'),
                    volume=cls._first_value(row, 'VOLUME', 'volume', 'vol'),
                    amount=cls._first_value(row, 'AMOUNT', 'amount'),
                    trade_date=cls._first_value(row, 'DATE', 'date', 'trade_date'),
                    trade_time=cls._first_value(row, 'TIME', 'time', 'trade_time'),
                    turnover_rate=cls._first_value(row, 'TURNOVER_RATE', 'turnover_rate'),
                    source='realtime_quote',
                )
            )
        return quotes

    @classmethod
    def _load_realtime_quotes(cls, codes: List[str]) -> Dict[str, Any]:
        """获取实时行情（Akshare优先 → Tushare降级 → 本地缓存兜底），带缓存"""
        if not codes:
            return {'quotes': [], 'source': 'empty', 'message': 'No codes provided.'}

        # 缓存键：按代码列表排序后生成，避免顺序不同导致重复请求
        cache_key = f'realtime_quotes_{",".join(sorted(codes))}'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        result = cls._do_load_realtime_quotes(codes)
        _cache.set(cache_key, result, ttl=cls.CACHE_TTL_QUOTES)
        return result

    @classmethod
    def _do_load_realtime_quotes(cls, codes: List[str]) -> Dict[str, Any]:
        """实际获取实时行情（内部方法，不走缓存）"""
        # ========== ① 优先：Akshare（免费、实时、无需积分） ==========
        try:
            ak_result = AkshareService.get_realtime_quotes(codes)
            if ak_result.get('quotes') and any(q.get('price') is not None for q in ak_result['quotes']):
                return {
                    'quotes': ak_result['quotes'],
                    'source': ak_result.get('source', 'sina_realtime'),
                    'message': ak_result.get('message', '已通过新浪快照加载实时行情。'),
                }
            logger.warning(f'Akshare quotes returned no price data, trying next source.')
        except Exception as exc:
            logger.warning(f'Akshare realtime quote failed: {exc}')

        # ========== ② 降级：Tushare Pro realtime_quote ==========
        errors: List[str] = []
        code_str = ','.join(codes)

        try:
            ts_mod = DatabaseUtils.init_tushare_realtime()
            df = ts_mod.realtime_quote(ts_code=code_str)
            if df is not None and not df.empty:
                quotes = cls._normalize_realtime_quotes(df.to_dict('records'), codes)
                if any(item.get('price') is not None for item in quotes):
                    return {
                        'quotes': quotes,
                        'source': 'realtime_quote',
                        'message': '已通过 Tushare 实时行情接口加载数据。',
                    }
        except Exception as exc:
            logger.warning(f'Realtime quote failed: {exc}')
            errors.append(str(exc))

        # ========== ③ 兜底：最近交易日数据 / 本地缓存 ==========
        fallback = cls._load_latest_trade_quotes(codes)
        fallback_message = '实时接口暂不可用，已自动降级为最近交易日监控数据。'
        if errors:
            fallback_message = f"{fallback_message} 原因：{errors[-1]}"
        fallback['message'] = fallback_message
        return fallback

    @classmethod
    def _load_latest_trade_quotes(cls, codes: List[str]) -> Dict[str, Any]:
        """获取最近交易日行情数据（优化：批量按日期查询，避免 N+1）"""
        name_map = cls._get_name_map(codes)
        quotes: List[Dict[str, Any]] = []

        try:
            pro = cls._create_tushare_client()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=20)).strftime('%Y%m%d')

            # 区分指数和个股
            stock_codes = [c for c in codes if not c.startswith(('0000', '3990', '0006')) or c[5:7] not in ('SH', 'SZ') or c[:6] in ('000001',)]
            # 实际上简化处理：指数用 index_daily，个股用 daily
            index_codes = []
            stock_codes_list = []
            index_ts_map = {item['ts_code']: item['name'] for item in MarketOverviewService.INDEX_ITEMS}

            for code in codes:
                if code in index_ts_map:
                    index_codes.append(code)
                else:
                    stock_codes_list.append(code)

            # 批量获取指数行情
            for code in index_codes:
                try:
                    df = pro.index_daily(ts_code=code, start_date=start_date, end_date=end_date)
                    if df is not None and not df.empty:
                        df = df.sort_values('trade_date', ascending=False)
                        latest = df.iloc[0]
                        quotes.append(
                            cls._build_quote_item(
                                ts_code=code,
                                name=index_ts_map.get(code, code),
                                price=latest.get('close'),
                                pre_close=latest.get('pre_close'),
                                open_price=latest.get('open'),
                                high=latest.get('high'),
                                low=latest.get('low'),
                                volume=latest.get('vol'),
                                amount=latest.get('amount'),
                                trade_date=cls._safe_text(latest.get('trade_date')),
                                trade_time='latest_trade_day',
                                source='latest_trade_day',
                            )
                        )
                        continue
                except Exception as exc:
                    logger.warning(f'Index daily fetch failed for {code}: {exc}')

                quotes.append(cls._build_quote_item(code, index_ts_map.get(code, code), None, None, None, None, None, None, None, None, None, source='latest_trade_day'))

            # 批量获取个股行情：按 trade_date 一次性获取全市场，再过滤
            if stock_codes_list:
                try:
                    # 获取最近交易日
                    cal_df = pro.trade_cal(exchange='SSE', is_open='1', start_date=start_date, end_date=end_date)
                    if cal_df is not None and not cal_df.empty:
                        latest_date = str(cal_df.sort_values('cal_date', ascending=False).iloc[0]['cal_date'])
                    else:
                        latest_date = end_date

                    # 按日期批量获取全市场日线
                    daily_df = pro.daily(trade_date=latest_date)
                    # 批量获取换手率（全市场一次请求）
                    turnover_map = {}
                    try:
                        basic_df = pro.daily_basic(trade_date=latest_date, fields='ts_code,turnover_rate')
                        if basic_df is not None and not basic_df.empty:
                            turnover_map = dict(zip(basic_df['ts_code'], basic_df['turnover_rate']))
                    except Exception as exc:
                        logger.warning(f'Batch daily_basic fetch failed: {exc}')

                    if daily_df is not None and not daily_df.empty:
                        code_set = set(stock_codes_list)
                        filtered = daily_df[daily_df['ts_code'].isin(code_set)]
                        for code in stock_codes_list:
                            row_df = filtered[filtered['ts_code'] == code]
                            if not row_df.empty:
                                latest = row_df.iloc[0]
                                turnover_rate = turnover_map.get(code)
                                quotes.append(
                                    cls._build_quote_item(
                                        ts_code=code,
                                        name=name_map.get(code, code),
                                        price=latest.get('close'),
                                        pre_close=latest.get('pre_close'),
                                        open_price=latest.get('open'),
                                        high=latest.get('high'),
                                        low=latest.get('low'),
                                        volume=latest.get('vol'),
                                        amount=latest.get('amount'),
                                        trade_date=latest_date,
                                        trade_time='latest_trade_day',
                                        turnover_rate=turnover_rate,
                                        source='latest_trade_day',
                                    )
                                )
                            else:
                                quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='latest_trade_day'))
                    else:
                        # 按日期获取失败，逐只获取
                        for code in stock_codes_list:
                            daily_single = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
                            if daily_single is not None and not daily_single.empty:
                                daily_single = daily_single.sort_values('trade_date', ascending=False)
                                latest = daily_single.iloc[0]
                                quotes.append(
                                    cls._build_quote_item(
                                        ts_code=code,
                                        name=name_map.get(code, code),
                                        price=latest.get('close'),
                                        pre_close=latest.get('pre_close'),
                                        open_price=latest.get('open'),
                                        high=latest.get('high'),
                                        low=latest.get('low'),
                                        volume=latest.get('vol'),
                                        amount=latest.get('amount'),
                                        trade_date=cls._safe_text(latest.get('trade_date')),
                                        trade_time='latest_trade_day',
                                        source='latest_trade_day',
                                    )
                                )
                            else:
                                quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='latest_trade_day'))
                except Exception as exc:
                    logger.warning(f'Batch daily fetch failed: {exc}')
                    for code in stock_codes_list:
                        quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='latest_trade_day'))

            return {
                'quotes': quotes,
                'source': 'latest_trade_day',
                'message': '已切换到最近交易日数据。',
            }
        except Exception as exc:
            logger.warning(f'Latest trade quote via Tushare failed: {exc}')

        # 最终兜底：本地数据库
        for code in codes:
            history = StockService.get_daily_history(code, limit=1)
            latest = history[0] if history else {}
            quotes.append(
                cls._build_quote_item(
                    ts_code=code,
                    name=name_map.get(code, code),
                    price=latest.get('close'),
                    pre_close=latest.get('pre_close'),
                    open_price=latest.get('open'),
                    high=latest.get('high'),
                    low=latest.get('low'),
                    volume=latest.get('vol') or latest.get('volume'),
                    amount=latest.get('amount'),
                    trade_date=latest.get('trade_date'),
                    trade_time='local_cache',
                    source='local_cache',
                )
            )

        return {
            'quotes': quotes,
            'source': 'local_cache',
            'message': 'Tushare 接口暂不可用，已切换到本地缓存数据。',
        }

    @classmethod
    def _normalize_date(cls, date_str: str) -> str:
        """将日期统一为 YYYY-MM-DD 格式，方便比较和前端显示"""
        s = cls._safe_text(date_str)
        if not s:
            return ''
        # 已经是 YYYY-MM-DD 格式
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            return s
        # YYYYMMDD 格式 → YYYY-MM-DD
        if len(s) == 8 and s.isdigit():
            return f'{s[:4]}-{s[4:6]}-{s[6:8]}'
        return s

    @classmethod
    def _merge_realtime_quote_into_daily_history(
        cls,
        history: List[Dict[str, Any]],
        realtime_quote: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        merged = [dict(item) for item in history]
        quote = realtime_quote or {}
        trade_date_raw = cls._safe_text(quote.get('trade_date'))
        trade_date = cls._normalize_date(trade_date_raw)
        price = cls._safe_float(quote.get('price'))
        if not trade_date or price is None:
            return merged

        open_price = cls._safe_float(quote.get('open'))
        pre_close = cls._safe_float(quote.get('pre_close'))
        high = cls._safe_float(quote.get('high'))
        low = cls._safe_float(quote.get('low'))
        candidate_values = [value for value in (open_price, price, pre_close) if value is not None]
        fallback_high = max(candidate_values) if candidate_values else price
        fallback_low = min(candidate_values) if candidate_values else price

        today_candle = {
            'trade_date': trade_date,
            'open': open_price if open_price is not None else pre_close if pre_close is not None else price,
            'high': high if high is not None else fallback_high,
            'low': low if low is not None else fallback_low,
            'close': price,
            'vol': cls._safe_float(quote.get('volume'), 0),
            'amount': cls._safe_float(quote.get('amount'), 0),
        }

        # 统一日期格式后比较，避免 '20260424' vs '2026-04-24' 不匹配
        if merged and cls._normalize_date(merged[-1].get('trade_date')) == trade_date:
            merged[-1].update({key: value for key, value in today_candle.items() if value not in (None, '')})
        else:
            merged.append(today_candle)

        return merged

    @classmethod
    def _build_realtime_daily_series(
        cls,
        ts_code: str,
        realtime_quote: Optional[Dict[str, Any]] = None,
        limit: int = 750,
    ) -> Dict[str, Any]:
        # 指数使用 index_daily 接口或本地数据库
        index_ts_map = {item['ts_code']: item['name'] for item in MarketOverviewService.INDEX_ITEMS}

        if ts_code in index_ts_map:
            return cls._build_index_daily_series(ts_code, realtime_quote=realtime_quote, limit=limit)

        history = list(reversed(StockService.get_daily_history(ts_code, limit=limit)))

        # 检测本地数据是否过旧（最后一天距今超过3天），如果是则从 Tushare 补全
        history = cls._ensure_history_up_to_date(ts_code, history, limit=limit)

        merged_history = cls._merge_realtime_quote_into_daily_history(history, realtime_quote=realtime_quote)

        has_realtime_candle = bool(
            realtime_quote
            and realtime_quote.get('price') is not None
            and realtime_quote.get('trade_date')
        )
        series_source = 'sina_daily_candle' if has_realtime_candle else 'stock_daily_history'
        series_message = '已使用新浪快照更新今日K线。' if has_realtime_candle else '已加载本地日线历史。'

        return {
            'series': cls._normalize_series(merged_history),
            'mode': 'daily',
            'source': series_source,
            'message': series_message,
        }

    @classmethod
    def _ensure_history_up_to_date(
        cls,
        ts_code: str,
        history: List[Dict[str, Any]],
        limit: int = 60,
    ) -> List[Dict[str, Any]]:
        """确保日线历史数据是最新的，如果本地数据过旧则从 Tushare 补全"""
        if not history:
            # 本地完全没有数据，直接从 Tushare 拉取
            return cls._fetch_tushare_daily_series(ts_code, limit=limit)

        last_date_str = cls._safe_text(history[-1].get('trade_date')) if history else ''
        if not last_date_str:
            return history

        # 统一日期格式为 YYYYMMDD
        last_date_normalized = last_date_str.replace('-', '')
        try:
            last_date = datetime.strptime(last_date_normalized, '%Y%m%d')
        except ValueError:
            return history

        days_gap = (datetime.now() - last_date).days
        if days_gap <= 3:
            # 数据足够新，无需补全
            return history

        # 本地数据过旧，从 Tushare 拉取完整历史
        logger.info(f'[DailySeries] {ts_code} 本地数据最后日期={last_date_str}，距今{days_gap}天，从 Tushare 补全')
        tushare_history = cls._fetch_tushare_daily_series(ts_code, limit=limit)
        if tushare_history:
            return tushare_history

        # Tushare 也失败了，返回本地数据
        return history

    @classmethod
    def _fetch_tushare_daily_series(
        cls,
        ts_code: str,
        limit: int = 60,
    ) -> List[Dict[str, Any]]:
        """从 Tushare 获取日线历史数据（用于补全本地数据的缺口）"""
        try:
            pro = cls._create_tushare_client()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=limit * 2)).strftime('%Y%m%d')
            df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return []

            df = df.sort_values('trade_date', ascending=True).tail(limit)
            history = []
            for _, row in df.iterrows():
                history.append({
                    'trade_date': str(row.get('trade_date', '')),
                    'open': cls._safe_float(row.get('open')),
                    'high': cls._safe_float(row.get('high')),
                    'low': cls._safe_float(row.get('low')),
                    'close': cls._safe_float(row.get('close')),
                    'vol': cls._safe_float(row.get('vol'), 0),
                    'amount': cls._safe_float(row.get('amount'), 0),
                })
            return history
        except Exception as exc:
            logger.warning(f'[DailySeries] Tushare daily fetch failed for {ts_code}: {exc}')
            return []

    @classmethod
    def _build_index_daily_series(
        cls,
        ts_code: str,
        realtime_quote: Optional[Dict[str, Any]] = None,
        limit: int = 60,
    ) -> Dict[str, Any]:
        """指数日线走势（优先本地数据库，其次Tushare index_daily）"""
        history = []
        try:
            conn, cursor = DatabaseUtils.connect_to_mysql()
            cursor.execute(
                "SELECT trade_date, open, high, low, close, vol, amount "
                "FROM stock_daily_history "
                "WHERE ts_code = %s "
                "ORDER BY trade_date DESC LIMIT %s",
                (ts_code, limit),
            )
            rows = cursor.fetchall()
            conn.close()
            for row in reversed(rows):
                history.append({
                    'trade_date': str(row[0]),
                    'open': cls._safe_float(row[1]),
                    'high': cls._safe_float(row[2]),
                    'low': cls._safe_float(row[3]),
                    'close': cls._safe_float(row[4]),
                    'vol': cls._safe_float(row[5], 0),
                    'amount': cls._safe_float(row[6], 0),
                })
        except Exception as exc:
            logger.warning(f'Local DB index history failed for {ts_code}: {exc}')

        # 检测本地数据是否过旧或不足，如果是则从 Tushare 补全
        need_tushare_fallback = len(history) < 10
        if not need_tushare_fallback and history:
            last_date_str = cls._safe_text(history[-1].get('trade_date'))
            last_date_normalized = last_date_str.replace('-', '')
            try:
                last_date = datetime.strptime(last_date_normalized, '%Y%m%d')
                if (datetime.now() - last_date).days > 3:
                    need_tushare_fallback = True
            except ValueError:
                pass

        if need_tushare_fallback:
            try:
                pro = cls._create_tushare_client()
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=limit * 2)).strftime('%Y%m%d')
                df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.sort_values('trade_date', ascending=True).tail(limit)
                    history = []
                    for _, row in df.iterrows():
                        history.append({
                            'trade_date': str(row.get('trade_date', '')),
                            'open': cls._safe_float(row.get('open')),
                            'high': cls._safe_float(row.get('high')),
                            'low': cls._safe_float(row.get('low')),
                            'close': cls._safe_float(row.get('close')),
                            'vol': cls._safe_float(row.get('vol'), 0),
                            'amount': cls._safe_float(row.get('amount'), 0),
                        })
            except Exception as exc:
                logger.warning(f'Tushare index_daily failed for {ts_code}: {exc}')

        merged_history = cls._merge_realtime_quote_into_daily_history(history, realtime_quote=realtime_quote)
        return {
            'series': cls._normalize_series(merged_history),
            'mode': 'daily',
            'source': 'index_daily',
            'message': '已加载指数日线走势。',
        }

    @classmethod
    def build_signals(cls, quote: Dict[str, Any]) -> List[Dict[str, str]]:
        pct_chg = quote.get('pct_chg') or 0
        amplitude = quote.get('amplitude') or 0
        open_price = quote.get('open')
        price = quote.get('price')
        pre_close = quote.get('pre_close') or 0
        turnover_rate = quote.get('turnover_rate') or 0

        price_level = 'neutral'
        price_status = '震荡观察'
        price_text = '价格波动相对温和，适合继续观察盘口变化。'
        if pct_chg >= 5:
            price_level = 'bullish'
            price_status = '强势拉升'
            price_text = '涨幅超过 5%，短线情绪较强，注意是否伴随放量。'
        elif pct_chg >= 2:
            price_level = 'bullish'
            price_status = '偏强运行'
            price_text = '当前处于明显上涨区间，可继续关注持续性。'
        elif pct_chg <= -5:
            price_level = 'bearish'
            price_status = '快速走弱'
            price_text = '跌幅较大，建议优先观察承接与止跌信号。'
        elif pct_chg <= -2:
            price_level = 'warning'
            price_status = '偏弱回落'
            price_text = '价格走弱，需留意是否跌破关键支撑位。'

        gap_status = '平开附近'
        gap_level = 'neutral'
        gap_text = '开盘价与昨收较接近，市场分歧尚不明显。'
        if open_price not in (None, 0) and pre_close not in (None, 0):
            gap_pct = round((open_price - pre_close) / pre_close * 100, 2)
            if gap_pct >= 2:
                gap_status = '高开关注'
                gap_level = 'bullish'
                gap_text = f'今开较昨收高开 {gap_pct}%，适合观察开盘后的量价承接。'
            elif gap_pct <= -2:
                gap_status = '低开承压'
                gap_level = 'warning'
                gap_text = f'今开较昨收低开 {abs(gap_pct)}%，需关注是否继续走弱。'

        active_level = 'neutral'
        active_status = '交投平稳'
        active_text = '当前换手与振幅水平中性，可继续跟踪。'
        if amplitude >= 6 or turnover_rate >= 8:
            active_level = 'bullish'
            active_status = '高活跃度'
            active_text = '振幅或换手偏高，说明市场关注度提升，适合重点盯盘。'
        elif amplitude >= 3 or turnover_rate >= 3:
            active_level = 'warning'
            active_status = '活跃升温'
            active_text = '价格波动开始放大，建议结合成交额变化观察。'

        trend_level = 'neutral'
        trend_status = '日内均衡'
        trend_text = '当前价格围绕开盘价波动，趋势尚未完全展开。'
        if price is not None and open_price not in (None, 0):
            intraday_pct = round((price - open_price) / open_price * 100, 2)
            if intraday_pct >= 2:
                trend_level = 'bullish'
                trend_status = '日内走强'
                trend_text = f'现价较开盘上涨 {intraday_pct}%，日内趋势偏强。'
            elif intraday_pct <= -2:
                trend_level = 'bearish'
                trend_status = '日内回落'
                trend_text = f'现价较开盘回落 {abs(intraday_pct)}%，需关注下方支撑。'

        return [
            {'title': '涨跌状态', 'status': price_status, 'text': price_text, 'level': price_level},
            {'title': '开盘信号', 'status': gap_status, 'text': gap_text, 'level': gap_level},
            {'title': '活跃度', 'status': active_status, 'text': active_text, 'level': active_level},
            {'title': '日内趋势', 'status': trend_status, 'text': trend_text, 'level': trend_level},
        ]

    @classmethod
    def _normalize_series(cls, raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for row in raw_rows:
            raw_label = cls._safe_text(cls._first_value(row, 'trade_time', 'TRADE_TIME', 'datetime', 'trade_date', 'DATE'))
            # 日线模式优先用 trade_date 作为标签，统一格式
            label = cls._normalize_date(raw_label) if raw_label and len(raw_label) <= 10 else raw_label
            items.append(
                {
                    'label': label,
                    'open': cls._safe_float(cls._first_value(row, 'open', 'OPEN')),
                    'high': cls._safe_float(cls._first_value(row, 'high', 'HIGH')),
                    'low': cls._safe_float(cls._first_value(row, 'low', 'LOW')),
                    'price': cls._safe_float(cls._first_value(row, 'close', 'CLOSE', 'price', 'PRICE')),
                    'volume': cls._safe_float(cls._first_value(row, 'vol', 'volume', 'VOLUME'), 0),
                    'amount': cls._safe_float(cls._first_value(row, 'amount', 'AMOUNT'), 0),
                }
            )
        return [item for item in items if item.get('price') is not None]

    @classmethod
    def get_price_series(
        cls,
        ts_code: str,
        freq: str = 'daily',
        realtime_quote: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        minute_freqs = {'1min', '5min', '15min', '30min', '60min'}
        higher_freqs = {'daily', 'weekly', 'monthly'}
        f = (freq or 'daily').strip()

        if f == 'daily':
            return cls._build_realtime_daily_series(ts_code, realtime_quote=realtime_quote)

        try:
            pro = cls._create_tushare_client()

            if f in minute_freqs:
                try:
                    df = pro.stk_mins(ts_code=ts_code, freq=f, limit=120)
                    if df is not None and not df.empty:
                        df = df.sort_values('trade_time', ascending=True)
                        return {
                            'series': cls._normalize_series(df.to_dict('records')),
                            'mode': 'minute',
                            'source': 'stk_mins',
                            'message': '分钟级走势已加载。',
                        }
                except Exception as exc_minute:
                    logger.warning(f'Minute data fetch failed for {ts_code}({f}): {exc_minute}')
                    if f != '60min':
                        try:
                            df60 = pro.stk_mins(ts_code=ts_code, freq='60min', limit=120)
                            if df60 is not None and not df60.empty:
                                df60 = df60.sort_values('trade_time', ascending=True)
                                return {
                                    'series': cls._normalize_series(df60.to_dict('records')),
                                    'mode': 'minute',
                                    'source': 'stk_mins',
                                    'message': f'{f} 接口不可用，已降级为 60min 走势。{exc_minute}',
                                }
                        except Exception as exc60:
                            logger.warning(f'60min fallback failed for {ts_code}: {exc60}')

            if f in higher_freqs:
                if f == 'daily':
                    ddf = pro.daily(ts_code=ts_code)
                elif f == 'weekly':
                    ddf = pro.weekly(ts_code=ts_code)
                else:
                    ddf = pro.monthly(ts_code=ts_code)

                if ddf is not None and not ddf.empty:
                    ddf = ddf.sort_values('trade_date', ascending=True)
                    return {
                        'series': cls._normalize_series(ddf.to_dict('records')),
                        'mode': f,
                        'source': f'tushare_{f}',
                        'message': f'{f} 级走势已加载。',
                    }
        except Exception as exc:
            logger.warning(f'Price series fetch failed for {ts_code}({f}): {exc}')
            minute_error = str(exc)
        else:
            minute_error = ''

        daily_payload = cls._build_realtime_daily_series(ts_code, realtime_quote=realtime_quote)
        daily_payload['message'] = f"分钟级接口暂不可用，已降级为实时日线走势。{minute_error}".strip()
        return daily_payload


    @classmethod
    def get_dashboard(cls, user_id: Optional[int], raw_codes: str = '', include_detail: bool = False) -> Dict[str, Any]:
        """获取监控面板数据，包含市场指数和自选股

        优化：
        1. 行情和指数并发获取，market_overview 异步加载（不阻塞）
        2. 支持 include_detail 参数，直接包含选中股票的详情，减少二次请求
        """
        watchlist = cls._get_user_watchlist(user_id)
        watchlist_items = [item.to_dict() for item in watchlist]
        codes = cls._pick_codes(user_id, raw_codes)

        logger.debug(
            f'[MonitorDashboard] user_id={user_id}, raw_codes={raw_codes!r}, '
            f'watchlist_count={len(watchlist)}, picked_codes={codes}'
        )

        # 并发获取行情和指数（快速，<1秒），market_overview 由前端单独请求
        quote_payload = {'quotes': [], 'source': 'empty', 'message': ''}
        market_quotes = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_quotes = executor.submit(cls._load_realtime_quotes, codes)
            future_market = executor.submit(cls._load_market_index_quotes)

            try:
                quote_payload = future_quotes.result(timeout=15)
            except Exception as exc:
                logger.warning(f'[Dashboard] Quotes fetch failed: {exc}')

            try:
                market_quotes = future_market.result(timeout=15)
            except Exception as exc:
                logger.warning(f'[Dashboard] Market index quotes failed: {exc}')

        selected_ts_code = quote_payload.get('quotes', [{}])[0].get('ts_code') if quote_payload.get('quotes') else ''

        result = {
            'codes': codes,
            'quotes': quote_payload.get('quotes', []),
            'quote_source': quote_payload.get('source'),
            'quote_message': quote_payload.get('message'),
            'selected_ts_code': selected_ts_code,
            'market_quotes': market_quotes,
            'market_overview': {},  # 前端单独请求 /api/market/overview
            'watchlist_items': watchlist_items,
            'watchlist_count': len(watchlist_items),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # 可选：直接包含选中股票的详情，避免前端二次请求
        if include_detail and selected_ts_code:
            try:
                detail = cls.get_stock_detail(
                    user_id=user_id,
                    ts_code=selected_ts_code,
                    freq='daily',
                    preloaded_quotes=quote_payload.get('quotes', []),
                )
                result['stock_detail'] = detail
            except Exception as exc:
                logger.warning(f'[Dashboard] Stock detail inclusion failed: {exc}')

        return result

    @classmethod
    def _load_market_index_quotes(cls) -> List[Dict[str, Any]]:
        """加载市场指数的实时行情（Akshare优先 → Tushare降级 → MarketOverview兜底）"""
        cached = _cache.get('market_index_quotes')
        if cached is not None:
            return cached

        index_ts_map = {item['ts_code']: item['name'] for item in MarketOverviewService.INDEX_ITEMS}
        codes = cls.MARKET_INDEX_CODES
        name_map = {code: index_ts_map.get(code, code) for code in codes}

        quotes = []

        # ========== ① 优先：Akshare（新浪快照，免费实时） ==========
        try:
            ak_result = AkshareService.get_realtime_quotes(codes)
            ak_quotes = ak_result.get('quotes', [])
            if ak_quotes and any(q.get('price') is not None for q in ak_quotes):
                for code in codes:
                    matched = next((q for q in ak_quotes if q.get('ts_code') == code), None)
                    if matched and matched.get('price') is not None:
                        quotes.append(cls._build_quote_item(
                            ts_code=code,
                            name=name_map.get(code, code),
                            price=matched.get('price'),
                            pre_close=matched.get('pre_close'),
                            open_price=matched.get('open'),
                            high=matched.get('high'),
                            low=matched.get('low'),
                            volume=matched.get('volume'),
                            amount=matched.get('amount'),
                            trade_date=matched.get('trade_date'),
                            trade_time=matched.get('trade_time'),
                            turnover_rate=matched.get('turnover_rate'),
                            source='sina_realtime',
                        ))
                    else:
                        quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='sina_realtime'))
                _cache.set('market_index_quotes', quotes, ttl=cls.CACHE_TTL_QUOTES)
                return quotes
        except Exception as exc:
            logger.warning(f'Akshare market index quotes failed: {exc}')

        # ========== ② 降级：Tushare realtime_quote ==========
        try:
            ts_mod = DatabaseUtils.init_tushare_realtime()
            code_str = ','.join(codes)
            df = ts_mod.realtime_quote(ts_code=code_str)
            if df is not None and not df.empty:
                for code in codes:
                    row_df = df[df['TS_CODE'] == code] if 'TS_CODE' in df.columns else pd.DataFrame()
                    if not row_df.empty:
                        row = row_df.iloc[0]
                        quotes.append(
                            cls._build_quote_item(
                                ts_code=code,
                                name=name_map.get(code, code),
                                price=row.get('PRICE'),
                                pre_close=row.get('PRE_CLOSE'),
                                open_price=row.get('OPEN'),
                                high=row.get('HIGH'),
                                low=row.get('LOW'),
                                volume=row.get('VOLUME'),
                                amount=row.get('AMOUNT'),
                                trade_date=row.get('DATE'),
                                trade_time=row.get('TIME'),
                                source='realtime_quote',
                            )
                        )
                    else:
                        quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='realtime_quote'))
                _cache.set('market_index_quotes', quotes, ttl=cls.CACHE_TTL_QUOTES)
                return quotes
        except Exception as exc:
            logger.warning(f'Tushare realtime_quote for market indices failed: {exc}')

        # ========== ③ 兜底：MarketOverviewService ==========
        overview = MarketOverviewService.get_market_overview()
        for item in overview.get('items', []):
            if item.get('ts_code') in codes:
                quotes.append(cls._build_quote_item(
                    ts_code=item['ts_code'],
                    name=item.get('name', item['ts_code']),
                    price=item.get('close'),
                    pre_close=None,
                    open_price=None,
                    high=None,
                    low=None,
                    volume=item.get('vol'),
                    amount=item.get('amount'),
                    trade_date=item.get('trade_date'),
                    trade_time=None,
                    source='market_overview',
                ))
        # 补充缺失的指数
        existing_codes = {q['ts_code'] for q in quotes}
        for code in codes:
            if code not in existing_codes:
                quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='market_overview'))

        _cache.set('market_index_quotes', quotes, ttl=cls.CACHE_TTL_QUOTES)
        return quotes

    @classmethod
    def get_intraday_series(cls, ts_code: str, period: str = '1') -> Dict[str, Any]:
        """获取分时走势数据（Akshare优先 → Tushare stk_mins降级）

        Args:
            ts_code: 股票代码，如 600519.SH
            period: 分钟频率 '1' / '5' / '15' / '30' / '60'

        Returns:
            {
                'intraday': [{'time': '09:31', 'close': 1458.5, 'volume': 3600, ...}],
                'pre_close': 1450.0,
                'date': '2026-04-24',
                'source': 'akshare_sina_minute',
                'message': '...',
            }
        """
        normalized_code = cls.normalize_ts_code(ts_code)
        cache_key = f'intraday_{normalized_code}_{period}'
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        result = None

        # ========== ① 优先：Akshare stock_zh_a_minute ==========
        try:
            ak_result = AkshareService.get_intraday_minute(
                symbol=normalized_code, period=period,
            )
            if ak_result.get('data'):
                result = {
                    'intraday': ak_result['data'],
                    'pre_close': ak_result.get('pre_close'),
                    'date': ak_result.get('date', ''),
                    'source': ak_result.get('source', 'akshare_sina_minute'),
                    'message': ak_result.get('message', '分时数据已加载'),
                }
        except Exception as exc:
            logger.warning(f'Akshare intraday failed for {normalized_code}: {exc}')

        # ========== ② 降级：Tushare stk_mins ==========
        if not result or not result.get('intraday'):
            try:
                pro = cls._create_tushare_client()
                freq_map = {'1': '1min', '5': '5min', '15': '15min', '30': '30min', '60': '60min'}
                ts_freq = freq_map.get(period, '1min')
                df = pro.stk_mins(ts_code=normalized_code, freq=ts_freq, limit=500)
                if df is not None and not df.empty:
                    df = df.sort_values('trade_time', ascending=True)
                    # 只取最近交易日
                    df['trade_date'] = df['trade_time'].str[:10]
                    latest_date = df['trade_date'].max()
                    df_today = df[df['trade_date'] == latest_date]

                    records = []
                    for _, row in df_today.iterrows():
                        time_str = cls._safe_text(row.get('trade_time', ''))
                        # 取 HH:MM 部分
                        if len(time_str) >= 16:
                            time_str = time_str[11:16]
                        records.append({
                            'time': time_str,
                            'open': cls._safe_float(row.get('open')),
                            'high': cls._safe_float(row.get('high')),
                            'low': cls._safe_float(row.get('low')),
                            'close': cls._safe_float(row.get('close')),
                            'volume': cls._safe_float(row.get('vol'), 0),
                            'amount': cls._safe_float(row.get('amount'), 0),
                        })

                    if records:
                        pre_close = cls._safe_float(records[0].get('open'))
                        # 尝试从缓存获取更准确的昨收价（避免再次网络请求）
                        cache_key = f'realtime_quotes_{normalized_code}'
                        cached_quotes = _cache.get(cache_key)
                        if cached_quotes:
                            cached_quote = (cached_quotes.get('quotes') or [{}])[0]
                            if cached_quote.get('pre_close') is not None:
                                pre_close = cached_quote['pre_close']
                        else:
                            # 缓存中没有，尝试从行情缓存中获取
                            for ck in [f'realtime_quotes_{normalized_code}',
                                       f'realtime_quotes_{",".join(sorted([normalized_code]))}']:
                                cached_data = _cache.get(ck)
                                if cached_data:
                                    cached_quote = (cached_data.get('quotes') or [{}])[0]
                                    if cached_quote.get('pre_close') is not None:
                                        pre_close = cached_quote['pre_close']
                                        break

                        result = {
                            'intraday': records,
                            'pre_close': pre_close,
                            'date': latest_date,
                            'source': 'tushare_stk_mins',
                            'message': '分时数据已加载（Tushare）',
                        }
            except Exception as exc:
                logger.warning(f'Tushare stk_mins failed for {normalized_code}: {exc}')

        if not result:
            # ========== ③ 最终降级：从数据库日线回退 ==========
            try:
                from app import db
                from app.models.stock import StockDaily
                latest_daily = db.session.query(StockDaily).filter(
                    StockDaily.ts_code == normalized_code
                ).order_by(StockDaily.trade_date.desc()).first()

                if latest_daily:
                    pre_close = cls._safe_float(latest_daily.pre_close)
                    records = [{
                        'time': '09:30',
                        'open': cls._safe_float(latest_daily.open),
                        'high': cls._safe_float(latest_daily.high),
                        'low': cls._safe_float(latest_daily.low),
                        'close': cls._safe_float(latest_daily.close),
                        'volume': cls._safe_float(latest_daily.vol, 0),
                        'amount': cls._safe_float(latest_daily.amount, 0),
                    }]
                    result = {
                        'intraday': records,
                        'pre_close': pre_close or cls._safe_float(latest_daily.open),
                        'date': cls._safe_text(latest_daily.trade_date),
                        'source': 'daily_fallback',
                        'message': f'非交易时间，展示最近交易日({cls._safe_text(latest_daily.trade_date)})数据',
                    }
            except Exception as exc:
                logger.warning(f'Daily fallback failed for {normalized_code}: {exc}')

        if not result:
            result = {
                'intraday': [],
                'pre_close': None,
                'date': '',
                'source': 'empty',
                'message': '分时数据暂不可用，请检查网络或在交易时间段重试。',
            }

        # 收盘后缓存到次日8:30（约12小时），盘中15秒刷新
        from datetime import datetime, time as dt_time
        now = datetime.now()
        market_close_time = dt_time(15, 30)
        if now.time() > market_close_time or now.weekday() >= 5:
            cache_ttl = 43200  # 12小时
        else:
            cache_ttl = 15
        _cache.set(cache_key, result, ttl=cache_ttl)
        return result

    @classmethod
    def get_stock_detail(cls, user_id: Optional[int], ts_code: str, freq: str = 'daily',
                         preloaded_quotes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        normalized_code = cls.normalize_ts_code(ts_code)
        if not normalized_code:
            raise ValueError('Invalid ts_code')

        normalized_freq = 'daily'

        # 优先从已加载行情中查找，避免重复请求
        quote = None
        if preloaded_quotes:
            quote = next((q for q in preloaded_quotes if q.get('ts_code') == normalized_code), None)

        quote_payload = None
        if quote is None:
            quote_payload = cls._load_realtime_quotes([normalized_code])
            quote = (quote_payload.get('quotes') or [{}])[0]
        else:
            quote_payload = {'quotes': [quote], 'source': quote.get('source', 'preloaded'), 'message': '复用已加载行情'}

        series_payload = cls.get_price_series(normalized_code, freq=normalized_freq, realtime_quote=quote)
        watch_codes = {item.ts_code for item in cls._get_user_watchlist(user_id)}

        index_ts_map = {item['ts_code']: item['name'] for item in MarketOverviewService.INDEX_ITEMS}
        is_index = normalized_code in index_ts_map

        stock_info = {}
        if not is_index:
            stock_info = StockService.get_stock_info(normalized_code) or {}
        else:
            stock_info = {
                'ts_code': normalized_code,
                'name': index_ts_map.get(normalized_code, normalized_code),
                'industry': '指数',
                'area': '',
            }

        return {
            'quote': quote,
            'quote_source': quote_payload.get('source'),
            'quote_message': quote_payload.get('message'),
            'series': series_payload.get('series', []),
            'series_mode': series_payload.get('mode'),
            'series_source': series_payload.get('source'),
            'series_message': series_payload.get('message'),
            'signals': cls.build_signals(quote) if not is_index else cls._build_index_signals(quote),
            'stock_info': stock_info,
            'is_watchlist': normalized_code in watch_codes,
            'is_index': is_index,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @classmethod
    def get_realtime_ranking(cls, sort_by: str = 'pct_change', limit: int = 20, src: str = 'sina') -> Dict[str, Any]:
        """获取实时涨跌幅排名

        数据源优先级：
        ① 新浪财经 HTTP API（免费、快速、直接请求）
        ② Tushare realtime_list（需验证token，可能失败）
        ③ Akshare stock_zh_a_spot（Sina 爬虫，慢但可靠）

        Args:
            sort_by: 排序字段，可选 pct_change(涨跌幅) / turnover_rate(换手率) / amount(成交额)
            limit: 返回条数，默认20
            src: 数据源标识（sina/dc），实际数据源按优先级自动选择
        """
        cache_key = f'realtime_ranking_{sort_by}'
        # 排名数据使用独立的较长缓存
        ranking_cache = _cache.get(cache_key)
        if ranking_cache is not None:
            return ranking_cache

        result = None

        # ========== ① 优先：直接请求新浪财经 API（最快） ==========
        result = cls._fetch_ranking_from_sina_direct(sort_by=sort_by, limit=limit)

        # ========== ② 降级：Tushare realtime_list ==========
        if not result or not result.get('success'):
            result = cls._fetch_ranking_from_tushare(sort_by=sort_by, limit=limit, src=src)

        # ========== ③ 兜底：Akshare ==========
        if not result or not result.get('success'):
            result = cls._fetch_ranking_from_akshare(sort_by=sort_by, limit=limit)

        if result is None:
            result = {
                'success': False,
                'message': '所有数据源均不可用，请检查网络连接或在交易时间段重试。',
                'sort_by': sort_by,
                'src': src,
                'top_gainers': [],
                'top_losers': [],
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        _cache.set(cache_key, result, ttl=cls.CACHE_TTL_RANKING)
        return result

    @classmethod
    def _fetch_ranking_from_sina_direct(cls, sort_by: str = 'pct_change', limit: int = 20) -> Optional[Dict[str, Any]]:
        """直接请求新浪财经 API 获取涨跌幅排名（快速，约0.5秒）"""
        try:
            import requests as req

            # 新浪API排序字段映射
            sina_sort_map = {
                'pct_change': 'changepercent',
                'turnover_rate': 'turnoverratio',
                'amount': 'amount',
            }
            sina_sort = sina_sort_map.get(sort_by, 'changepercent')

            session = req.Session()
            session.trust_env = False  # 绕过系统代理

            url = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
            base_params = {
                'num': str(min(limit, 80)),
                'node': 'hs_a',
                '_s_r_a': 'page',
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://vip.stock.finance.sina.com.cn/',
            }

            # 涨幅榜（降序）
            params_up = {**base_params, 'page': '1', 'sort': sina_sort, 'asc': '0'}
            r_up = session.get(url, params=params_up, headers=headers, timeout=10)
            if r_up.status_code != 200 or not r_up.text.strip():
                return None

            import json as _json
            data_up = _json.loads(r_up.text)
            if not data_up:
                return None

            # 跌幅榜（升序）
            params_down = {**base_params, 'page': '1', 'sort': sina_sort, 'asc': '1'}
            r_down = session.get(url, params=params_down, headers=headers, timeout=10)
            data_down = _json.loads(r_down.text) if r_down.status_code == 200 and r_down.text.strip() else []

            # 转换格式
            top_gainers = cls._format_sina_ranking_rows(data_up[:limit])
            top_losers = cls._format_sina_ranking_rows(data_down[:limit]) if data_down else []

            return {
                'success': True,
                'message': '实时涨跌幅排名已加载（新浪财经 API）。',
                'sort_by': sort_by,
                'src': 'sina_api',
                'total_count': len(data_up),
                'top_gainers': top_gainers,
                'top_losers': top_losers,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as exc:
            logger.warning(f'Sina direct ranking failed: {exc}')
            return None

    @classmethod
    def _format_sina_ranking_rows(cls, rows: list) -> List[Dict[str, Any]]:
        """将新浪API返回的原始数据格式化为标准格式"""
        result = []
        for row in rows:
            # 新浪symbol格式: sh600000, sz000001, bj430047
            symbol = cls._safe_text(row.get('symbol', ''))
            code = cls._safe_text(row.get('code', ''))
            if symbol.startswith('sh'):
                ts_code = f'{code}.SH'
            elif symbol.startswith('sz'):
                ts_code = f'{code}.SZ'
            elif symbol.startswith('bj'):
                ts_code = f'{code}.BJ'
            else:
                ts_code = cls.normalize_ts_code(code)

            result.append({
                'ts_code': ts_code,
                'name': cls._safe_text(row.get('name', '')),
                'price': cls._safe_float(row.get('trade')),
                'pct_change': cls._safe_float(row.get('changepercent')),
                'change': cls._safe_float(row.get('pricechange')),
                'open': cls._safe_float(row.get('open')),
                'high': cls._safe_float(row.get('high')),
                'low': cls._safe_float(row.get('low')),
                'close': cls._safe_float(row.get('settlement')),  # 昨收
                'volume': cls._safe_float(row.get('volume'), 0),
                'amount': cls._safe_float(row.get('amount'), 0),
                'turnover_rate': cls._safe_float(row.get('turnoverratio')),
                'pe': cls._safe_float(row.get('per'), 0),
                'pb': cls._safe_float(row.get('pb')),
                'total_mv': cls._safe_float(row.get('mktcap'), 0),
                'float_mv': cls._safe_float(row.get('nmc'), 0),
            })
        return result

    @classmethod
    def _fetch_ranking_from_tushare(cls, sort_by: str = 'pct_change', limit: int = 20, src: str = 'dc') -> Optional[Dict[str, Any]]:
        """通过 Tushare realtime_list 获取排名（降级方案）"""
        sort_key_map = {
            'pct_change': 'pct_change',
            'pct_chg': 'pct_change',
            'turnover_rate': 'turnover_rate',
            'amount': 'amount',
            'vol_ratio': 'vol_ratio',
        }
        actual_sort = sort_key_map.get(sort_by, 'pct_change')

        try:
            ts_mod = DatabaseUtils.init_tushare_realtime()
            # 绕过 require_permission 装饰器，直接调用底层函数
            if src == 'sina':
                from tushare.stock.rtq import get_stock_all_a_sina
                df = get_stock_all_a_sina(interval=1, page_count=2, proxies={})
            else:
                from tushare.stock.rtq import get_stock_all_a_dc
                df = get_stock_all_a_dc(page_count=2, proxies={})

            if df is None or df.empty:
                return None

            df.columns = [c.lower() for c in df.columns]
            if 'pct_change' not in df.columns and 'pct_chg' in df.columns:
                df = df.rename(columns={'pct_chg': 'pct_change'})

            numeric_cols = ['price', 'pct_change', 'change', 'volume', 'amount', 'swing',
                            'low', 'high', 'open', 'close', 'turnover_rate', 'vol_ratio']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            sort_col = actual_sort if actual_sort in df.columns else 'pct_change'
            if sort_col not in df.columns:
                return None

            df_sorted = df.sort_values(by=sort_col, ascending=False, na_position='last')
            top_gainers = cls._format_ranking_rows(df_sorted.head(limit), src=src)

            df_losers = df.sort_values(by=sort_col, ascending=True, na_position='last')
            top_losers = cls._format_ranking_rows(df_losers.head(limit), src=src)

            return {
                'success': True,
                'message': '实时涨跌幅排名已加载（Tushare realtime_list）。',
                'sort_by': actual_sort,
                'src': f'tushare_{src}',
                'total_count': len(df),
                'top_gainers': top_gainers,
                'top_losers': top_losers,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as exc:
            logger.warning(f'Tushare ranking failed: {exc}')
            return None

    @classmethod
    def _fetch_ranking_from_akshare(cls, sort_by: str = 'pct_change', limit: int = 20) -> Optional[Dict[str, Any]]:
        """通过 Akshare 获取排名（兜底方案，较慢）"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot()

            if df is None or df.empty:
                return None

            # Akshare 返回中文列名，映射到标准字段
            col_map = {
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌额': 'change',
                '涨跌幅': 'pct_change',
                '今开': 'open',
                '最高': 'high',
                '最低': 'low',
                '昨收': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
                '时间戳': 'time',
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            # 构造 ts_code
            if 'code' in df.columns:
                df['ts_code'] = df['code'].apply(cls.normalize_ts_code)

            # 数值转换
            for col in ['price', 'pct_change', 'change', 'open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            sort_col = sort_by if sort_by in df.columns else 'pct_change'
            if sort_col not in df.columns:
                return None

            df_sorted = df.sort_values(by=sort_col, ascending=False, na_position='last')
            top_gainers = cls._format_akshare_ranking_rows(df_sorted.head(limit))

            df_losers = df.sort_values(by=sort_col, ascending=True, na_position='last')
            top_losers = cls._format_akshare_ranking_rows(df_losers.head(limit))

            return {
                'success': True,
                'message': '实时涨跌幅排名已加载（Akshare 新浪数据源）。',
                'sort_by': sort_by,
                'src': 'akshare_sina',
                'total_count': len(df),
                'top_gainers': top_gainers,
                'top_losers': top_losers,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as exc:
            logger.warning(f'Akshare ranking failed: {exc}')
            return None

    @classmethod
    def _format_akshare_ranking_rows(cls, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """将 Akshare 排名 DataFrame 行格式化"""
        rows = []
        for _, row in df.iterrows():
            rows.append({
                'ts_code': cls._safe_text(row.get('ts_code', '')),
                'name': cls._safe_text(row.get('name', '')),
                'price': cls._safe_float(row.get('price')),
                'pct_change': cls._safe_float(row.get('pct_change')),
                'change': cls._safe_float(row.get('change')),
                'open': cls._safe_float(row.get('open')),
                'high': cls._safe_float(row.get('high')),
                'low': cls._safe_float(row.get('low')),
                'close': cls._safe_float(row.get('close')),
                'volume': cls._safe_float(row.get('volume'), 0),
                'amount': cls._safe_float(row.get('amount'), 0),
                'turnover_rate': None,
            })
        return rows

    @classmethod
    def _format_ranking_rows(cls, df: pd.DataFrame, src: str = 'dc') -> List[Dict[str, Any]]:
        """将 Tushare ranking DataFrame 行格式化为前端友好的字典列表"""
        rows = []
        for _, row in df.iterrows():
            item = {
                'ts_code': cls._safe_text(row.get('ts_code', '')),
                'name': cls._safe_text(row.get('name', '')),
                'price': cls._safe_float(row.get('price')),
                'pct_change': cls._safe_float(row.get('pct_change')),
                'change': cls._safe_float(row.get('change')),
                'open': cls._safe_float(row.get('open')),
                'high': cls._safe_float(row.get('high')),
                'low': cls._safe_float(row.get('low')),
                'close': cls._safe_float(row.get('close')),
                'volume': cls._safe_float(row.get('volume'), 0),
                'amount': cls._safe_float(row.get('amount'), 0),
                'swing': cls._safe_float(row.get('swing')),
                'turnover_rate': cls._safe_float(row.get('turnover_rate')),
                'vol_ratio': cls._safe_float(row.get('vol_ratio')),
            }
            if src == 'dc':
                item.update({
                    'pe': cls._safe_float(row.get('pe'), 0),
                    'pb': cls._safe_float(row.get('pb')),
                    'total_mv': cls._safe_float(row.get('total_mv'), 0),
                    'float_mv': cls._safe_float(row.get('float_mv'), 0),
                })
            rows.append(item)
        return rows

    @classmethod
    def _build_index_signals(cls, quote: Dict[str, Any]) -> List[Dict[str, str]]:
        """指数专用信号"""
        pct_chg = quote.get('pct_chg') or 0
        level = 'bullish' if pct_chg >= 1 else 'bearish' if pct_chg <= -1 else 'neutral'
        status = '偏强' if pct_chg >= 1 else '偏弱' if pct_chg <= -1 else '震荡'

        return [
            {'title': '指数涨跌', 'status': status, 'text': f'当前涨跌幅 {pct_chg:.2f}%，{"市场情绪偏积极" if pct_chg > 0 else "市场情绪偏谨慎" if pct_chg < 0 else "市场多空均衡"}。', 'level': level},
            {'title': '数据来源', 'status': '实时数据', 'text': '指数行情来自实时快照或最近交易日数据。', 'level': 'neutral'},
        ]
