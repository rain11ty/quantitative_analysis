# -*- coding: utf-8 -*-
from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import User, UserAnalysisRecord, UserChatHistory, UserWatchlist
from app.services.system_log_service import SystemLogService
from app.services.user_activity_service import UserActivityService
from app.utils.auth import login_required

# 速率限制（生产环境生效，开发环境为空操作）
try:
    from flask_limiter import Limiter
    _limiter = Limiter(key_func=lambda: request.remote_addr)
except Exception:
    class _NoOpLimiter:
        def limit(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
    _limiter = _NoOpLimiter()


auth_routes = Blueprint('auth', __name__)


MSG_LOGIN_REQUIRED = '请先登录后再访问。'
MSG_LOGIN_INPUT = '请输入账号和密码。'
MSG_LOGIN_FAILED = '账号或密码错误。'
MSG_LOGIN_SUCCESS = '欢迎回来，{username}。'
MSG_REGISTER_REQUIRED = '请完整填写注册信息。'
MSG_USERNAME_SHORT = '用户名至少需要 3 个字符。'
MSG_EMAIL_INVALID = '请输入有效的邮箱地址。'
MSG_PASSWORD_SHORT = '密码至少需要 6 位。'
MSG_PASSWORD_MISMATCH = '两次输入的密码不一致。'
MSG_USERNAME_EXISTS = '用户名已存在。'
MSG_EMAIL_EXISTS = '该邮箱已被注册。'
MSG_REGISTER_SUCCESS = '注册成功，请登录。'
MSG_LOGOUT_SUCCESS = '你已安全退出登录。'
MSG_ACCOUNT_DISABLED = '当前账号已被管理员停用。'
MSG_ACCOUNT_BANNED = '当前账号已被管理员封禁。'




def _get_safe_redirect(default_endpoint='main.index'):
    next_page = (request.args.get('next') or request.form.get('next') or '').strip()
    if next_page.startswith('/') and not next_page.startswith('//'):
        return next_page
    return url_for(default_endpoint)


def _json_login_required_response():
    return jsonify({'code': 401, 'message': MSG_LOGIN_REQUIRED, 'data': None}), 401


@auth_routes.route('/login', methods=['GET', 'POST'])
@_limiter.limit("5 per minute")  # 防暴力破解：每分钟最多 5 次登录尝试
def login():
    if getattr(g, 'current_user', None):
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'

        if not account or not password:
            flash(MSG_LOGIN_INPUT, 'warning')
            return render_template('auth/login.html', next_page=_get_safe_redirect())

        user = User.query.filter(or_(User.username == account, User.email == account.lower())).first()

        if user is None or not user.check_password(password):
            flash(MSG_LOGIN_FAILED, 'danger')
            try:
                SystemLogService.write('login_failed', f'Login failed: {account}', user=None, status='failed')
            except Exception:
                db.session.rollback()
            return render_template('auth/login.html', next_page=_get_safe_redirect())

        if user.status in (User.STATUS_DISABLED, User.STATUS_BANNED):
            blocked_message = MSG_ACCOUNT_BANNED if user.status == User.STATUS_BANNED else MSG_ACCOUNT_DISABLED
            flash(blocked_message, 'danger')
            try:
                SystemLogService.write('login_blocked', f'Blocked account tried login: {user.username}, status={user.status}', user=user, status='failed')
            except Exception:
                db.session.rollback()
            return render_template('auth/login.html', next_page=_get_safe_redirect())


        session.clear()
        session.permanent = remember_me
        session['user_id'] = user.id

        user.last_login_at = db.func.now()
        user.last_login_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        db.session.commit()

        try:
            SystemLogService.write('login_success', f'User login: {user.username}', user=user, status='success')
        except Exception:
            db.session.rollback()

        flash(MSG_LOGIN_SUCCESS.format(username=user.username), 'success')
        return redirect(_get_safe_redirect())

    return render_template('auth/login.html', next_page=_get_safe_redirect())


@auth_routes.route('/register', methods=['GET', 'POST'])
@_limiter.limit("3 per minute")  # 防恶意注册：每分钟最多 3 次注册尝试
def register():
    if getattr(g, 'current_user', None):
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()

        if not username or not email or not password:
            flash(MSG_REGISTER_REQUIRED, 'warning')
            return render_template('auth/register.html')

        if len(username) < 3:
            flash(MSG_USERNAME_SHORT, 'warning')
            return render_template('auth/register.html')

        if '@' not in email or '.' not in email:
            flash(MSG_EMAIL_INVALID, 'warning')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash(MSG_PASSWORD_SHORT, 'warning')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash(MSG_PASSWORD_MISMATCH, 'warning')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash(MSG_USERNAME_EXISTS, 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash(MSG_EMAIL_EXISTS, 'danger')
            return render_template('auth/register.html')

        user = User(username=username, email=email, phone=phone or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(MSG_REGISTER_SUCCESS, 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_routes.route('/forgot-password', methods=['GET', 'POST'])
@_limiter.limit("3 per minute")  # 防密码重置滥用
def forgot_password():
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not account or not new_password or not confirm_password:
            flash('Please complete all required fields.', 'warning')
            return render_template('auth/forgot_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return render_template('auth/forgot_password.html')

        if len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'warning')
            return render_template('auth/forgot_password.html')

        user = User.query.filter(or_(User.username == account, User.email == account.lower())).first()
        if not user:
            flash('Account not found.', 'danger')
            return render_template('auth/forgot_password.html')

        user.set_password(new_password)
        db.session.commit()

        try:
            SystemLogService.write('password_reset', f'Password reset: {user.username}', user=user, status='success')
        except Exception:
            db.session.rollback()

        flash('Password has been reset. Please login again.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_routes.route('/logout')
def logout():
    current_user = getattr(g, 'current_user', None)
    if current_user:
        try:
            SystemLogService.write('logout', f'User logout: {current_user.username}', user=current_user, status='success')
        except Exception:
            db.session.rollback()

    session.clear()
    flash(MSG_LOGOUT_SUCCESS, 'info')
    return redirect(url_for('auth.login'))



@auth_routes.route('/profile')
@login_required
def profile():
    watchlist_items = UserWatchlist.query.filter_by(user_id=g.current_user.id).order_by(UserWatchlist.created_at.desc()).limit(12).all()
    analysis_records = UserAnalysisRecord.query.filter_by(user_id=g.current_user.id).order_by(UserAnalysisRecord.created_at.desc()).limit(8).all()
    chat_records = UserChatHistory.query.filter_by(user_id=g.current_user.id).order_by(UserChatHistory.created_at.desc()).limit(6).all()

    profile_stats = {
        'watchlist_count': UserWatchlist.query.filter_by(user_id=g.current_user.id).count(),
        'analysis_count': UserAnalysisRecord.query.filter_by(user_id=g.current_user.id).count(),
        'chat_count': UserChatHistory.query.filter_by(user_id=g.current_user.id).count(),
    }

    return render_template(
        'auth/profile.html',
        watchlist_items=watchlist_items,
        analysis_records=analysis_records,
        chat_records=chat_records,
        profile_stats=profile_stats,
    )


@auth_routes.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    nickname = request.form.get('nickname', '').strip()
    phone = request.form.get('phone', '').strip()
    avatar = request.form.get('avatar', '').strip()

    g.current_user.nickname = nickname or None
    g.current_user.phone = phone or None
    g.current_user.avatar = avatar or None
    db.session.commit()

    flash('个人资料已更新。', 'success')
    return redirect(url_for('auth.profile'))


@auth_routes.route('/profile/password', methods=['POST'])
@login_required
def update_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not g.current_user.check_password(current_password):
        flash('当前密码不正确。', 'danger')
        return redirect(url_for('auth.profile'))

    if len(new_password) < 6:
        flash('新密码至少需要 6 位。', 'warning')
        return redirect(url_for('auth.profile'))

    if new_password != confirm_password:
        flash('两次输入的新密码不一致。', 'warning')
        return redirect(url_for('auth.profile'))


    g.current_user.set_password(new_password)
    db.session.commit()

    flash('Password updated.', 'success')
    return redirect(url_for('auth.profile'))


@auth_routes.route('/profile/watchlist', methods=['POST'])
def add_watchlist():
    if not getattr(g, 'current_user', None):
        return _json_login_required_response()

    data = request.get_json(silent=True) or request.form
    ts_code = (data.get('ts_code') or '').strip().upper()
    stock_name = (data.get('stock_name') or '').strip()
    source = (data.get('source') or 'manual').strip() or 'manual'

    try:
        success, message, item = UserActivityService.add_to_watchlist(
            user_id=g.current_user.id,
            ts_code=ts_code,
            stock_name=stock_name,
            source=source,
        )
        return jsonify(
            {
                'code': 200 if success else 400,
                'message': message,
                'data': item.to_dict() if item else None,
            }
        ), 200 if success else 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'Add watchlist failed: {exc}', 'data': None}), 500


@auth_routes.route('/profile/watchlist/<ts_code>/delete', methods=['POST'])
@login_required
def remove_watchlist(ts_code):
    wants_json = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        success, message = UserActivityService.remove_from_watchlist(g.current_user.id, ts_code)
        category = 'success' if success else 'warning'
        if wants_json:
            return jsonify({'code': 200 if success else 404, 'message': message, 'data': None}), 200 if success else 404
        flash(message, category)
    except Exception as exc:
        db.session.rollback()
        if wants_json:
            return jsonify({'code': 500, 'message': f'Remove watchlist failed: {exc}', 'data': None}), 500
        flash(f'Remove watchlist failed: {exc}', 'danger')

    return redirect(url_for('auth.profile'))


@auth_routes.route('/profile/records/analysis', methods=['POST'])
def save_analysis_record():
    if not getattr(g, 'current_user', None):
        return _json_login_required_response()

    data = request.get_json(silent=True) or {}
    summary = (data.get('summary') or '').strip()
    module_name = (data.get('module_name') or 'Stock Analysis').strip()
    ts_code = (data.get('ts_code') or '').strip().upper()
    stock_name = (data.get('stock_name') or '').strip()

    if not summary:
        return jsonify({'code': 400, 'message': 'Summary is required.', 'data': None}), 400

    try:
        record = UserActivityService.record_analysis(
            user_id=g.current_user.id,
            module_name=module_name,
            summary=summary,
            ts_code=ts_code,
            stock_name=stock_name,
        )
        return jsonify({'code': 200, 'message': 'Saved to analysis history.', 'data': record.to_dict() if record else None})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'Save analysis failed: {exc}', 'data': None}), 500


@auth_routes.route('/profile/records/chat', methods=['POST'])
def save_chat_record():
    if not getattr(g, 'current_user', None):
        return _json_login_required_response()

    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    answer = (data.get('answer') or '').strip()

    if not question or not answer:
        return jsonify({'code': 400, 'message': 'Question and answer are required.', 'data': None}), 400

    try:
        record = UserActivityService.record_chat(
            user_id=g.current_user.id,
            question=question,
            answer=answer,
        )
        return jsonify({'code': 200, 'message': 'Saved to chat history.', 'data': record.to_dict() if record else None})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'Save chat failed: {exc}', 'data': None}), 500
