# -*- coding: utf-8 -*-
"""新闻资讯服务 - 基于 Akshare 接口"""
import numpy as np
import pandas as pd
from loguru import logger
from app.utils.cache_utils import cache
from app.services.akshare_service import call_with_no_proxy
import akshare as ak


class NewsService:
    CACHE_TTL = 120  # 2分钟缓存

    @staticmethod
    def _safe_str(value):
        """安全转换为字符串"""
        if value is None:
            return ''
        if isinstance(value, float) and (pd.isna(value) or np.isnan(value)):
            return ''
        return str(value).strip()

    @staticmethod
    def get_cjzc():
        """获取东方财富-财经早餐"""
        cache_key = 'news_cjzc'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = call_with_no_proxy(ak.stock_info_cjzc_em)
            if df is None or df.empty:
                return {'items': [], 'source': '东方财富-财经早餐', 'count': 0}

            items = []
            for _, row in df.head(50).iterrows():
                items.append({
                    'title': NewsService._safe_str(row.get('标题')),
                    'summary': NewsService._safe_str(row.get('摘要')),
                    'time': NewsService._safe_str(row.get('发布时间')),
                    'link': NewsService._safe_str(row.get('链接')),
                    'source': '东财-财经早餐',
                })

            result = {'items': items, 'source': '东方财富-财经早餐', 'count': len(items)}
            cache.set(cache_key, result, ttl=NewsService.CACHE_TTL)
            return result
        except Exception as exc:
            logger.error(f'获取财经早餐失败: {exc}')
            return {'items': [], 'source': '东方财富-财经早餐', 'count': 0, 'error': str(exc)}

    @staticmethod
    def get_global_em():
        """获取东方财富-全球财经快讯"""
        cache_key = 'news_global_em'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = call_with_no_proxy(ak.stock_info_global_em)
            if df is None or df.empty:
                return {'items': [], 'source': '东方财富-全球快讯', 'count': 0}

            items = []
            for _, row in df.iterrows():
                items.append({
                    'title': NewsService._safe_str(row.get('标题')),
                    'summary': NewsService._safe_str(row.get('摘要')),
                    'time': NewsService._safe_str(row.get('发布时间')),
                    'link': NewsService._safe_str(row.get('链接')),
                    'source': '东财-全球快讯',
                })

            result = {'items': items, 'source': '东方财富-全球快讯', 'count': len(items)}
            cache.set(cache_key, result, ttl=NewsService.CACHE_TTL)
            return result
        except Exception as exc:
            logger.error(f'获取东方财富全球快讯失败: {exc}')
            return {'items': [], 'source': '东方财富-全球快讯', 'count': 0, 'error': str(exc)}

    @staticmethod
    def get_global_cls():
        """获取财联社-电报"""
        cache_key = 'news_global_cls'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = call_with_no_proxy(ak.stock_info_global_cls, symbol="全部")
            if df is None or df.empty:
                return {'items': [], 'source': '财联社-电报', 'count': 0}

            items = []
            for _, row in df.iterrows():
                pub_date = NewsService._safe_str(row.get('发布日期'))
                pub_time = NewsService._safe_str(row.get('发布时间'))
                time_str = f'{pub_date} {pub_time}'.strip() if pub_date else pub_time
                items.append({
                    'title': NewsService._safe_str(row.get('标题')),
                    'summary': NewsService._safe_str(row.get('内容')),
                    'time': time_str,
                    'link': '',
                    'source': '财联社',
                })

            result = {'items': items, 'source': '财联社-电报', 'count': len(items)}
            cache.set(cache_key, result, ttl=NewsService.CACHE_TTL)
            return result
        except Exception as exc:
            logger.error(f'获取财联社电报失败: {exc}')
            return {'items': [], 'source': '财联社-电报', 'count': 0, 'error': str(exc)}

    @staticmethod
    def get_global_ths():
        """获取同花顺-全球财经直播"""
        cache_key = 'news_global_ths'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = call_with_no_proxy(ak.stock_info_global_ths)
            if df is None or df.empty:
                return {'items': [], 'source': '同花顺-财经直播', 'count': 0}

            items = []
            for _, row in df.iterrows():
                items.append({
                    'title': NewsService._safe_str(row.get('标题')),
                    'summary': NewsService._safe_str(row.get('内容')),
                    'time': NewsService._safe_str(row.get('发布时间')),
                    'link': NewsService._safe_str(row.get('链接')),
                    'source': '同花顺',
                })

            result = {'items': items, 'source': '同花顺-财经直播', 'count': len(items)}
            cache.set(cache_key, result, ttl=NewsService.CACHE_TTL)
            return result
        except Exception as exc:
            logger.error(f'获取同花顺财经直播失败: {exc}')
            return {'items': [], 'source': '同花顺-财经直播', 'count': 0, 'error': str(exc)}

    @staticmethod
    def get_all_news():
        """获取所有来源的新闻（合并按时间排序）"""
        cache_key = 'news_all'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        all_items = []
        sources = [
            ('cjzc', NewsService.get_cjzc),
            ('global_em', NewsService.get_global_em),
            ('cls', NewsService.get_global_cls),
            ('ths', NewsService.get_global_ths),
        ]

        source_errors = []
        for name, func in sources:
            try:
                data = func()
                if data.get('items'):
                    all_items.extend(data['items'])
                elif data.get('error'):
                    source_errors.append(f"{data['source']}: {data['error']}")
            except Exception as exc:
                source_errors.append(f"{name}: {exc}")
                logger.warning(f'获取新闻来源 {name} 失败: {exc}')

        # 按时间降序排序（最新的在前面）
        all_items.sort(key=lambda x: x.get('time', ''), reverse=True)

        result = {
            'items': all_items,
            'count': len(all_items),
            'source': '全部来源',
            'errors': source_errors if source_errors else None,
        }
        cache.set(cache_key, result, ttl=NewsService.CACHE_TTL)
        return result
