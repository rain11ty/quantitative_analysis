# -*- coding: utf-8 -*-
from flask import jsonify, request
from loguru import logger

from app.api import api_bp
from app.services.akshare_service import AkshareService
from app.services.market_overview_service import MarketOverviewService
from app.services.stock_service import StockService
from app.utils.api_helpers import api_error_handler


@api_bp.route('/stocks', methods=['GET'])
@api_error_handler(default_message='获取股票列表失败')
def get_stocks():
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


@api_bp.route('/market/overview', methods=['GET'])
@api_error_handler(default_message='获取市场概览失败')
def get_market_overview():
    result = MarketOverviewService.get_market_overview()
    # 三级降级保证 success=True（即使数据来自缓存/空），始终返回 200
    # 前端通过 result.get('degraded') 判断是否需要展示降级提示
    status_code = 200 if result.get('success') else 503
    return jsonify({'code': status_code, 'message': result.get('message'), 'data': result}), status_code


@api_bp.route('/market/health', methods=['GET'])
@api_error_handler(default_message='检测Tushare服务状态失败')
def ping_market_api():
    result = MarketOverviewService.ping_tushare()
    status_code = 200 if result.get('success') else 503
    return jsonify({'code': status_code, 'message': result.get('message'), 'data': result}), status_code


@api_bp.route('/market/akshare/health', methods=['GET'])
@api_error_handler(default_message='检测行情快照服务状态失败')
def ping_akshare_api():
    result = AkshareService.ping()
    status_code = 200 if result.get('success') else 503
    return jsonify({'code': status_code, 'message': result.get('message'), 'data': result}), status_code


