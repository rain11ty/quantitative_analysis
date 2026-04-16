# -*- coding: utf-8 -*-
from datetime import timedelta

from flask import Flask, flash, g, jsonify, redirect, request, session, url_for
from flask_cors import CORS

from config import config
from app.extensions import db
from app.utils.logger import setup_logger


PUBLIC_ENDPOINTS = {
    'auth.login',
    'auth.register',
    'auth.forgot_password',
    'admin.login',
    'static',
}

PUBLIC_PATH_PREFIXES = (
    '/static/',
    '/auth/login',
    '/auth/register',
    '/auth/forgot-password',
    '/admin/login',
)


def _is_public_request():
    if request.method == 'OPTIONS':
        return True

    endpoint = request.endpoint or ''
    if endpoint in PUBLIC_ENDPOINTS:
        return True

    path = request.path or ''
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _wants_json_response():
    if request.path.startswith('/api/'):
        return True

    accept = request.accept_mimetypes
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True

    if accept:
        return accept['application/json'] >= accept['text/html']
    return False


def _build_login_response(is_admin_entry=False, message='Please login first.', status_code=401):
    login_endpoint = 'admin.login' if is_admin_entry else 'auth.login'

    if _wants_json_response():
        return jsonify({'code': status_code, 'message': message, 'data': None}), status_code

    flash(message, 'warning')
    return redirect(url_for(login_endpoint, next=request.path))


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.permanent_session_lifetime = timedelta(days=7)
    app.config['JSON_AS_ASCII'] = False

    if hasattr(app, 'json'):
        app.json.ensure_ascii = False

    db.init_app(app)
    CORS(app)

    setup_logger(app.config['LOG_LEVEL'], app.config['LOG_FILE'])

    @app.after_request
    def ensure_utf8_charset(response):
        content_type = response.headers.get('Content-Type', '')
        utf8_mimetypes = (
            'text/html',
            'text/plain',
            'text/css',
            'text/javascript',
            'text/event-stream',
            'application/json',
            'application/javascript',
        )
        if any(content_type.startswith(mimetype) for mimetype in utf8_mimetypes):
            if 'charset=' not in content_type.lower():
                response.headers['Content-Type'] = f'{response.mimetype}; charset=utf-8'
        return response

    @app.context_processor
    def inject_auth_context():
        return {'current_user': getattr(g, 'current_user', None)}

    @app.before_request
    def load_current_user_and_guard_routes():
        g.current_user = None

        if request.method == 'OPTIONS':
            return None

        from app.models import User

        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user is None:
                session.clear()
            else:
                if user.status == User.STATUS_DISABLED:
                    session.clear()
                    if not _is_public_request():
                        return _build_login_response(
                            is_admin_entry=request.path.startswith('/admin'),
                            message='Current account is disabled.',
                            status_code=403,
                        )
                elif user.status == User.STATUS_BANNED:
                    session.clear()
                    if not _is_public_request():
                        return _build_login_response(
                            is_admin_entry=request.path.startswith('/admin'),
                            message='Current account is banned.',
                            status_code=403,
                        )
                else:
                    g.current_user = user

        if _is_public_request():
            return None

        if g.current_user is None:
            return _build_login_response(
                is_admin_entry=request.path.startswith('/admin'),
                message='\u8bf7\u5148\u767b\u5f55\u540e\u518d\u8bbf\u95ee\u3002',
                status_code=401,
            )

        if request.path.startswith('/admin') and not g.current_user.is_admin:
            if _wants_json_response():
                return jsonify({'code': 403, 'message': '\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650\u3002', 'data': None}), 403

            flash('\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650\u3002', 'danger')
            return redirect(url_for('main.index'))

        return None

    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth_routes import auth_routes
    app.register_blueprint(auth_routes, url_prefix='/auth')

    from app.routes.admin_routes import admin_routes
    app.register_blueprint(admin_routes)

    return app
