# -*- coding: utf-8 -*-
from flask import g, jsonify, request
from loguru import logger

from app.api import api_bp
from app.services.realtime_monitor_service import RealtimeMonitorService


@api_bp.route('/monitor/dashboard', methods=['GET'])
def get_monitor_dashboard():
    try:
        raw_codes = (request.args.get('ts_codes') or '').strip()
        result = RealtimeMonitorService.get_dashboard(
            user_id=getattr(getattr(g, 'current_user', None), 'id', None),
            raw_codes=raw_codes,
        )
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get monitor dashboard failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


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
    except ValueError as exc:
        return jsonify({'code': 400, 'message': str(exc), 'data': None}), 400
    except Exception as exc:
        logger.error(f'Get monitor stock detail failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500
