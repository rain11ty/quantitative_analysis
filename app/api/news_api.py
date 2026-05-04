# -*- coding: utf-8 -*-
"""新闻资讯 API 路由（优先读缓存，缓存未命中时实时获取）"""
from __future__ import annotations

from flask import jsonify, request
from app.api import api_bp
from app.utils.api_helpers import api_error_handler


def _get_cached_news(key: str):
    """从 Redis 缓存读取新闻数据"""
    try:
        from app.utils.cache_utils import get_cache
        return get_cache().get(key)
    except Exception:
        return None


def _fetch_all_news():
    """实时获取所有新闻源数据并聚合"""
    from app.services.news_service import NewsService
    return NewsService.get_all_news()


def _get_news_with_fallback():
    """获取新闻数据（优先缓存，缓存未命中时实时获取）"""
    cached = _get_cached_news('news_aggregate:all')
    if cached is None:
        try:
            cached = _fetch_all_news()
        except Exception:
            cached = None
    return cached


@api_bp.route('/news', methods=['GET'])
@api_error_handler(default_message='获取新闻资讯失败')
def get_news():
    """获取新闻资讯 - 支持 source 参数筛选（优先读缓存，缓存未命中时实时获取）"""
    source = request.args.get('source', 'all')

    cached = _get_news_with_fallback()

    if cached is not None:
        if source == 'all':
            return jsonify({'code': 200, 'message': 'success', 'data': cached})

        # 根据 source 参数筛选对应来源的新闻
        source_filter_map = {
            'cjzc': lambda s: s.startswith('东财-财经'),
            'global_em': lambda s: s.startswith('东财-全球'),
            'cls': lambda s: s.startswith('财联社'),
            'ths': lambda s: s.startswith('同花顺'),
        }
        filter_fn = source_filter_map.get(source)
        if filter_fn:
            items = [item for item in cached.get('items', [])
                     if filter_fn(item.get('source', ''))]
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {'items': items, 'count': len(items), 'source': source},
            })

        # 未知 source，返回全部
        return jsonify({'code': 200, 'message': 'success', 'data': cached})

    return jsonify({
        'code': 200,
        'message': '数据暂未就绪，请稍后重试',
        'data': {'items': [], 'count': 0, 'source': '全部来源'},
    })


@api_bp.route('/news/cjzc', methods=['GET'])
@api_error_handler(default_message='获取财经早餐失败')
def get_news_cjzc():
    """获取东方财富-财经早餐（优先读缓存，缓存未命中时实时获取）"""
    cached = _get_news_with_fallback()

    if cached is not None:
        items = [item for item in cached.get('items', []) if item.get('source', '').startswith('东财-财经')]
        return jsonify({'code': 200, 'message': 'success', 'data': {'items': items, 'source': '东方财富-财经早餐', 'count': len(items)}})

    return jsonify({
        'code': 200,
        'message': '数据暂未就绪，请稍后重试',
        'data': {'items': [], 'source': '东方财富-财经早餐', 'count': 0},
    })


@api_bp.route('/news/global', methods=['GET'])
@api_error_handler(default_message='获取全球快讯失败')
def get_news_global():
    """获取全球财经快讯（优先读缓存，缓存未命中时实时获取）"""
    cached = _get_news_with_fallback()

    if cached is not None:
        return jsonify({'code': 200, 'message': 'success', 'data': cached})

    return jsonify({
        'code': 200,
        'message': '数据暂未就绪，请稍后重试',
        'data': {'items': [], 'count': 0, 'source': '全部来源'},
    })
