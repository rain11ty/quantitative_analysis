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
    result = RealtimeMonitorService.get_dashboard(
        user_id=getattr(getattr(g, 'current_user', None), 'id', None),
        raw_codes=raw_codes,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/monitor/stocks/<ts_code>', methods=['GET'])
def get_monitor_stock_detail(ts_code):
    try:
        freq = (request.args.get('freq') or '1min').strip()
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
