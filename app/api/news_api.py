# -*- coding: utf-8 -*-
"""新闻资讯 API 路由"""
from flask import jsonify, request
from app.api import api_bp
from app.services.news_service import NewsService
from app.utils.api_helpers import api_error_handler


@api_bp.route('/news', methods=['GET'])
@api_error_handler(default_message='获取新闻资讯失败')
def get_news():
    """获取新闻资讯 - 支持 source 参数筛选"""
    source = request.args.get('source', 'all')
    source_map = {
        'all': NewsService.get_all_news,
        'cjzc': NewsService.get_cjzc,
        'global_em': NewsService.get_global_em,
        'cls': NewsService.get_global_cls,
        'ths': NewsService.get_global_ths,
    }
    func = source_map.get(source, NewsService.get_all_news)
    result = func()
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/news/cjzc', methods=['GET'])
@api_error_handler(default_message='获取财经早餐失败')
def get_news_cjzc():
    """获取东方财富-财经早餐"""
    result = NewsService.get_cjzc()
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/news/global', methods=['GET'])
@api_error_handler(default_message='获取全球快讯失败')
def get_news_global():
    """获取全球财经快讯（合并东财+财联社+同花顺）"""
    source = request.args.get('source', 'all')
    source_map = {
        'all': NewsService.get_all_news,
        'em': NewsService.get_global_em,
        'cls': NewsService.get_global_cls,
        'ths': NewsService.get_global_ths,
    }
    func = source_map.get(source, NewsService.get_all_news)
    result = func()
    return jsonify({'code': 200, 'message': 'success', 'data': result})
