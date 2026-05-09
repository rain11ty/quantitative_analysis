# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    StockBasic,
    StockMinuteData,
    SystemLog,
    User,
    UserAnalysisRecord,
    UserChatHistory,
    UserWatchlist,
)
from app.services.minute_data_sync_service import MinuteDataSyncService
from app.services.system_log_service import SystemLogService
from app.services.market_overview_service import MarketOverviewService
from app.services.akshare_service import AkshareService
from app.utils.auth import admin_required


admin_routes = Blueprint('admin', __name__, url_prefix='/admin')


def _write_admin_log(action_type, message, status='success'):
    try:
        SystemLogService.write(action_type, message, user=g.current_user, status=status)
    except Exception:
        db.session.rollback()


def _get_data_overview_stats():
    """获取数据概览统计（data_center 和 api_data_overview 共用）。"""
    from sqlalchemy import text

    data_stats = {}
    table_names = [
        ('stock_basic', '股票基础信息'),
        ('stock_daily_basic', '每日基本面'),
        ('stock_daily_history', '日线行情'),
        ('stock_factor', '技术指标'),
        ('stock_moneyflow', '资金流向'),
        ('stock_business', '选股宽表'),
        ('stock_minute_data', '分钟数据'),
        ('stock_trade_calendar', '交易日历'),
    ]

    db_name = db.engine.url.database

    with db.engine.connect() as conn:
        # 使用 information_schema 快速获取行数估计值，避免大表 COUNT(*) 全表扫描
        for table_name, label in table_names:
            try:
                r = conn.execute(
                    text("SELECT TABLE_ROWS FROM information_schema.TABLES "
                         "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl"),
                    {'db': db_name, 'tbl': table_name},
                )
                row = r.fetchone()
                count = row[0] if row else -1
            except Exception:
                count = -1
            data_stats[table_name] = {'count': count, 'label': label}

        # 获取 stock_business 最新交易日
        try:
            r = conn.execute(text('SELECT MAX(trade_date) FROM stock_business'))
            data_stats['stock_business']['latest_date'] = r.scalar()
        except Exception:
            data_stats['stock_business']['latest_date'] = None

        # 获取各源表最新交易日
        for tbl in ['stock_daily_basic', 'stock_daily_history', 'stock_factor', 'stock_moneyflow']:
            try:
                r = conn.execute(text(f'SELECT MAX(trade_date) FROM `{tbl}`'))
                data_stats[tbl]['latest_date'] = r.scalar()
            except Exception:
                data_stats[tbl]['latest_date'] = None

    # 同步状态：查最近的关键操作记录
    def _latest_log(action_type_list):
        return SystemLog.query.filter(
            SystemLog.action_type.in_(action_type_list)
        ).order_by(SystemLog.created_at.desc()).first()

    latest_incremental = _latest_log(['daily_incremental_update'])
    latest_wide_sync = _latest_log(['sync_stock_business', 'admin_sync_wide_table'])
    latest_health = _latest_log(['data_health_check'])

    sync_status = {
        'incremental': {
            'time': latest_incremental.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest_incremental else None,
            'status': latest_incremental.status if latest_incremental else 'unknown',
            'message': latest_incremental.message if latest_incremental else '暂无记录',
        },
        'wide_sync': {
            'time': latest_wide_sync.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest_wide_sync else None,
            'status': latest_wide_sync.status if latest_wide_sync else 'unknown',
            'message': latest_wide_sync.message if latest_wide_sync else '暂无记录',
        },
        'health': {
            'time': latest_health.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest_health else None,
            'status': latest_health.status if latest_health else 'unknown',
            'message': latest_health.message if latest_health else '暂无记录',
        },
    }

    # 缓存同步状态（从 Redis 读取）
    cache_status = {}
    try:
        from app.utils.cache_utils import get_cache
        cache = get_cache()

        # 市场概览缓存
        market_overview = cache.get('market_overview')
        if market_overview:
            cache_status['market_overview'] = {
                'trade_date': market_overview.get('trade_date', ''),
                'update_time': market_overview.get('update_time', ''),
                'source': market_overview.get('source', ''),
                'success': market_overview.get('success', False),
            }
        else:
            cache_status['market_overview'] = {'trade_date': '', 'update_time': '', 'source': '', 'success': False}

        # 涨跌排行缓存
        ranking_pct = cache.get('realtime_ranking_pct_change')
        if ranking_pct:
            cache_status['ranking'] = {
                'update_time': ranking_pct.get('update_time', ''),
                'count': len(ranking_pct.get('items', [])),
            }
        else:
            cache_status['ranking'] = {'update_time': '', 'count': 0}

        # 新闻缓存
        news = cache.get('news_aggregate:all')
        if news:
            cache_status['news'] = {
                'update_time': news.get('update_time', ''),
                'count': news.get('count', 0),
            }
        else:
            cache_status['news'] = {'update_time': '', 'count': 0}

        # 板块排行缓存
        boards_industry = cache.get('hot_boards_industry')
        if boards_industry:
            cache_status['boards'] = {
                'update_time': boards_industry.get('update_time', ''),
                'count': len(boards_industry.get('items', [])),
            }
        else:
            cache_status['boards'] = {'update_time': '', 'count': 0}

        # 资金流向缓存
        sector_flow = cache.get('sector_fund_flow')
        if sector_flow:
            cache_status['sector_flow'] = {
                'update_time': sector_flow.get('update_time', ''),
                'count': len(sector_flow.get('items', [])),
            }
        else:
            cache_status['sector_flow'] = {'update_time': '', 'count': 0}
    except Exception as exc:
        from loguru import logger
        logger.warning(f'读取缓存状态失败: {exc}')
        cache_status = {
            'market_overview': {'trade_date': '', 'update_time': '', 'source': '', 'success': False},
            'ranking': {'update_time': '', 'count': 0},
            'news': {'update_time': '', 'count': 0},
            'boards': {'update_time': '', 'count': 0},
            'sector_flow': {'update_time': '', 'count': 0},
        }

    # 最近同步日志
    sync_action_types = [
        'sync_stock_business', 'admin_sync_stock_data',
        'daily_incremental_update', 'data_health_check',
        'admin_sync_wide_table',
        'admin_refresh_market_overview',
        'admin_refresh_ranking',
        'admin_refresh_news',
        'admin_refresh_boards',
        'admin_refresh_sector_flow',
    ]
    sync_logs = SystemLog.query.filter(
        SystemLog.action_type.in_(sync_action_types)
    ).order_by(SystemLog.created_at.desc()).limit(20).all()

    return data_stats, sync_status, sync_logs, cache_status


