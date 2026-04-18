# -*- coding: utf-8 -*-
from flask import jsonify, request
from loguru import logger

from app.api import api_bp
from app.services.market_overview_service import MarketOverviewService
from app.services.stock_service import StockService


@api_bp.route('/stocks', methods=['GET'])
def get_stocks():
    try:
        industry = request.args.get('industry')
        area = request.args.get('area')
        search = request.args.get('search')
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 20)), 100)

        result = StockService.get_stock_list(
            industry=industry,
            area=area,
            search=search,
            page=page,
            page_size=page_size,
        )

        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stocks API failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/market/overview', methods=['GET'])
def get_market_overview():
    try:
        result = MarketOverviewService.get_market_overview()
        status_code = 200 if result.get('success') else 503
        return jsonify({'code': status_code, 'message': result.get('message'), 'data': result}), status_code
    except Exception as exc:
        logger.error(f'Get market overview API failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/market/health', methods=['GET'])
def ping_market_api():
    try:
        result = MarketOverviewService.ping_tushare()
        status_code = 200 if result.get('success') else 503
        return jsonify({'code': status_code, 'message': result.get('message'), 'data': result}), status_code
    except Exception as exc:
        logger.error(f'Ping Tushare API failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/stocks/<ts_code>', methods=['GET'])
def get_stock_detail(ts_code):
    try:
        result = StockService.get_stock_info(ts_code)
        if result is None:
            return jsonify({'code': 404, 'message': 'stock not found', 'data': None}), 404
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stock detail API failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/stocks/<ts_code>/history', methods=['GET'])
def get_stock_history(ts_code):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 60))

        result = StockService.get_daily_history(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stock history API failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/stocks/<ts_code>/factors', methods=['GET'])
def get_stock_factors(ts_code):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 60))

        result = StockService.get_stock_factors(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stock factors API failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/stocks/<ts_code>/moneyflow', methods=['GET'])
def get_stock_moneyflow(ts_code):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 30))

        result = StockService.get_moneyflow(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stock moneyflow API failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/stocks/<ts_code>/cyq', methods=['GET'])
def get_stock_cyq(ts_code):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 30))

        result = StockService.get_cyq_perf(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get stock cyq API failed: {ts_code}, {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/industries', methods=['GET'])
def get_industries():
    try:
        result = StockService.get_industry_list()
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get industries API failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500


@api_bp.route('/areas', methods=['GET'])
def get_areas():
    try:
        result = StockService.get_area_list()
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception as exc:
        logger.error(f'Get areas API failed: {exc}')
        return jsonify({'code': 500, 'message': f'server error: {exc}', 'data': None}), 500
