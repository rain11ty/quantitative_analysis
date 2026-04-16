from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
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
from app.utils.auth import admin_required


admin_routes = Blueprint('admin', __name__, url_prefix='/admin')


def _write_admin_log(action_type, message, status='success'):
    try:
        SystemLogService.write(action_type, message, user=g.current_user, status=status)
    except Exception:
        db.session.rollback()


@admin_routes.route('/login', methods=['GET', 'POST'])
def login():
    current_user = getattr(g, 'current_user', None)
    if request.method == 'GET' and current_user and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        session.clear()
        if current_user is not None:
            g.current_user = None

        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter(or_(User.username == account, User.email == account.lower())).first()
        if not user or not user.check_password(password):
            flash('Invalid admin account or password.', 'danger')
            return render_template('admin/login.html')

        if not user.is_admin:
            flash('This account is not an admin account.', 'danger')
            return render_template('admin/login.html')

        if user.status == User.STATUS_DISABLED:
            flash('This admin account is disabled.', 'danger')
            return render_template('admin/login.html')

        if user.status == User.STATUS_BANNED:
            flash('This admin account is banned.', 'danger')
            return render_template('admin/login.html')

        session.clear()
        session.permanent = True
        session['user_id'] = user.id

        user.last_login_at = db.func.now()
        user.last_login_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        db.session.commit()

        try:
            SystemLogService.write('admin_login', f'Admin login: {user.username}', user=user, status='success')
        except Exception:
            db.session.rollback()

        flash(f'Welcome to admin panel, {user.username}.', 'success')
        return redirect(url_for('admin.dashboard'))

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
    query = User.query
    if keyword:
        query = query.filter(or_(User.username.ilike(f'%{keyword}%'), User.email.ilike(f'%{keyword}%')))

    users_data = query.order_by(User.created_at.desc()).all()
    available_statuses = [User.STATUS_ACTIVE, User.STATUS_DISABLED, User.STATUS_BANNED]
    return render_template('admin/users.html', users=users_data, keyword=keyword, available_statuses=available_statuses)


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

    query = SystemLog.query
    if action_type:
        query = query.filter(SystemLog.action_type == action_type)
    if status:
        query = query.filter(SystemLog.status == status)

    rows = query.order_by(SystemLog.created_at.desc()).limit(300).all()
    action_types = [item[0] for item in db.session.query(SystemLog.action_type).distinct().all() if item[0]]
    return render_template(
        'admin/logs.html',
        logs=rows,
        action_types=action_types,
        selected_action=action_type,
        selected_status=status,
    )


@admin_routes.route('/data')
@admin_required
def data_center():
    data_stats = {
        'stock_basic_count': StockBasic.query.count(),
        'minute_data_count': StockMinuteData.query.count(),
    }
    return render_template('admin/data.html', data_stats=data_stats)


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
