# -*- coding: utf-8 -*-
from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import User, UserAnalysisRecord, UserChatHistory, UserWatchlist
from app.services.email_service import EmailService
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

MSG_VERIFY_CODE_SENT = '验证码已发送，请查收邮件。'
MSG_VERIFY_CODE_ERROR = '验证码错误或已过期，请重新获取。'
MSG_EMAIL_NOT_FOUND = '该账号未绑定此邮箱，无法找回密码。'




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


# ---- 注册（含邮箱验证） ----

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
        verify_code = request.form.get('verify_code', '').strip()

        # 基础校验
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

        # 邮箱验证码校验
        if not verify_code:
            flash('请输入邮箱验证码。', 'warning')
            return render_template('auth/register.html')

        ok, msg = EmailService.verify_code(EmailService.TYPE_REGISTER, email, verify_code)
        if not ok:
            flash(msg, 'danger')
            return render_template('auth/register.html')

        # 创建用户（已验证邮箱）
        user = User(username=username, email=email, phone=phone or None)
        user.email_verified = True
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        try:
            SystemLogService.write('register', f'Register: {user.username}, email_verified=True', user=user, status='success')
        except Exception:
            db.session.rollback()

        flash(MSG_REGISTER_SUCCESS, 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


# ---- 发送验证码（AJAX 接口 + 页面回退） ----

@auth_routes.route('/send-verify-code', methods=['POST'])
@_limiter.limit("6 per minute")  # 每分钟最多 6 次发送请求
def send_verify_code():
    """
    发送邮箱验证码。

    参数：
      code_type : register | reset_password | change_email
      email     : 目标邮箱地址

    返回 JSON：{code, message}
      AJAX 调用使用 JSON 响应。
      非 AJAX 回退时也返回 JSON（前端 JavaScript 处理）。
    """
    code_type = request.form.get('code_type', '').strip()
    email = request.form.get('email', '').strip()

    if not code_type:
        return jsonify({'code': 400, 'message': '缺少验证码类型。', 'data': None}), 400

    if not email or '@' not in email or '.' not in email:
        return jsonify({'code': 400, 'message': '请输入有效的邮箱地址。', 'data': None}), 400

    # 类型合法性检查
    valid_types = {EmailService.TYPE_REGISTER, EmailService.TYPE_RESET_PASSWORD, EmailService.TYPE_CHANGE_EMAIL}
    if code_type not in valid_types:
        return jsonify({'code': 400, 'message': '不支持的验证码类型。', 'data': None}), 400

    # 注册/改绑邮箱时检查是否已被占用
    if code_type == EmailService.TYPE_REGISTER:
        existing = User.query.filter_by(email=email.lower()).first()
        if existing:
            return jsonify({'code': 409, 'message': MSG_EMAIL_EXISTS, 'data': None}), 409

    if code_type == EmailService.TYPE_CHANGE_EMAIL:
        existing = User.query.filter_by(email=email.lower()).first()
        if existing:
            return jsonify({'code': 409, 'message': '该邮箱已被其他账号使用。', 'data': None}), 409

    # 找回密码时检查账号是否存在
    if code_type == EmailService.TYPE_RESET_PASSWORD:
        account = request.form.get('account', '').strip()
        if account:
            user = User.query.filter(or_(User.username == account, User.email == account.lower())).first()
            if not user:
                return jsonify({'code': 404, 'message': '该账号不存在。', 'data': None}), 404
            if user.email != email.lower():
                return jsonify({'code': 400, 'message': MSG_EMAIL_NOT_FOUND, 'data': None}), 400

    success, message = EmailService.send_verify_code(code_type, email)

    return jsonify({
        'code': 200 if success else 500,
        'message': message,
        'data': None,
    }), 200 if success else 500


# ---- 忘记密码（分两步：发验证码 → 验证+重置） ----

@auth_routes.route('/forgot-password', methods=['GET', 'POST'])
@_limiter.limit("3 per minute")
def forgot_password():
    """Step 1: 输入账号/邮箱，发送验证码到绑定邮箱"""
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        email = request.form.get('email', '').strip()

        if not account or not email:
            flash('请填写账号和绑定的邮箱地址。', 'warning')
            return render_template('auth/forgot_password.html')

        if '@' not in email or '.' not in email:
            flash(MSG_EMAIL_INVALID, 'warning')
            return render_template('auth/forgot_password.html')

        user = User.query.filter(or_(User.username == account, User.email == account.lower())).first()
        if not user:
            flash('该账号不存在。', 'danger')
            return render_template('auth/forgot_password.html')

        if user.email != email.lower():
            flash('该账号未绑定此邮箱，无法找回密码。', 'danger')
            return render_template('auth/forgot_password.html')

        # 发送重置验证码
        ok, msg = EmailService.send_verify_code(EmailService.TYPE_RESET_PASSWORD, email)
        if ok:
            flash(f'{msg} 请在页面中输入验证码和新密码完成重置。', 'success')
        else:
            flash(f'发送失败：{msg}', 'danger')

        # 将 account 和 email 传给模板（隐藏域保留）
        return render_template('auth/forgot_password.html',
                               _step2=True,
                               _account=account,
                               _email=email)

    return render_template('auth/forgot_password.html')


@auth_routes.route('/forgot-password/reset', methods=['POST'])
@_limiter.limit("6 per minute")
def forgot_password_reset():
    """Step 2: 输入验证码 + 新密码，完成重置"""
    account = request.form.get('account', '').strip()
    email = request.form.get('email', '').strip().lower()
    verify_code = request.form.get('verify_code', '').strip()
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not all([account, email, verify_code, new_password, confirm_password]):
        flash('请完整填写所有字段（账号、邮箱、验证码、新密码）。', 'warning')
        return render_template('auth/forgot_password.html',
                               _step2=True, _account=account, _email=email)

    # 校验验证码
    ok, msg = EmailService.verify_code(EmailService.TYPE_RESET_PASSWORD, email, verify_code)
    if not ok:
        flash(msg, 'danger')
        return render_template('auth/forgot_password.html',
                               _step2=True, _account=account, _email=email)

    # 新密码校验
    if new_password != confirm_password:
        flash('两次输入的新密码不一致。', 'warning')
        return render_template('auth/forgot_password.html',
                               _step2=True, _account=account, _email=email)

    if len(new_password) < 6:
        flash(MSG_PASSWORD_SHORT, 'warning')
        return render_template('auth/forgot_password.html',
                               _step2=True, _account=account, _email=email)

    # 查找用户并重置
    user = User.query.filter(or_(User.username == account, User.email == email)).first()
    if not user:
        flash('该账号不存在。', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user.set_password(new_password)
    db.session.commit()

    try:
        SystemLogService.write('password_reset', f'Password reset via email: {user.username}', user=user, status='success')
    except Exception:
        db.session.rollback()

    flash('密码已成功重置，请使用新密码登录。', 'success')
    return redirect(url_for('auth.login'))


# ---- 退出登录 ----

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



# ---- 个人中心 ----

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

    flash('密码已更新。', 'success')
    return redirect(url_for('auth.profile'))


@auth_routes.route('/profile/email', methods=['POST'])
@login_required
def change_email():
    """修改绑定邮箱：输入新邮箱 → 发送验证码 → 验证后更新"""
    new_email = request.form.get('new_email', '').strip().lower()
    verify_code = request.form.get('email_verify_code', '').strip()

    if not new_email:
        flash('请输入新的邮箱地址。', 'warning')
        return redirect(url_for('auth.profile'))

    if '@' not in new_email or '.' not in new_email:
        flash(MSG_EMAIL_INVALID, 'warning')
        return redirect(url_for('auth.profile'))

    if new_email == g.current_user.email:
        flash('新邮箱不能与当前邮箱相同。', 'warning')
        return redirect(url_for('auth.profile'))

    # 检查新邮箱是否被其他账号占用
    existing = User.query.filter_by(email=new_email).first()
    if existing:
        flash('该邮箱已被其他账号使用。', 'danger')
        return redirect(url_for('auth.profile'))

    if not verify_code:
        flash('请先发送并输入邮箱验证码。', 'warning')
        return redirect(url_for('auth.profile'))

    # 验证验证码
    ok, msg = EmailService.verify_code(EmailService.TYPE_CHANGE_EMAIL, new_email, verify_code)
    if not ok:
        flash(msg, 'danger')
        return redirect(url_for('auth.profile'))

    old_email = g.current_user.email
    g.current_user.email = new_email
    g.current_user.email_verified = True
    db.session.commit()

    try:
        SystemLogService.write('change_email',
                               f'Email changed: {old_email} -> {new_email}',
                               user=g.current_user, status='success')
    except Exception:
        db.session.rollback()

    flash(f'邮箱已成功更改为 {new_email}。', 'success')
    return redirect(url_for('auth.profile'))


# ---- 自选股 & 记录（保持不变） ----

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
