# -*- coding: utf-8 -*-
"""Akshare 数据服务 - 封装免费 A 股数据接口，作为 Tushare 的补充/替代

主要用途：
  1. 实时行情监控（免费、无需积分）
  2. 大盘指数实时数据（上证/深证/创业板等）
  3. 个股历史 K 线数据
  4. 涨跌/涨停/跌停统计

接口来源：东方财富(EM) / 新浪(Sina)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd
import requests
from loguru import logger

# ======================== 代理处理 ========================
# Akshare 底层使用 curl_cffi，网络请求可能受以下代理方式影响：
#
# 方式 1: 系统代理（旧模式）
#   HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings
#   流量路径：应用 → 127.0.0.1:7890 → Clash → 目标
#   解决：清除环境变量 + 注册表代理可绕过
#
# 方式 2: TUN 虚拟网卡模式（Clash Verge / Clash Meta 等）
#   流量路径：应用 → 虚拟网卡(UTUN) → Clash规则引擎 → 目标
#   ⚠️ 清除环境变量无效！流量在网卡层就被劫持
#   解决：在 Clash 规则中添加 *.eastmoney.com 为 DIRECT（直连）
#
# 本模块提供：
#   - detect_proxy_mode()     检测当前代理类型
#   - call_with_no_proxy()    自动重试（清除环境变量后重试一次）
#   - _NoProxyContext         上下文管理器，临时清理代理环境变量
#
# 推荐的 Clash 规则配置（添加到 rules 列表最前面）：
#   - DOMAIN-SUFFIX,eastmoney.com,DIRECT
#   - DOMAIN-SUFFIX,push2.eastmoney.com,DIRECT
#   - DOMAIN-SUFFIX,push2his.eastmoney.com,DIRECT


def detect_proxy_mode() -> Dict[str, Any]:
    """检测当前系统的代理模式

    Returns:
        {
            'mode': 'none' | 'system_proxy' | 'tun' | 'unknown',
            'env_proxies': {...},
            'registry_proxy': {...},
            'tun_adapters': [...],      # 检测到的虚拟网卡名称
            'recommendation': str,       # 修复建议
        }
    """
    info = {
        'mode': 'unknown',
        'env_proxies': {},
        'registry_proxy': {},
        'tun_adapters': [],
        'recommendation': '',
    }

    # 1) 环境变量代理
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']:
        val = os.environ.get(key)
        if val:
            info['env_proxies'][key] = val

    # 2) Windows 注册表代理
    try:
        import winreg
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        )
        enable, _ = winreg.QueryValueEx(reg_key, 'ProxyEnable')
        server, _ = winreg.QueryValueEx(reg_key, 'ProxyServer')
        winreg.CloseKey(reg_key)
        info['registry_proxy'] = {'enable': bool(enable), 'server': server}
    except Exception:
        pass

    # 3) TUN 虚拟网卡检测
    tun_names = {'utun', 'tun', 'wintun', 'cloudflare-warp', 'clash-tun',
                 'meta-tun', 'verge-tun', 'clash-meta'}
    try:
        import subprocess
        result = subprocess.run(
            ['netsh', 'interface', 'show', 'interface'],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )
        output = (result.stdout or '' + result.stderr or '').lower()
        detected = [name for name in tun_names if name in output]
        if detected:
            info['tun_adapters'] = detected
    except Exception:
        pass

    # 综合判断模式
    if info['tun_adapters']:
        info['mode'] = 'tun'
        info['recommendation'] = (
            '检测到 TUN 虚拟网卡模式。请在 Clash 规则中添加直连规则:\n'
            '  - DOMAIN-SUFFIX,eastmoney.com,DIRECT\n'
            '  或者在 Clash 中将 eastmoney.com 相关域名设为绕过代理(Bypass)。'
        )
    elif info['registry_proxy'].get('enable') or info['env_proxies']:
        info['mode'] = 'system_proxy'
        info['recommendation'] = (
            f"检测到系统代理({info['registry_proxy'].get('server', '')})。"
            "代码已自动尝试清除代理重试。"
        )
    else:
        info['mode'] = 'none'
        info['recommendation'] = '未检测到代理，连接问题可能是网络或防火墙导致。'

    return info


def _clear_env_proxies() -> dict:
    """清除当前进程的环境变量代理，返回被清除的值以便恢复"""
    removed = {}
    proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    for key in proxy_keys:
        val = os.environ.pop(key, None)
        if val is not None:
            removed[key] = val
    return removed


def _restore_env_proxies(removed: dict):
    """恢复之前清除的环境变量代理"""
    for key, val in removed.items():
        os.environ[key] = val


class _NoProxyContext:
    """上下文管理器：临时清除环境变量代理，执行操作后恢复"""

    def __enter__(self):
        self._saved = _clear_env_proxies()
        return self

    def __exit__(self, *args):
        _restore_env_proxies(self._saved)


def call_with_no_proxy(func, *args, **kwargs):
    """在无代理环境下调用指定函数（自动重试一次）

    当 Akshare 因 ProxyError 失败时，先清除代理重试。
    注意：TUN 模式下清除环境变量无效，会记录诊断信息。

    Args:
        func: 要调用的函数（如 ak.stock_zh_index_spot_em）
        *args, **kwargs: 传给 func 的参数

    Returns:
        func 的返回值
    """
    # 第一次：正常调用（使用当前代理配置）
    try:
        return func(*args, **kwargs)
    except Exception as first_exc:
        exc_str = str(first_exc).lower()
        is_proxy_error = any(kw in exc_str for kw in ['proxy', 'remote end closed', 'connection'])
        if not is_proxy_error:
            raise  # 非代理相关错误，直接抛出

        # 检测代理模式并给出针对性提示
        proxy_info = detect_proxy_mode()
        if proxy_info['mode'] == 'tun':
            logger.warning(
                f'Akshare call failed (TUN模式检测到!). '
                f'TUN网卡: {proxy_info.get("tun_adapters", [])}. '
                f'清除环境变量对TUN无效! 建议在Clash规则中添加 eastmoney.com DIRECT. '
                f'原始错误: {first_exc}'
            )
        else:
            logger.warning(f'Akshare call failed with proxy error, retrying without env proxies: {first_exc}')

        # 第二次：清除环境变量后重试（对 TUN 无效，但对 system_proxy 有效）
        try:
            with _NoProxyContext():
                return func(*args, **kwargs)
        except Exception as second_exc:
            if proxy_info['mode'] == 'tun':
                logger.error(
                    f'Akshare still failed under TUN (env-clear ineffective). '
                    f'Fix: Add DOMAIN-SUFFIX,eastmoney.com,DIRECT to Clash rules. '
                    f'Error: {second_exc}'
                )
            else:
                logger.error(f'Akshare also failed without proxy: {second_exc}')
            raise second_exc from first_exc


def check_proxy_status() -> Dict[str, Any]:
    """检查当前系统代理状态（已升级为完整模式检测）"""
    return detect_proxy_mode()


class AkshareService:
    SINA_QUOTE_URL = 'https://hq.sinajs.cn/'
    SINA_HEADERS = {
        'Referer': 'https://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0',
    }
    SINA_BATCH_SIZE = 800
    MARKET_STATS_CACHE_TTL_SECONDS = 60
    MARKET_UNIVERSE_CACHE_HOURS = 12
    _market_stats_cache: Dict[str, Any] = {'expires_at': None, 'value': None}
    _market_universe_cache: Dict[str, Any] = {'expires_at': None, 'codes': []}
    """Akshare 数据获取服务（统一封装层）"""

    # ======================== 工具方法 ========================

    @staticmethod
    def _to_float(value: Any, digits: int = 2) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or value == '' or pd.isna(value):
            return None
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_text(value: Any) -> str:
        """安全转换为文本"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ''
        return str(value).strip()

    @staticmethod
    def _ts_code_to_ak(code: str) -> str:
        """Tushare ts_code → Akshare 格式（如 600519.SH → 600519）"""
        if not code:
            return ''
        return code.split('.')[0]

    @staticmethod
    def _ak_to_ts_code(code: str, default_market: str = 'SH') -> str:
        """Akshare 格式 → Tushare ts_code（如 600519 → 600519.SH）"""
        if not code:
            return ''
        code = str(code).strip()
        if '.' in code:
            return code.upper()
        if code.startswith(('6', '9')):
            return f'{code}.SH'
        if code.startswith(('0', '2', '3')):
            return f'{code}.SZ'
        if code.startswith(('4', '8')):
            return f'{code}.BJ'
        return f'{code}.{default_market}'

    @staticmethod
    def _ts_code_to_sina_symbol(code: str) -> str:
        if not code:
            return ''
        normalized = str(code).strip().upper()
        if '.' in normalized:
            symbol, market = normalized.split('.', 1)
            return f'{market.lower()}{symbol}'
        if normalized.startswith(('6', '9')):
            return f'sh{normalized}'
        if normalized.startswith(('0', '2', '3')):
            return f'sz{normalized}'
        if normalized.startswith(('4', '8')):
            return f'bj{normalized}'
        return normalized.lower()

    @staticmethod
    def _sina_symbol_to_ts_code(symbol: str) -> str:
        if not symbol:
            return ''
        normalized = str(symbol).strip().lower()
        if len(normalized) <= 2:
            return normalized.upper()
        market = normalized[:2]
        raw_code = normalized[2:]
        market_map = {'sh': 'SH', 'sz': 'SZ', 'bj': 'BJ'}
        return f'{raw_code}.{market_map.get(market, market.upper())}'

    @classmethod
    def _fetch_sina_snapshots(cls, symbols: List[str]) -> Dict[str, List[str]]:
        if not symbols:
            return {}

        snapshots: Dict[str, List[str]] = {}
        for start in range(0, len(symbols), cls.SINA_BATCH_SIZE):
            batch = [symbol for symbol in symbols[start:start + cls.SINA_BATCH_SIZE] if symbol]
            if not batch:
                continue

            response = call_with_no_proxy(
                requests.get,
                f"{cls.SINA_QUOTE_URL}?list={','.join(batch)}",
                headers=cls.SINA_HEADERS,
                timeout=15,
            )
            response.encoding = 'gbk'

            for raw_line in (response.text or '').splitlines():
                line = raw_line.strip()
                if not line or 'hq_str_' not in line or '=' not in line:
                    continue
                left, right = line.split('=', 1)
                symbol = left.split('hq_str_')[-1].strip()
                payload = right.strip().rstrip(';').strip('"')
                snapshots[symbol] = payload.split(',') if payload else []

        return snapshots

    @classmethod
    def _parse_sina_snapshot(
        cls,
        symbol: str,
        fields: List[str],
        source: str = 'sina_realtime',
        default_name: str = '',
    ) -> Optional[Dict[str, Any]]:
        if not fields or len(fields) < 32:
            return None

        price = cls._to_float(fields[3])
        pre_close = cls._to_float(fields[2])
        open_price = cls._to_float(fields[1])
        high = cls._to_float(fields[4])
        low = cls._to_float(fields[5])
        volume = cls._to_float(fields[8], 0)
        amount = cls._to_float(fields[9], 0)

        change = None
        pct_chg = None
        if price is not None and pre_close not in (None, 0):
            change = round(price - pre_close, 2)
            pct_chg = round(change / pre_close * 100, 2)

        amplitude = None
        if high is not None and low is not None and pre_close not in (None, 0):
            amplitude = round((high - low) / pre_close * 100, 2)

        return {
            'ts_code': cls._sina_symbol_to_ts_code(symbol),
            'name': cls._safe_text(fields[0]) or default_name,
            'price': price,
            'pre_close': pre_close,
            'open': open_price,
            'high': high,
            'low': low,
            'change': change,
            'pct_chg': pct_chg,
            'amplitude': amplitude,
            'volume': volume,
            'amount': amount,
            'turnover_rate': None,
            'trade_date': cls._safe_text(fields[30]),
            'trade_time': cls._safe_text(fields[31]),
            'source': source,
        }

    @classmethod
    def _empty_quote(cls, code: str, source: str = 'sina_not_found') -> Dict[str, Any]:
        ts_code = code.upper() if '.' in str(code) else cls._ak_to_ts_code(code)
        return {
            'ts_code': ts_code,
            'name': '',
            'price': None,
            'pre_close': None,
            'open': None,
            'high': None,
            'low': None,
            'change': None,
            'pct_chg': None,
            'amplitude': None,
            'volume': None,
            'amount': None,
            'turnover_rate': None,
            'trade_date': '',
            'trade_time': '',
            'source': source,
        }

    @classmethod
    def _get_market_universe_codes(cls) -> List[str]:
        now = datetime.now()
        expires_at = cls._market_universe_cache.get('expires_at')
        if expires_at and expires_at > now and cls._market_universe_cache.get('codes'):
            return list(cls._market_universe_cache['codes'])

        try:
            from app.models import StockBasic

            codes = [
                cls._safe_text(ts_code).upper()
                for (ts_code,) in StockBasic.query.with_entities(StockBasic.ts_code).all()
                if cls._safe_text(ts_code)
            ]
            cls._market_universe_cache = {
                'expires_at': now + timedelta(hours=cls.MARKET_UNIVERSE_CACHE_HOURS),
                'codes': codes,
            }
            return list(codes)
        except Exception as exc:
            logger.warning(f'Load stock universe for Sina stats failed: {exc}')
            return list(cls._market_universe_cache.get('codes', []))

    @staticmethod
    def _fallback_sina_market_stats() -> Dict[str, Any]:
        df = call_with_no_proxy(ak.stock_zh_a_spot)
        if df is None or df.empty:
            return {
                'advancing': 0,
                'declining': 0,
                'flat': 0,
                'limit_up': 0,
                'limit_down': 0,
                'total': 0,
                'source': 'sina_market_stats',
                'message': '无数据',
            }

        pct_col = '涨跌幅'
        return {
            'advancing': int((df[pct_col] > 0).sum()),
            'declining': int((df[pct_col] < 0).sum()),
            'flat': int((df[pct_col] == 0).sum()),
            'limit_up': int(((df[pct_col] >= 9.8) & (~df['名称'].str.contains('ST', na=False))).sum()),
            'limit_down': int(((df[pct_col] <= -9.8) & (~df['名称'].str.contains('ST', na=False))).sum()),
            'total': len(df),
            'source': 'sina_market_stats',
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': '市场统计已通过新浪快照加载。',
        }

    # ======================== 实时行情 ========================

    @classmethod
    def get_realtime_quotes(cls, codes: List[str]) -> Dict[str, Any]:
        """
        获取实时行情（东方财富）

        Args:
            codes: 股票代码列表，支持 ts_code 格式或纯代码

        Returns:
            {
                'quotes': [...],      # 行情列表
                'source': 'akshare_em',
                'message': '...',
            }
        """
        if not codes:
            return {'quotes': [], 'source': 'empty', 'message': '未提供股票代码'}

        try:
            normalized_codes = [c.upper() if '.' in c else cls._ak_to_ts_code(c) for c in codes]
            symbol_map = {code: cls._ts_code_to_sina_symbol(code) for code in normalized_codes}
            snapshots = cls._fetch_sina_snapshots(list(symbol_map.values()))

            ordered = []
            for code in normalized_codes:
                symbol = symbol_map[code]
                quote = cls._parse_sina_snapshot(symbol, snapshots.get(symbol, []), source='sina_realtime')
                ordered.append(quote if quote else cls._empty_quote(code))

            has_data = any(q.get('price') is not None for q in ordered)
            return {
                'quotes': ordered,
                'source': 'sina_realtime',
                'message': '已通过新浪快照加载实时行情。' if has_data else '当前非交易时间，无实时报价。',
            }

        except Exception as exc:
            logger.error(f'Sina realtime quote error: {exc}')
            return {'quotes': [], 'source': 'sina_realtime', 'message': f'新浪实时行情获取失败: {exc}'}

    # ======================== 指数数据 ========================

    # 常用指数代码（新浪快照）
    INDEX_MAP = {
        '000001.SH': {'name': '上证指数', 'symbol': 'sh000001'},
        '399001.SZ': {'name': '深证成指', 'symbol': 'sz399001'},
        '399006.SZ': {'name': '创业板指', 'symbol': 'sz399006'},
        '000300.SH': {'name': '沪深300', 'symbol': 'sh000300'},
        '000016.SH': {'name': '上证50', 'symbol': 'sh000016'},
        '000905.SH': {'name': '中证500', 'symbol': 'sh000905'},
        '000688.SH': {'name': '科创50', 'symbol': 'sh000688'},
    }

    @classmethod
    def get_index_spot(cls) -> Dict[str, Any]:
        """
        获取大盘指数实时数据

        Returns:
            {
                'items': [{ts_code, name, price, pct_chg, ...}],
                'source': 'akshare_em',
                ...
            }
        """
        try:
            snapshots = cls._fetch_sina_snapshots([meta['symbol'] for meta in cls.INDEX_MAP.values()])
            if not snapshots:
                return {'items': [], 'source': 'sina_index', 'message': '未获取到指数数据'}

            items = []
            for ts_code, meta in cls.INDEX_MAP.items():
                quote = cls._parse_sina_snapshot(meta['symbol'], snapshots.get(meta['symbol'], []), source='sina_index')
                if not quote:
                    items.append({
                        'ts_code': ts_code,
                        'name': meta['name'],
                        'price': None,
                        'change': None,
                        'pct_chg': None,
                        'vol': None,
                        'amount': None,
                        'open': None,
                        'high': None,
                        'low': None,
                        'pre_close': None,
                        'trade_date': '',
                        'error': 'No data',
                    })
                    continue

                items.append({
                    'ts_code': ts_code,
                    'name': meta['name'],
                    'price': quote.get('price'),
                    'change': quote.get('change'),
                    'pct_chg': quote.get('pct_chg'),
                    'vol': quote.get('volume'),
                    'amount': quote.get('amount'),
                    'open': quote.get('open'),
                    'high': quote.get('high'),
                    'low': quote.get('low'),
                    'pre_close': quote.get('pre_close'),
                    'trade_date': quote.get('trade_date', ''),
                    'error': None,
                })

            latest_trade_date = max((item.get('trade_date') or '' for item in items), default='')
            return {
                'success': True,
                'items': items,
                'source': 'sina_index',
                'trade_date': latest_trade_date,
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': '指数数据已通过新浪快照加载。',
            }

        except Exception as exc:
            logger.error(f'Sina index spot error: {exc}')
            return {
                'success': False,
                'items': [],
                'source': 'sina_index',
                'message': f'指数数据获取失败: {exc}',
            }

    @classmethod
    def get_index_history(cls, symbol: str = 'sh000001',
                          start_date: str = '', end_date: str = '',
                          period: str = 'daily', adjust: str = '') -> Dict[str, Any]:
        """
        获取指数历史 K 线

        Args:
            symbol: 如 sh000001(上证), sz399001(深证)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: daily / weekly / monthly
            adjust: '' / 'qfq'(前复权) / 'hfq'(后复权)

        Returns:
            {'data': [...DataFrame records...], 'source': ...}
        """
        try:
            if period == 'daily':
                df = call_with_no_proxy(ak.stock_zh_index_daily, symbol=symbol)
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date).date()]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date).date()]
            else:
                kwargs = {'symbol': symbol}
                if start_date:
                    kwargs['start_date'] = start_date
                if end_date:
                    kwargs['end_date'] = end_date
                if period == 'weekly':
                    kwargs['period'] = 'weekly'
                elif period == 'monthly':
                    kwargs['period'] = 'monthly'
                if adjust:
                    kwargs['adjust'] = adjust
                df = call_with_no_proxy(ak.index_zh_a_hist, **kwargs)
            if df is None or df.empty:
                return {'data': [], 'source': 'akshare', 'message': '无历史数据'}

            kline = []
            for _, row in df.iterrows():
                kline.append({
                    'trade_date': cls._safe_text(row.get('日期') or row.get('date')),
                    'open': cls._to_float(row.get('开盘') or row.get('open')),
                    'close': cls._to_float(row.get('收盘') or row.get('close')),
                    'high': cls._to_float(row.get('最高') or row.get('high')),
                    'low': cls._to_float(row.get('最低') or row.get('low')),
                    'vol': cls._to_float(row.get('成交量') or row.get('volume'), 0),
                    'amount': cls._to_float(row.get('成交额') or row.get('amount'), 0),
                })

            return {
                'data': kline,
                'source': 'akshare_index_hist',
                'count': len(kline),
                'message': '指数K线已加载',
            }
        except Exception as exc:
            logger.error(f'Akshare index history error ({symbol}): {exc}')
            return {'data': [], 'source': 'akshare', 'message': str(exc)}

    # ======================== 个股历史K线 ========================

    @classmethod
    def get_stock_history(cls, symbol: str, period: str = 'daily',
                          start_date: str = '', end_date: str = '',
                          adjust: str = 'qfq', limit: int = 500) -> Dict[str, Any]:
        """
        获取个股历史 K 线数据（东方财富）

        Args:
            symbol: 股票代码（如 600519）
            period: daily / weekly / monthly
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: '' / 'qfq' / 'hfq'
            limit: 最大返回条数

        Returns:
            {'data': [...], 'source': 'akshare', 'count': N}
        """
        try:
            ak_symbol = cls._ts_code_to_ak(symbol)
            kwargs = {
                'symbol': ak_symbol,
                'period': period,
                'adjust': adjust,
            }
            if start_date:
                kwargs['start_date'] = start_date
            if end_date:
                kwargs['end_date'] = end_date

            df = call_with_no_proxy(ak.stock_zh_a_hist, **kwargs)
            if df is None or df.empty:
                return {'data': [], 'source': 'akshare', 'message': f'{symbol} 无历史数据'}

            # 取最近 limit 条
            df = df.tail(limit)

            kline = []
            for _, row in df.iterrows():
                kline.append({
                    'date': cls._safe_text(row.get('日期')),
                    'open': cls._to_float(row.get('开盘')),
                    'close': cls._to_float(row.get('收盘')),
                    'high': cls._to_float(row.get('最高')),
                    'low': cls._to_float(row.get('最低')),
                    'volume': cls._to_float(row.get('成交量'), 0),
                    'amount': cls._to_float(row.get('成交额'), 0),
                    'turnover': cls._to_float(row.get('换手率')),
                    'pct_chg': cls._to_float(row.get('涨跌幅')),
                })

            return {
                'data': kline,
                'source': 'akshare_stock_hist',
                'symbol': symbol,
                'period': period,
                'adjust': adjust,
                'count': len(kline),
                'message': f'{symbol} 历史{limit}条已加载',
            }
        except Exception as exc:
            logger.error(f'Akshare stock history error ({symbol}): {exc}')
            return {'data': [], 'source': 'akshare', 'message': str(exc)}

    # ======================== 市场统计 ========================

    @classmethod
    def get_market_stats(cls) -> Dict[str, Any]:
        """
        获取市场统计信息（涨跌家数、涨停跌停数等）

        Returns:
            {
                'advancing': N,     # 上涨家数
                'declining': N,     # 下跌家数
                'flat': N,          # 平盘家数
                'limit_up': N,      # 涨停数
                'limit_down': N,    # 跌停数
                'source': 'akshare_em',
            }
        """
        try:
            now = datetime.now()
            expires_at = cls._market_stats_cache.get('expires_at')
            cached_value = cls._market_stats_cache.get('value')
            if expires_at and expires_at > now and cached_value:
                return dict(cached_value)

            codes = cls._get_market_universe_codes()
            if not codes:
                result = cls._fallback_sina_market_stats()
            else:
                snapshots = cls._fetch_sina_snapshots([cls._ts_code_to_sina_symbol(code) for code in codes])
                advancing = declining = flat = limit_up = limit_down = total = 0

                for code in codes:
                    symbol = cls._ts_code_to_sina_symbol(code)
                    quote = cls._parse_sina_snapshot(symbol, snapshots.get(symbol, []), source='sina_market_stats')
                    if not quote or quote.get('price') is None or quote.get('pre_close') in (None, 0):
                        continue

                    pct_chg = quote.get('pct_chg') or 0
                    total += 1
                    if pct_chg > 0:
                        advancing += 1
                    elif pct_chg < 0:
                        declining += 1
                    else:
                        flat += 1

                    is_st = 'ST' in str(quote.get('name', '')).upper()
                    if pct_chg >= 9.8 and not is_st:
                        limit_up += 1
                    if pct_chg <= -9.8 and not is_st:
                        limit_down += 1

                result = {
                    'advancing': advancing,
                    'declining': declining,
                    'flat': flat,
                    'limit_up': limit_up,
                    'limit_down': limit_down,
                    'total': total,
                    'source': 'sina_market_stats',
                    'update_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': '市场统计已通过新浪快照加载。',
                }

            cls._market_stats_cache = {
                'expires_at': now + timedelta(seconds=cls.MARKET_STATS_CACHE_TTL_SECONDS),
                'value': dict(result),
            }
            return result
        except Exception as exc:
            logger.error(f'Sina market stats error: {exc}')
            return {
                'advancing': 0, 'declining': 0, 'flat': 0,
                'limit_up': 0, 'limit_down': 0,
                'source': 'sina_market_stats', 'message': str(exc),
            }

    @classmethod
    def get_stock_info(cls, symbol: str) -> Dict[str, Any]:
        """
        获取个股基本信息（东财）

        Args:
            symbol: 股票代码（如 600519）
        """
        try:
            ak_sym = cls._ts_code_to_ak(symbol)
            df = ak.stock_individual_info_em(symbol=ak_sym)
            if df is None or df.empty:
                return {}

            info = {}
            for _, row in df.iterrows():
                key = cls._safe_text(row.get('item'))
                val = cls._safe_text(row.get('value'))
                if key:
                    info[key] = val
            return info
        except Exception as exc:
            logger.warning(f'Akshare stock info error ({symbol}): {exc}')
            return {}

    # ======================== 分时数据 ========================

    @classmethod
    def get_intraday_minute(cls, symbol: str, period: str = '1',
                            adjust: str = '') -> Dict[str, Any]:
        """
        获取个股/指数分时分钟K线数据（新浪财经）

        Args:
            symbol: 股票代码，支持 ts_code 格式或纯代码
            period: 分钟频率 '1' / '5' / '15' / '30' / '60'
            adjust: 复权方式 '' / 'qfq' / 'hfq'

        Returns:
            {
                'data': [{'time': '09:30', 'open': ..., 'high': ..., 'low': ...,
                          'close': ..., 'volume': ..., 'amount': ...}],
                'source': 'akshare_sina_minute',
                'date': '2026-04-24',
                'pre_close': ...,
                'count': N,
                'message': '...',
            }
        """
        try:
            # 将 ts_code 转为新浪格式
            sina_symbol = cls._ts_code_to_sina_symbol(symbol)
            if not sina_symbol:
                # 可能已经是 sh600519 格式
                sina_symbol = symbol

            # 判断是否为指数代码，指数使用专用分时接口
            is_index = symbol in cls.INDEX_MAP or (
                '.' in symbol and symbol.split('.')[0].startswith(('0000', '3990', '0006'))
            ) or sina_symbol.startswith(('sh000', 'sz399', 'sh0006'))

            if is_index:
                # 指数分时：新浪 stock_zh_a_minute 对指数也可用（东财接口会被代理拦截）
                df = call_with_no_proxy(
                    ak.stock_zh_a_minute,
                    symbol=sina_symbol,
                    period=period,
                    adjust=adjust,
                )
            else:
                # 个股分时：使用 ak.stock_zh_a_minute
                df = call_with_no_proxy(
                    ak.stock_zh_a_minute,
                    symbol=sina_symbol,
                    period=period,
                    adjust=adjust,
                )
            if df is None or df.empty:
                return {'data': [], 'source': 'akshare_sina_minute',
                        'message': f'{symbol} 无分时数据'}

            # 只取最近交易日的数据
            df['day'] = pd.to_datetime(df['day'])
            latest_date = df['day'].dt.date.max()
            df_today = df[df['day'].dt.date == latest_date].copy()

            if df_today.empty:
                return {'data': [], 'source': 'akshare_sina_minute',
                        'message': f'{symbol} 今日无分时数据'}

            # 获取昨收价（用于分时图基准线）
            pre_close = cls._to_float(df_today.iloc[0].get('open')) if not df_today.empty else None

            # 格式化数据
            records = []
            for _, row in df_today.iterrows():
                time_str = str(row['day'].strftime('%H:%M')) if pd.notna(row['day']) else ''
                records.append({
                    'time': time_str,
                    'open': cls._to_float(row.get('open')),
                    'high': cls._to_float(row.get('high')),
                    'low': cls._to_float(row.get('low')),
                    'close': cls._to_float(row.get('close')),
                    'volume': cls._to_float(row.get('volume'), 0),
                    'amount': cls._to_float(row.get('amount'), 0),
                })

            # 尝试从新浪快照获取更准确的昨收价
            try:
                snapshots = cls._fetch_sina_snapshots([sina_symbol])
                snapshot = cls._parse_sina_snapshot(
                    sina_symbol, snapshots.get(sina_symbol, []),
                    source='sina_realtime',
                )
                if snapshot and snapshot.get('pre_close') is not None:
                    pre_close = snapshot['pre_close']
            except Exception:
                pass

            return {
                'data': records,
                'source': 'akshare_sina_minute',
                'date': str(latest_date),
                'pre_close': pre_close,
                'count': len(records),
                'message': f'{symbol} 分时{period}分钟数据已加载',
            }
        except Exception as exc:
            logger.error(f'Akshare intraday minute error ({symbol}): {exc}')
            return {'data': [], 'source': 'akshare_sina_minute',
                    'message': str(exc)}

    # ======================== 健康检查 ========================

    @classmethod
    def ping(cls) -> Dict[str, Any]:
        """检查实时监控当前使用的新浪快照链路是否可用。"""
        try:
            sample_items = list(cls.INDEX_MAP.items())[:3]
            symbols = [meta['symbol'] for _, meta in sample_items]
            snapshots = cls._fetch_sina_snapshots(symbols)

            quotes = []
            for _, meta in sample_items:
                quote = cls._parse_sina_snapshot(
                    meta['symbol'],
                    snapshots.get(meta['symbol'], []),
                    source='sina_realtime',
                    default_name=meta['name'],
                )
                if quote:
                    quotes.append(quote)

            priced_quotes = [quote for quote in quotes if quote.get('price') is not None]
            success = bool(priced_quotes)
            return {
                'success': success,
                'message': '新浪快照连接正常' if success else '新浪快照已响应，但未返回有效价格',
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'sina_snapshot',
                'spot_count': len(priced_quotes),
                'checked_symbols': symbols,
                'samples': [
                    {
                        'ts_code': quote.get('ts_code'),
                        'name': quote.get('name'),
                        'price': quote.get('price'),
                        'trade_date': quote.get('trade_date'),
                        'trade_time': quote.get('trade_time'),
                    }
                    for quote in quotes
                ],
                'proxy': check_proxy_status(),
            }
        except Exception as exc:
            return {
                'success': False,
                'message': f'新浪快照连接失败: {exc}',
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'sina_snapshot',
                'proxy': check_proxy_status(),
            }


def _is_trade_time() -> bool:
    """简单判断当前是否在交易时间（粗略判断）"""
    now = datetime.now()
    weekday = now.weekday()  # 0=Mon, 4=Fri
    if weekday >= 5:
        return False
    t = now.hour * 100 + now.minute
    return (915 <= t <= 1130) or (1300 <= t <= 1500)
