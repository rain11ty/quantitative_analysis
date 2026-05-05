# -*- coding: utf-8 -*-
import re

from flask import jsonify, request

from app.api import api_bp
from app.services.akshare_service import AkshareService
from app.services.market_overview_service import MarketOverviewService
from app.services.stock_service import StockService
from app.utils.api_helpers import api_error_handler, parse_int_param


def _validate_ts_code(ts_code):
    """Validate stock code format (e.g. 600519.SH, 000001.SZ, 833171.BJ)"""
    return bool(re.match(r'^[A-Za-z0-9.]+$', ts_code))


@api_bp.route('/stocks', methods=['GET'])
@api_error_handler(default_message='获取股票列表失败')
def get_stocks():
    industry = request.args.get('industry')
    area = request.args.get('area')
    search = request.args.get('search')
    page = parse_int_param(request.args.get('page'), 1, min_val=1)
    page_size = parse_int_param(request.args.get('page_size'), 20, min_val=1, max_val=100)

    # Screening parameter keys that trigger screen_stocks() when present
    _SCREEN_KEYS = (
        'pe_min', 'pe_max', 'pb_min', 'pb_max',
        'ps_min', 'ps_max', 'dv_min', 'dv_max',
        'mv_min', 'mv_max', 'circ_mv_min', 'circ_mv_max',
        'turnover_min', 'turnover_max',
        'volume_ratio_min', 'volume_ratio_max',
        'rsi6_min', 'rsi6_max',
        'kdj_k_min', 'kdj_k_max',
        'macd_min', 'macd_max',
        'cci_min', 'cci_max',
        'net_amount_min', 'net_amount_max',
        'lg_buy_rate_min', 'lg_buy_rate_max',
        'net_d5_amount_min', 'net_d5_amount_max',
        'market', 'trade_date',
    )

    has_screen_params = any(request.args.get(k) is not None for k in _SCREEN_KEYS)
    dc_raw = request.args.get('dynamic_conditions')
    has_screen_params = has_screen_params or dc_raw is not None

    if has_screen_params:
        criteria = {'page': page, 'page_size': page_size}
        if search:
            criteria['search'] = search
        if industry:
            criteria['industry'] = industry
        if area:
            criteria['area'] = area
        for k in _SCREEN_KEYS:
            val = request.args.get(k)
            if val is not None:
                criteria[k] = val
        # Parse dynamic_conditions from JSON string
        dc_raw = request.args.get('dynamic_conditions')
        if dc_raw:
            try:
                import json as _json
                criteria['dynamic_conditions'] = _json.loads(dc_raw)
            except (ValueError, TypeError):
                pass
        result = StockService.screen_stocks(criteria)
    else:
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
    """获取市场概览（优先读缓存，缓存未命中时实时获取）"""
    try:
        from app.utils.cache_utils import get_cache
        cached = get_cache().get('market_overview')
    except Exception:
        cached = None

    if cached is not None:
        status_code = 200 if cached.get('success') else 503
        return jsonify({'code': status_code, 'message': cached.get('message'), 'data': cached}), status_code

    # 缓存未命中，实时获取
    try:
        data = MarketOverviewService.get_market_overview()
        status_code = 200 if data.get('success') else 503
        return jsonify({'code': status_code, 'message': data.get('message'), 'data': data}), status_code
    except Exception:
        return jsonify({
            'code': 200,
            'message': '数据暂未就绪，请稍后重试',
            'data': {
                'success': False,
                'source': 'none',
                'items': [],
                'advancing': 0,
                'declining': 0,
                'flat': 0,
            },
        })


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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = parse_int_param(request.args.get('limit'), 60, min_val=1, max_val=5000)

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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = parse_int_param(request.args.get('limit'), 60, min_val=1, max_val=5000)

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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = parse_int_param(request.args.get('limit'), 30, min_val=1, max_val=5000)

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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = parse_int_param(request.args.get('limit'), 30, min_val=1, max_val=5000)

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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    trade_date = request.args.get('trade_date')
    limit_days = parse_int_param(request.args.get('limit_days'), 1, min_val=1, max_val=30)

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


# ========== 热门板块排行 ==========

@api_bp.route('/market/boards', methods=['GET'])
@api_error_handler(default_message='获取热门板块数据失败')
def get_market_boards():
    """获取热门板块排行（优先读缓存，缓存未命中时实时获取）"""
    board_type = (request.args.get('type') or 'industry').strip()
    if board_type not in ('industry', 'concept'):
        board_type = 'industry'
    # Support both legacy limit param and new page/page_size params
    page = parse_int_param(request.args.get('page'), 1, min_val=1)
    page_size = parse_int_param(request.args.get('page_size'), 20, min_val=1, max_val=100)
    limit = parse_int_param(request.args.get('limit'), None, min_val=1, max_val=500)
    if limit is not None:
        # Legacy mode: return first N items (no pagination)
        page = 1
        page_size = limit

    try:
        from app.utils.cache_utils import get_cache
        cached = get_cache().get(f'hot_boards_{board_type}')
    except Exception:
        cached = None

    if cached is not None:
        result = dict(cached)
        all_items = result.get('items', [])
        total = len(all_items)
        start = (page - 1) * page_size
        result['items'] = all_items[start:start + page_size]
        result['total'] = total
        result['page'] = page
        result['page_size'] = page_size
        return jsonify({'code': 200, 'message': 'success', 'data': result})

    # 缓存未命中，实时获取
    try:
        result = MarketOverviewService._fetch_board_ranking(board_type=board_type, limit=50)
        all_items = result.get('items', [])
        total = len(all_items)
        start = (page - 1) * page_size
        result['items'] = all_items[start:start + page_size]
        result['total'] = total
        result['page'] = page
        result['page_size'] = page_size
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception:
        return jsonify({
            'code': 200,
            'message': '板块数据暂未就绪，请稍后重试',
            'data': {
                'success': False,
                'board_type': board_type,
                'items': [],
                'total': 0,
                'update_time': '',
            },
        })


