# -*- coding: utf-8 -*-
"""新闻资讯 API 路由"""
from flask import jsonify, request
from app.api import api_bp
from app.services.news_service import NewsService
from app.utils.api_helpers import api_error_handler
import json
import hashlib

# 缓存配置：Redis TTL 5分钟，内存降级 TTL 3分钟
_NEWS_CACHE_TTL = 300
_FALLBACK_TTL = 180
_memory_cache = {}


def _get_news_cache_key(source):
    return f"news_aggregate:{source}"


def _get_cached_news(source):
    """优先从Redis获取缓存，不可用时使用内存缓存"""
    try:
        from app.extensions import cache
        key = _get_news_cache_key(source)
        data = cache.get(key)
        if data is not None:
            return json.loads(data) if isinstance(data, str) else data
    except Exception:
        pass
    return _memory_cache.get(source)


def _set_news_cache(source, data):
    """写入双层缓存：Redis + 内存(降级)"""
    try:
        from app.extensions import cache
        key = _get_news_cache_key(source)
        cache.set(key, json.dumps(data, ensure_ascii=False), timeout=_NEWS_CACHE_TTL)
    except Exception:
        pass
    _memory_cache[source] = data


@api_bp.route('/news', methods=['GET'])
@api_error_handler(default_message='获取新闻资讯失败')
def get_news():
    """获取新闻资讯 - 支持 source 参数筛选 (带5分钟缓存)"""
    source = request.args.get('source', 'all')

    # 尝试读取缓存
    cached = _get_cached_news(source)
    if cached is not None:
        return jsonify({'code': 200, 'message': 'success (cached)', 'data': cached})

    source_map = {
        'all': NewsService.get_all_news,
        'cjzc': NewsService.get_cjzc,
        'global_em': NewsService.get_global_em,
        'cls': NewsService.get_global_cls,
        'ths': NewsService.get_global_ths,
    }
    func = source_map.get(source, NewsService.get_all_news)
    result = func()

    # 写入缓存（无论是否为空都缓存，防止穿透）
    _set_news_cache(source, result or [])

    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/news/cjzc', methods=['GET'])
@api_error_handler(default_message='获取财经早餐失败')
def get_news_cjzc():
    """获取东方财富-财经早餐 (带缓存)"""
    cached = _get_cached_news('cjzc')
    if cached is not None:
        return jsonify({'code': 200, 'message': 'success (cached)', 'data': cached})

    result = NewsService.get_cjzc()
    _set_news_cache('cjzc', result or [])
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/news/global', methods=['GET'])
@api_error_handler(default_message='获取全球快讯失败')
def get_news_global():
    """获取全球财经快讯（合并东财+财联社+同花顺）(带缓存)"""
    source = request.args.get('source', 'all')
    cache_key = f'global_{source}'

    cached = _get_cached_news(cache_key)
    if cached is not None:
        return jsonify({'code': 200, 'message': 'success (cached)', 'data': cached})

    source_map = {
        'all': NewsService.get_all_news,
        'em': NewsService.get_global_em,
        'cls': NewsService.get_global_cls,
        'ths': NewsService.get_global_ths,
    }
    func = source_map.get(source, NewsService.get_all_news)
    result = func()

    _set_news_cache(cache_key, result or [])
    return jsonify({'code': 200, 'message': 'success', 'data': result})
