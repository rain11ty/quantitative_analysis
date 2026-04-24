# -*- coding: utf-8 -*-
from flask import g, jsonify, request
from loguru import logger

from app.api import api_bp
from app.services.realtime_monitor_service import RealtimeMonitorService
from app.utils.api_helpers import api_error_handler


@api_bp.route('/monitor/dashboard', methods=['GET'])
@api_error_handler(default_message='获取监控面板数据失败')
def get_monitor_dashboard():
    raw_codes = (request.args.get('ts_codes') or '').strip()
    user_id = getattr(getattr(g, 'current_user', None), 'id', None)
    result = RealtimeMonitorService.get_dashboard(
        user_id=user_id,
        raw_codes=raw_codes,
    )
    # 注入诊断信息，方便前端排查
    result['debug'] = {
        'user_id': user_id,
        'raw_codes': raw_codes,
        'is_logged_in': user_id is not None,
    }
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/monitor/ranking', methods=['GET'])
@api_error_handler(default_message='获取实时涨跌排名失败')
def get_realtime_ranking():
    sort_by = (request.args.get('sort_by') or 'pct_change').strip()
    limit = min(int(request.args.get('limit', 20)), 50)
    src = (request.args.get('src') or 'dc').strip()
    if src not in ('dc', 'sina'):
        src = 'dc'
    result = RealtimeMonitorService.get_realtime_ranking(
        sort_by=sort_by,
        limit=limit,
        src=src,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/monitor/stocks/<path:ts_code>', methods=['GET'])
def get_monitor_stock_detail(ts_code):
    try:
        freq = (request.args.get('freq') or 'daily').strip()
        result = RealtimeMonitorService.get_stock_detail(
            user_id=getattr(getattr(g, 'current_user', None), 'id', None),
            ts_code=ts_code,
            freq=freq,
        )
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e), 'data': None}), 400
    except Exception as exc:
        from config import Config
        is_debug = getattr(Config, 'DEBUG', False)
        logger.error(f'Get monitor stock detail failed: {ts_code}, {exc}')
        message = f'server error: {exc}' if is_debug else '获取股票详情失败，请稍后重试'
        return jsonify({'code': 500, 'message': message, 'data': None}), 500


@api_bp.route('/monitor/intraday/<path:ts_code>', methods=['GET'])
@api_error_handler(default_message='获取分时数据失败')
def get_monitor_intraday(ts_code):
    """获取个股/指数分时走势数据"""
    period = (request.args.get('period') or '1').strip()
    if period not in ('1', '5', '15', '30', '60'):
        period = '1'
    result = RealtimeMonitorService.get_intraday_series(ts_code=ts_code, period=period)
    return jsonify({'code': 200, 'message': 'success', 'data': result})