@api_bp.route('/areas', methods=['GET'])
@api_error_handler(default_message='获取地域列表失败')
def get_areas():
    result = StockService.get_area_list()
    return jsonify({'code': 200, 'message': 'success', 'data': result})


# ========== 板块资金流向排名 ==========

@api_bp.route('/market/sector-fund-flow', methods=['GET'])
@api_error_handler(default_message='获取板块资金流向数据失败')
def get_sector_fund_flow():
    """获取板块资金流向排名（优先读缓存，缓存未命中时实时获取）"""
    # Support both legacy limit param and new page/page_size params
    page = parse_int_param(request.args.get('page'), 1, min_val=1)
    page_size = parse_int_param(request.args.get('page_size'), 20, min_val=1, max_val=100)
    limit = parse_int_param(request.args.get('limit'), None, min_val=1, max_val=500)
    sort_order = (request.args.get('sort') or 'desc').strip()
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'
    if limit is not None:
        # Legacy mode: return first N items (no pagination)
        page = 1
        page_size = limit

    try:
        from app.utils.cache_utils import get_cache
        cached = get_cache().get('sector_fund_flow_rank')
    except Exception:
        cached = None

    if cached is not None:
        result = dict(cached)
        all_items = result.get('items', [])
        # Sort by main_net_inflow for outflow (asc) or inflow (desc).
        # Use reverse=True + float('-inf') for None so missing values
        # always sort to the end regardless of direction.
        if sort_order == 'asc':
            all_items = sorted(
                all_items,
                key=lambda x: x.get('main_net_inflow') if x.get('main_net_inflow') is not None else float('inf'),
            )
        else:
            all_items = sorted(
                all_items,
                key=lambda x: x.get('main_net_inflow') if x.get('main_net_inflow') is not None else float('-inf'),
                reverse=True,
            )
        total = len(all_items)
        start = (page - 1) * page_size
        result['items'] = all_items[start:start + page_size]
        result['total'] = total
        result['page'] = page
        result['page_size'] = page_size
        return jsonify({'code': 200, 'message': 'success', 'data': result})

    # 缓存未命中，实时获取
    try:
        result = MarketOverviewService.get_sector_fund_flow_rank()
        all_items = result.get('items', [])
        if sort_order == 'asc':
            all_items = sorted(
                all_items,
                key=lambda x: x.get('main_net_inflow') if x.get('main_net_inflow') is not None else float('inf'),
            )
        else:
            all_items = sorted(
                all_items,
                key=lambda x: x.get('main_net_inflow') if x.get('main_net_inflow') is not None else float('-inf'),
                reverse=True,
            )
        total = len(all_items)
        start = (page - 1) * page_size
        result['items'] = all_items[start:start + page_size]
        result['total'] = total
        result['page'] = page
        result['page_size'] = page_size
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception:
        return jsonify({
            'code': 200,
            'message': '板块资金流向数据暂未就绪，请稍后重试',
            'data': {
                'success': False,
                'items': [],
                'total': 0,
                'update_time': '',
            },
        })


# ========== 自选股相关接口 ==========

@api_bp.route('/market/index/<path:ts_code>/kline', methods=['GET'])
@api_error_handler(default_message='获取指数K线数据失败')
def get_index_kline(ts_code):
    """获取指数历史K线数据（优先读缓存，缓存未命中时实时获取）"""
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
    period = request.args.get('period', '1Y')
    if period not in ('1M', '3M', '6M', '1Y', '3Y'):
        period = '1Y'

    cache_key = f'index_kline_{ts_code}_{period}'
    try:
        from app.utils.cache_utils import get_cache
        cached = get_cache().get(cache_key)
    except Exception:
        cached = None

    if cached is not None:
        return jsonify({'code': 200, 'message': 'success', 'data': cached})

    # 缓存未命中，实时获取
    try:
        result = MarketOverviewService.get_index_kline(ts_code, period)
        return jsonify({'code': 200, 'message': 'success', 'data': result})
    except Exception:
        return jsonify({'code': 200, 'message': 'K线数据暂未就绪', 'data': {'success': False, 'kline': [], 'update_time': ''}})


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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
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
    if not _validate_ts_code(ts_code):
        return jsonify({'code': 400, 'message': 'Invalid stock code', 'data': None}), 400
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
