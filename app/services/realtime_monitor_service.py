from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import tushare as ts
from loguru import logger

from app.models import StockBasic, UserWatchlist
from app.services.market_overview_service import MarketOverviewService
from app.services.stock_service import StockService
from app.utils.db_utils import DatabaseUtils


class RealtimeMonitorService:
    DEFAULT_CODES = ['000001.SZ', '600519.SH', '300750.SZ']
    MAX_CODES = 12
    SUPPORTED_FREQS = {'1min', '5min', '15min', '30min', '60min'}

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
        DatabaseUtils.reload_from_env()
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
        return {stock.ts_code: stock.name for stock in stocks}

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
        if not codes:
            return {'quotes': [], 'source': 'empty', 'message': 'No codes provided.'}

        errors: List[str] = []
        code_str = ','.join(codes)

        try:
            pro = cls._create_tushare_client()
            df = pro.realtime_quote(ts_code=code_str)
            if df is not None and not df.empty:
                quotes = cls._normalize_realtime_quotes(df.to_dict('records'), codes)
                if any(item.get('price') is not None for item in quotes):
                    return {
                        'quotes': quotes,
                        'source': 'realtime_quote',
                        'message': '已通过 Tushare 实时行情接口加载数据。',
                    }
        except Exception as exc:
            logger.warning(f'Realtime quote via pro failed: {exc}')
            errors.append(str(exc))

        try:
            DatabaseUtils.reload_from_env()
            ts.set_token(DatabaseUtils._tushare_token)
            pro = ts.pro_api()
            if DatabaseUtils._tushare_proxy_url:
                pro._DataApi__http_url = DatabaseUtils._tushare_proxy_url
            df = ts.realtime_quote(ts_code=code_str)
            if df is not None and not df.empty:
                quotes = cls._normalize_realtime_quotes(df.to_dict('records'), codes)
                if any(item.get('price') is not None for item in quotes):
                    return {
                        'quotes': quotes,
                        'source': 'realtime_quote',
                        'message': '已通过 Tushare 实时行情接口加载数据。',
                    }
        except Exception as exc:
            logger.warning(f'Realtime quote via module call failed: {exc}')
            errors.append(str(exc))

        fallback = cls._load_latest_trade_quotes(codes)
        fallback_message = '实时接口暂不可用，已自动降级为最近交易日监控数据。'
        if errors:
            fallback_message = f"{fallback_message} 原因：{errors[-1]}"
        fallback['message'] = fallback_message
        return fallback

    @classmethod
    def _load_latest_trade_quotes(cls, codes: List[str]) -> Dict[str, Any]:
        name_map = cls._get_name_map(codes)
        quotes: List[Dict[str, Any]] = []

        try:
            pro = cls._create_tushare_client()
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=20)).strftime('%Y%m%d')

            for code in codes:
                daily_df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
                if daily_df is None or daily_df.empty:
                    quotes.append(cls._build_quote_item(code, name_map.get(code, code), None, None, None, None, None, None, None, None, None, source='latest_trade_day'))
                    continue

                daily_df = daily_df.sort_values('trade_date', ascending=False)
                latest = daily_df.iloc[0]
                turnover_rate = None
                latest_trade_date = cls._safe_text(latest.get('trade_date'))
                try:
                    basic_df = pro.daily_basic(ts_code=code, trade_date=latest_trade_date)
                    if basic_df is not None and not basic_df.empty:
                        turnover_rate = basic_df.iloc[0].get('turnover_rate')
                except Exception as exc:
                    logger.warning(f'Daily basic fetch failed for {code}: {exc}')

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
                        trade_date=latest_trade_date,
                        trade_time='latest_trade_day',
                        turnover_rate=turnover_rate,
                        source='latest_trade_day',
                    )
                )

            return {
                'quotes': quotes,
                'source': 'latest_trade_day',
                'message': '已切换到最近交易日数据。',
            }
        except Exception as exc:
            logger.warning(f'Latest trade quote via Tushare failed: {exc}')

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
            label = cls._safe_text(cls._first_value(row, 'trade_time', 'TRADE_TIME', 'datetime', 'trade_date', 'DATE'))
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
    def get_price_series(cls, ts_code: str, freq: str = '1min') -> Dict[str, Any]:
        # 支持的频率：分钟级（1min/5min/15min/30min/60min）或更高粒度（日/周/月）
        minute_freqs = {'1min', '5min', '15min', '30min', '60min'}
        higher_freqs = {'daily', 'weekly', 'monthly'}
        f = (freq or '1min').strip()

        try:
            pro = cls._create_tushare_client()

            # 1) 分钟级优先：先按指定分钟级取，不行则自动退到 60min
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
                    # 尝试 60min 作为降级
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

            # 2) 更高粒度：daily/weekly/monthly
            if f in higher_freqs:
                if f == 'daily':
                    ddf = pro.daily(ts_code=ts_code)
                elif f == 'weekly':
                    ddf = pro.weekly(ts_code=ts_code)
                else:  # 'monthly'
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

        # 3) 最终降级：使用本地日线历史（数据库/缓存）
        history = list(reversed(StockService.get_daily_history(ts_code, limit=30)))
        return {
            'series': cls._normalize_series(history),
            'mode': 'daily',
            'source': 'stock_daily_history',
            'message': f'分钟级接口暂不可用，已降级为日线走势。{minute_error}'.strip(),
        }


    @classmethod
    def get_dashboard(cls, user_id: Optional[int], raw_codes: str = '') -> Dict[str, Any]:
        codes = cls._pick_codes(user_id, raw_codes)
        watchlist_items = [item.to_dict() for item in cls._get_user_watchlist(user_id)]
        quote_payload = cls._load_realtime_quotes(codes)
        market_overview = MarketOverviewService.get_market_overview()

        return {
            'codes': codes,
            'quotes': quote_payload.get('quotes', []),
            'quote_source': quote_payload.get('source'),
            'quote_message': quote_payload.get('message'),
            'selected_ts_code': quote_payload.get('quotes', [{}])[0].get('ts_code') if quote_payload.get('quotes') else '',
            'market_overview': market_overview,
            'watchlist_items': watchlist_items,
            'watchlist_count': len(watchlist_items),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    @classmethod
    def get_stock_detail(cls, user_id: Optional[int], ts_code: str, freq: str = '1min') -> Dict[str, Any]:
        normalized_code = cls.normalize_ts_code(ts_code)
        if not normalized_code:
            raise ValueError('Invalid ts_code')

        quote_payload = cls._load_realtime_quotes([normalized_code])
        quote = (quote_payload.get('quotes') or [{}])[0]
        series_payload = cls.get_price_series(normalized_code, freq=freq)
        watch_codes = {item.ts_code for item in cls._get_user_watchlist(user_id)}

        return {
            'quote': quote,
            'quote_source': quote_payload.get('source'),
            'quote_message': quote_payload.get('message'),
            'series': series_payload.get('series', []),
            'series_mode': series_payload.get('mode'),
            'series_source': series_payload.get('source'),
            'series_message': series_payload.get('message'),
            'signals': cls.build_signals(quote),
            'stock_info': StockService.get_stock_info(normalized_code),
            'is_watchlist': normalized_code in watch_codes,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