@admin_routes.route('/login', methods=['GET', 'POST'])
def login():
    # 统一登录入口：管理员登录页面跳转到普通登录页
    return redirect(url_for('auth.login', next='/admin/'))

    return render_template('admin/login.html')


@admin_routes.route('/logout')
@admin_required
def logout():
    _write_admin_log('admin_logout', f'Admin logout: {g.current_user.username}')
    session.clear()
    flash('Admin logged out.', 'info')
    return redirect(url_for('admin.login'))


@admin_routes.route('/')
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(status=User.STATUS_ACTIVE).count()
    disabled_users = User.query.filter_by(status=User.STATUS_DISABLED).count()
    banned_users = User.query.filter_by(status=User.STATUS_BANNED).count()
    admin_count = User.query.filter_by(role=User.ROLE_ADMIN).count()
    total_watchlist = UserWatchlist.query.count()
    total_analysis = UserAnalysisRecord.query.count()
    total_chat = UserChatHistory.query.count()
    total_stocks = StockBasic.query.count()
    total_minute_rows = StockMinuteData.query.count()
    total_logs = SystemLog.query.count()

    latest_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(12).all()

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'disabled_users': disabled_users,
        'banned_users': banned_users,
        'admin_count': admin_count,
        'total_watchlist': total_watchlist,
        'total_analysis': total_analysis,
        'total_chat': total_chat,
        'total_stocks': total_stocks,
        'total_minute_rows': total_minute_rows,
        'total_logs': total_logs,
    }

    return render_template('admin/dashboard.html', stats=stats, latest_logs=latest_logs)


