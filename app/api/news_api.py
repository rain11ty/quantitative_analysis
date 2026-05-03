# -*- coding: utf-8 -*-
"""新闻资讯 API 路由（纯读缓存，数据由 Celery 定时任务刷新）"""
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


@api_bp.route('/news', methods=['GET'])
@api_error_handler(default_message='获取新闻资讯失败')
def get_news():
    """获取新闻资讯 - 支持 source 参数筛选（纯读缓存）"""
    source = request.args.get('source', 'all')

    if source == 'all':
        cached = _get_cached_news('news_aggregate:all')
    else:
        cached = _get_cached_news(f'news_aggregate:{source}')

    if cached is not None:
        return jsonify({'code': 200, 'message': 'success', 'data': cached})

    return jsonify({
        'code': 200,
        'message': '数据暂未就绪，请稍后重试',
        'data': {'items': [], 'count': 0, 'source': '全部来源'},
    })


@api_bp.route('/news/cjzc', methods=['GET'])
@api_error_handler(default_message='获取财经早餐失败')
def get_news_cjzc():
    """获取东方财富-财经早餐（纯读缓存）"""
    cached = _get_cached_news('news_aggregate:all')
    if cached is not None:
        # 从聚合缓存中筛选 cjzc 来源
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
    """获取全球财经快讯（纯读缓存）"""
    cached = _get_cached_news('news_aggregate:all')
    if cached is not None:
        return jsonify({'code': 200, 'message': 'success', 'data': cached})

    return jsonify({
        'code': 200,
        'message': '数据暂未就绪，请稍后重试',
        'data': {'items': [], 'count': 0, 'source': '全部来源'},
    })