@api_bp.route('/stocks/<path:ts_code>', methods=['GET'])
@api_error_handler(default_message='获取股票详情失败')
def get_stock_detail(ts_code):
    result = StockService.get_stock_info(ts_code)
    if result is None:
        return jsonify({'code': 404, 'message': 'stock not found', 'data': None}), 404
    # 附带最新日线基本数据（估值/市值/换手率等）
    daily_basic = StockService.get_daily_basic(ts_code)
    if daily_basic:
        result['daily_basic'] = daily_basic
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/realtime', methods=['GET'])
@api_error_handler(default_message='获取实时行情失败')
def get_stock_realtime(ts_code):
    """获取个股实时行情（含K线走势）"""
    from app.services.realtime_monitor_service import RealtimeMonitorService
    from flask import g

    freq = (request.args.get('freq') or 'daily').strip()
    result = RealtimeMonitorService.get_stock_detail(
        user_id=getattr(getattr(g, 'current_user', None), 'id', None),
        ts_code=ts_code,
        freq=freq,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/history', methods=['GET'])
@api_error_handler(default_message='获取历史数据失败')
def get_stock_history(ts_code):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = min(max(int(request.args.get('limit', 60)), 1), 5000)  # 限制范围 1~5000

    result = StockService.get_daily_history(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/factors', methods=['GET'])
@api_error_handler(default_message='获取技术因子数据失败')
def get_stock_factors(ts_code):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = min(max(int(request.args.get('limit', 60)), 1), 5000)

    result = StockService.get_stock_factors(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/moneyflow', methods=['GET'])
@api_error_handler(default_message='获取资金流向数据失败')
def get_stock_moneyflow(ts_code):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = min(max(int(request.args.get('limit', 30)), 1), 1000)

    result = StockService.get_moneyflow(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/cyq', methods=['GET'])
@api_error_handler(default_message='获取筹码分布数据失败')
def get_stock_cyq(ts_code):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = min(max(int(request.args.get('limit', 30)), 1), 1000)

    result = StockService.get_cyq_perf(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/stocks/<path:ts_code>/cyq_chips', methods=['GET'])
@api_error_handler(default_message='获取筹码分布详情失败')
def get_stock_cyq_chips(ts_code):
    """获取股票每日筹码分布详情（各价位占比）"""
    trade_date = request.args.get('trade_date')
    limit_days = min(max(int(request.args.get('limit_days', 1)), 1), 30)

    result = StockService.get_cyq_chips(
        ts_code=ts_code,
        trade_date=trade_date,
        limit_days=limit_days,
    )
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/industries', methods=['GET'])
@api_error_handler(default_message='获取行业列表失败')
def get_industries():
    result = StockService.get_industry_list()
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/areas', methods=['GET'])
@api_error_handler(default_message='获取地域列表失败')
def get_areas():
    result = StockService.get_area_list()
    return jsonify({'code': 200, 'message': 'success', 'data': result})


# ========== 自选股相关接口 ==========

@api_bp.route('/market/index/<path:ts_code>/kline', methods=['GET'])
@api_error_handler(default_message='获取指数K线数据失败')
def get_index_kline(ts_code):
    """获取指数历史K线数据"""
    period = request.args.get('period', '1Y')
    if period not in ('1M', '3M', '6M', '1Y', '3Y'):
        period = '1Y'
    result = MarketOverviewService.get_index_kline(ts_code, period=period)
    return jsonify({'code': 200, 'message': 'success', 'data': result})


@api_bp.route('/watchlist', methods=['GET'])
@api_error_handler(default_message='获取自选列表失败')
def get_watchlist():
    """获取当前用户的自选股票列表"""
    from flask import g
    user_id = getattr(getattr(g, 'current_user', None), 'id', None)
    if not user_id:
        return jsonify({'code': 401, 'message': '请先登录', 'data': []}), 401
    
    from app.models import UserWatchlist
    items = UserWatchlist.query.filter_by(user_id=user_id).order_by(UserWatchlist.created_at.desc()).all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': [item.to_dict() for item in items]
    })


@api_bp.route('/watchlist/<path:ts_code>', methods=['POST'])
@api_error_handler(default_message='添加自选失败')
def add_to_watchlist(ts_code):
    """将股票加入自选"""
    from flask import g
    user_id = getattr(getattr(g, 'current_user', None), 'id', None)
    if not user_id:
        return jsonify({'code': 401, 'message': '请先登录', 'data': None}), 401
    
    from app.models import UserWatchlist, StockBasic
    from app.extensions import db
    
    # 检查是否已存在
    existing = UserWatchlist.query.filter_by(user_id=user_id, ts_code=ts_code).first()
    if existing:
        return jsonify({'code': 200, 'message': '该股票已在自选中', 'data': existing.to_dict()})
    
    # 获取股票信息
    stock = StockBasic.query.filter_by(ts_code=ts_code).first()
    if not stock:
        return jsonify({'code': 404, 'message': '股票不存在', 'data': None}), 404
    
    item = UserWatchlist(
        user_id=user_id,
        ts_code=ts_code,
        stock_name=stock.name or '',
        market='SH' if ts_code.endswith('.SH') else 'BJ' if ts_code.endswith('.BJ') else 'SZ'
    )
    db.session.add(item)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'已将 {stock.name}({ts_code}) 加入自选',
        'data': item.to_dict()
    })


@api_bp.route('/watchlist/<path:ts_code>', methods=['DELETE'])
@api_error_handler(default_message='移除自选失败')
def remove_from_watchlist(ts_code):
    """从自选中移除股票"""
    from flask import g
    user_id = getattr(getattr(g, 'current_user', None), 'id', None)
    if not user_id:
        return jsonify({'code': 401, 'message': '请先登录', 'data': None}), 401
    
    from app.models import UserWatchlist
    from app.extensions import db
    
    item = UserWatchlist.query.filter_by(user_id=user_id, ts_code=ts_code).first()
    if not item:
        return jsonify({'code': 404, 'message': '该股票不在自选中', 'data': None}), 404
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '已从自选中移除', 'data': {'ts_code': ts_code}})