@admin_routes.route('/users')
@admin_required
def users():
    keyword = (request.args.get('keyword') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(50, max(10, request.args.get('per_page', 20, type=int)))
    query = User.query
    if keyword:
        from app.utils.sql_utils import escape_like
        safe_kw = escape_like(keyword)
        query = query.filter(or_(User.username.ilike(f'%{safe_kw}%', escape='\\'), User.email.ilike(f'%{safe_kw}%', escape='\\')))

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    available_statuses = [User.STATUS_ACTIVE, User.STATUS_DISABLED, User.STATUS_BANNED]
    return render_template('admin/users.html',
                           users=pagination.items,
                           keyword=keyword,
                           available_statuses=available_statuses,
                           pagination=pagination)


@admin_routes.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    watchlist_items = UserWatchlist.query.filter_by(user_id=user.id).order_by(UserWatchlist.created_at.desc()).limit(10).all()
    analysis_records = UserAnalysisRecord.query.filter_by(user_id=user.id).order_by(UserAnalysisRecord.created_at.desc()).limit(10).all()
    chat_records = UserChatHistory.query.filter_by(user_id=user.id).order_by(UserChatHistory.created_at.desc()).limit(10).all()

    return render_template(
        'admin/user_detail.html',
        user=user,
        watchlist_items=watchlist_items,
        analysis_records=analysis_records,
        chat_records=chat_records,
    )


@admin_routes.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == g.current_user.id:
        flash('Cannot disable current admin account.', 'warning')
        return redirect(url_for('admin.users'))

    user.status = User.STATUS_DISABLED if user.status == User.STATUS_ACTIVE else User.STATUS_ACTIVE
    db.session.commit()
    _write_admin_log(
        'admin_toggle_user_status',
        f'Admin {g.current_user.username} changed {user.username} status to {user.status}',
    )
    flash(f'User {user.username} status updated to {user.status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_routes.route('/users/<int:user_id>/set-status', methods=['POST'])
@admin_required
def set_user_status(user_id):
    user = User.query.get_or_404(user_id)
    new_status = (request.form.get('status') or '').strip()
    allowed_statuses = {User.STATUS_ACTIVE, User.STATUS_DISABLED, User.STATUS_BANNED}

    if new_status not in allowed_statuses:
        flash('Invalid status value.', 'danger')
        return redirect(url_for('admin.users'))

    if user.id == g.current_user.id and new_status != User.STATUS_ACTIVE:
        flash('Cannot disable or ban current admin account.', 'warning')
        return redirect(url_for('admin.users'))

    user.status = new_status
    db.session.commit()
    _write_admin_log(
        'admin_set_user_status',
        f'Admin {g.current_user.username} changed {user.username} status to {user.status}',
    )
    flash(f'User {user.username} status updated to {user.status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_routes.route('/users/<int:user_id>/set-role', methods=['POST'])
@admin_required
def set_user_role(user_id):
    user = User.query.get_or_404(user_id)
    role = (request.form.get('role') or User.ROLE_USER).strip()
    if role not in (User.ROLE_USER, User.ROLE_ADMIN):
        flash('Invalid role value.', 'danger')
        return redirect(url_for('admin.users'))

    user.role = role
    db.session.commit()
    _write_admin_log(
        'admin_set_user_role',
        f'Admin {g.current_user.username} changed {user.username} role to {user.role}',
    )
    flash(f'User {user.username} role updated to {user.role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_routes.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == g.current_user.id:
        flash('Cannot delete current admin account.', 'warning')
        return redirect(url_for('admin.users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    _write_admin_log(
        'admin_delete_user',
        f'Admin {g.current_user.username} deleted user {username}',
    )
    flash(f'User {username} deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_routes.route('/logs')
@admin_required
def logs():
    action_type = (request.args.get('action_type') or '').strip()
    status = (request.args.get('status') or '').strip()
    user_id = (request.args.get('user_id') or '').strip()
    start_date = (request.args.get('start_date') or '').strip()
    end_date = (request.args.get('end_date') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 20

    query = SystemLog.query
    if action_type:
        query = query.filter(SystemLog.action_type == action_type)
    if status:
        query = query.filter(SystemLog.status == status)
    if user_id:
        try:
            query = query.filter(SystemLog.user_id == int(user_id))
        except (ValueError, TypeError):
            pass
    if start_date:
        from datetime import datetime as dt_cls, timedelta
        try:
            start_dt = dt_cls.strptime(start_date, '%Y-%m-%d')
            query = query.filter(SystemLog.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime as dt_cls, timedelta
        try:
            end_dt = dt_cls.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(SystemLog.created_at < end_dt)
        except ValueError:
            pass

    pagination = query.order_by(SystemLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    action_types = [item[0] for item in db.session.query(SystemLog.action_type).distinct().all() if item[0]]
    return render_template(
        'admin/logs.html',
        logs=pagination.items,
        pagination=pagination,
        action_types=action_types,
        selected_action=action_type,
        selected_status=status,
        selected_user_id=user_id,
        selected_start_date=start_date,
        selected_end_date=end_date,
    )


@admin_routes.route('/data')
@admin_required
def data_center():
    data_stats, sync_status, sync_logs, cache_status = _get_data_overview_stats()
    return render_template('admin/data.html',
                           data_stats=data_stats,
                           sync_logs=sync_logs,
                           sync_status=sync_status,
                           cache_status=cache_status)


@admin_routes.route('/data/sync-wide', methods=['POST'])
@admin_required
def sync_wide_table():
    """触发 stock_business 宽表同步（表单提交，兼容旧方式）"""
    days = request.form.get('days', 30, type=int)
    full = request.form.get('full', 'false') == 'true'

    try:
        from app.tasks import sync_stock_business_wide
        task = sync_stock_business_wide.delay(days=days, full=full)
        _write_admin_log(
            'admin_sync_wide_table',
            f'Admin {g.current_user.username} triggered stock_business sync: days={days}, full={full}',
        )
        flash(f'宽表同步任务已提交（任务ID: {task.id}），预计 5-15 分钟完成。', 'success')
    except Exception as exc:
        flash(f'任务提交失败: {exc}', 'danger')

    return redirect(url_for('admin.data_center'))


@admin_routes.route('/data/sync-one', methods=['POST'])
@admin_required
def sync_one_stock():
    ts_code = (request.form.get('ts_code') or '').strip().upper()
    period_type = (request.form.get('period_type') or '1min').strip()

    if not ts_code:
        flash('Please input a stock code like 000001.SZ.', 'warning')
        return redirect(url_for('admin.data_center'))

    try:
        with MinuteDataSyncService() as manager:
            result = manager.sync_single_stock_data(ts_code=ts_code, period_type=period_type)

        if result.get('success'):
            flash(f'Sync success: {ts_code}, rows={result.get("data_count", 0)}.', 'success')
            status = 'success'
        else:
            flash(f'Sync failed: {result.get("message")}', 'danger')
            status = 'failed'

        _write_admin_log(
            'admin_sync_stock_data',
            f'Admin {g.current_user.username} sync {ts_code} {period_type}: {result.get("message")}',
            status=status,
        )
    except Exception as exc:
        db.session.rollback()
        flash(f'Sync error: {exc}', 'danger')

    return redirect(url_for('admin.data_center'))


# ======================== 数据中心 API ========================

@admin_routes.route('/data/api/overview', methods=['GET'])
@admin_required
def api_data_overview():
    """返回数据概览 JSON，供前端 AJAX 刷新使用"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    data_stats, sync_status, sync_logs, cache_status = _get_data_overview_stats()
    return jsonify({
        'data_stats': data_stats,
        'sync_status': sync_status,
        'sync_logs': [log.to_dict() for log in sync_logs],
        'cache_status': cache_status,
    })


@admin_routes.route('/data/api/sync-business', methods=['POST'])
@admin_required
def api_sync_business():
    """API: 触发宽表同步（AJAX 调用）"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    data = request.get_json(silent=True) or {}
    days = data.get('days', 30)
    full = data.get('full', False)

    try:
        from app.tasks import sync_stock_business_wide
        task = sync_stock_business_wide.delay(days=int(days), full=bool(full))
        _write_admin_log(
            'admin_sync_wide_table',
            f'Admin {g.current_user.username} triggered stock_business sync via API: days={days}, full={full}',
        )
        return jsonify({
            'success': True,
            'message': f'宽表同步任务已提交（任务ID: {task.id}），预计 5-15 分钟完成。',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/health-check', methods=['POST'])
@admin_required
def api_health_check():
    """API: 触发数据健康检查（AJAX 调用）"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import run_data_health_check
        task = run_data_health_check.delay()
        _write_admin_log(
            'admin_health_check',
            f'Admin {g.current_user.username} triggered data health check via API',
        )
        return jsonify({
            'success': True,
            'message': f'健康检查任务已提交（任务ID: {task.id}），请稍后刷新查看结果。',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


# ======================== 缓存手动刷新 API ========================

@admin_routes.route('/data/api/refresh-market-overview', methods=['POST'])
@admin_required
def api_refresh_market_overview():
    """API: 手动刷新市场概览缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import refresh_market_overview_cache
        task = refresh_market_overview_cache.delay()
        _write_admin_log(
            'admin_refresh_market_overview',
            f'Admin {g.current_user.username} triggered market overview refresh',
        )
        return jsonify({
            'success': True,
            'message': '市场概览缓存刷新任务已提交',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/refresh-ranking', methods=['POST'])
@admin_required
def api_refresh_ranking():
    """API: 手动刷新涨跌排行缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import refresh_ranking_cache
        task = refresh_ranking_cache.delay()
        _write_admin_log(
            'admin_refresh_ranking',
            f'Admin {g.current_user.username} triggered ranking refresh',
        )
        return jsonify({
            'success': True,
            'message': '涨跌排行缓存刷新任务已提交',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/refresh-news', methods=['POST'])
@admin_required
def api_refresh_news():
    """API: 手动刷新新闻缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import refresh_news_cache
        task = refresh_news_cache.delay()
        _write_admin_log(
            'admin_refresh_news',
            f'Admin {g.current_user.username} triggered news refresh',
        )
        return jsonify({
            'success': True,
            'message': '新闻缓存刷新任务已提交',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/refresh-boards', methods=['POST'])
@admin_required
def api_refresh_boards():
    """API: 手动刷新板块排行缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import refresh_board_ranking_cache
        task = refresh_board_ranking_cache.delay()
        _write_admin_log(
            'admin_refresh_boards',
            f'Admin {g.current_user.username} triggered boards ranking refresh',
        )
        return jsonify({
            'success': True,
            'message': '板块排行缓存刷新任务已提交',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/refresh-sector-flow', methods=['POST'])
@admin_required
def api_refresh_sector_flow():
    """API: 手动刷新资金流向缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import refresh_sector_fund_flow_cache
        task = refresh_sector_fund_flow_cache.delay()
        _write_admin_log(
            'admin_refresh_sector_flow',
            f'Admin {g.current_user.username} triggered sector fund flow refresh',
        )
        return jsonify({
            'success': True,
            'message': '资金流向缓存刷新任务已提交',
            'task_id': task.id,
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


@admin_routes.route('/data/api/refresh-all-cache', methods=['POST'])
@admin_required
def api_refresh_all_cache():
    """API: 一键刷新所有缓存"""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'success': False, 'message': '非法请求'}), 400

    try:
        from app.tasks import (
            refresh_market_overview_cache,
            refresh_ranking_cache,
            refresh_news_cache,
            refresh_board_ranking_cache,
            refresh_sector_fund_flow_cache,
        )
        tasks = []
        tasks.append(refresh_market_overview_cache.delay())
        tasks.append(refresh_ranking_cache.delay())
        tasks.append(refresh_news_cache.delay())
        tasks.append(refresh_board_ranking_cache.delay())
        tasks.append(refresh_sector_fund_flow_cache.delay())

        _write_admin_log(
            'admin_refresh_all_cache',
            f'Admin {g.current_user.username} triggered all cache refresh',
        )
        return jsonify({
            'success': True,
            'message': f'所有缓存刷新任务已提交（{len(tasks)} 个任务）',
            'task_ids': [t.id for t in tasks],
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'任务提交失败: {exc}'}), 500


# ======================== 系统自检 ========================

@admin_routes.route('/system-check')
@admin_required
def system_check():
    """系统自检页面"""
    return render_template('admin/health_check.html')


@admin_routes.route('/api/system-check', methods=['POST'])
@admin_required
def api_system_check():
    """执行系统自检，返回各组件连通性状态"""
    import time as _time

    results = {
        'overall': 'ok',
        'checked_at': _time.strftime('%Y-%m-%d %H:%M:%S'),
        'components': {},
    }

    # 1. 数据库
    try:
        db.session.execute(db.text('SELECT 1'))
        results['components']['database'] = {
            'status': 'ok',
            'label': 'MySQL 数据库',
            'message': '连接正常',
        }
    except Exception as e:
        results['overall'] = 'degraded'
        results['components']['database'] = {
            'status': 'error',
            'label': 'MySQL 数据库',
            'message': str(e)[:200],
        }

    # 2. Redis
    try:
        from app.extensions import redis_client
        if redis_client is not None:
            redis_client.ping()
            results['components']['redis'] = {
                'status': 'ok',
                'label': 'Redis 缓存',
                'message': '连接正常',
            }
        else:
            results['components']['redis'] = {
                'status': 'disabled',
                'label': 'Redis 缓存',
                'message': '未启用，使用内存缓存',
            }
    except Exception as e:
        results['overall'] = 'degraded'
        results['components']['redis'] = {
            'status': 'error',
            'label': 'Redis 缓存',
            'message': str(e)[:200],
        }

    # 3. Tushare
    try:
        ts_result = MarketOverviewService.ping_tushare()
        if ts_result.get('success'):
            results['components']['tushare'] = {
                'status': 'ok',
                'label': 'Tushare Pro',
                'message': ts_result.get('message', '连接正常'),
                'detail': {
                    'proxy_url': ts_result.get('proxy_url', ''),
                    'latest_trade_date': ts_result.get('latest_trade_date', ''),
                },
            }
        else:
            results['overall'] = 'degraded'
            results['components']['tushare'] = {
                'status': 'error',
                'label': 'Tushare Pro',
                'message': ts_result.get('message', '连接失败'),
                'detail': {
                    'proxy_url': ts_result.get('proxy_url', ''),
                },
            }
    except Exception as e:
        results['overall'] = 'degraded'
        results['components']['tushare'] = {
            'status': 'error',
            'label': 'Tushare Pro',
            'message': str(e)[:200],
        }

    # 4. AkShare / 新浪快照
    try:
        ak_result = AkshareService.ping()
        if ak_result.get('success'):
            results['components']['akshare'] = {
                'status': 'ok',
                'label': 'AkShare / 新浪快照',
                'message': ak_result.get('message', '连接正常'),
                'detail': {
                    'source': ak_result.get('source', ''),
                    'spot_count': ak_result.get('spot_count', 0),
                    'proxy': ak_result.get('proxy', ''),
                },
            }
        else:
            results['overall'] = 'degraded'
            results['components']['akshare'] = {
                'status': 'error',
                'label': 'AkShare / 新浪快照',
                'message': ak_result.get('message', '连接失败'),
                'detail': {
                    'source': ak_result.get('source', ''),
                    'proxy': ak_result.get('proxy', ''),
                },
            }
    except Exception as e:
        results['overall'] = 'degraded'
        results['components']['akshare'] = {
            'status': 'error',
            'label': 'AkShare / 新浪快照',
            'message': str(e)[:200],
        }

    return jsonify(results)
