# -*- coding: utf-8 -*-
import os
from datetime import timedelta

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    Limiter = None

    def get_remote_address():
        return request.remote_addr

from config import config
from app.extensions import db, init_redis
from app.utils.logger import setup_logger


PUBLIC_ENDPOINTS = {
    'main.index',
    'main.news',
    'main.ai_assistant',
    'auth.login',
    'auth.register',
    'auth.send_verify_code',
    'auth.forgot_password',
    'admin.login',
    'static',
    'healthz',
    'metrics',
    'api.get_stock_realtime',
    'api.get_monitor_stock_detail',
    'api.get_monitor_dashboard',
    'api.get_market_overview',
    'api.ping_market_api',
    'api.ping_akshare_api',
    'api.ai_status',
    'api.get_stocks',
    'api.get_stock_detail',
    'api.get_stock_history',
    'api.get_stock_factors',
    'api.get_stock_moneyflow',
    'api.get_stock_cyq',
    'api.get_index_kline',
    'api.get_monitor_intraday',
    'api.get_realtime_ranking',
    'api.get_industries',
    'api.get_areas',
    'api.get_news',
    'api.get_news_cjzc',
    'api.get_news_global',
}

PUBLIC_PATH_PREFIXES = (
    '/static/',
    '/auth/login',
    '/auth/register',
    '/auth/send-verify-code',
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

    # 初始化 Redis（连接失败自动降级为内存缓存）
    init_redis(app)
    from app.utils.cache_utils import init_cache
    init_cache(app)

    # 初始化邮件服务
    from app.extensions import init_mail
    init_mail(app)

    from loguru import logger

    # --- CORS 配置 ---
    # 开发环境允许所有来源；生产环境必须限定白名单
    if app.config.get('DEBUG', False):
        CORS(app)  # 开发模式全开
        logger.info("[CORS] 开发模式：允许所有来源")
    else:
        cors_origins = os.getenv('CORS_ORIGINS', '').split(',')
        cors_origins = [o.strip() for o in cors_origins if o.strip()]
        if not cors_origins:
            cors_origins = []  # 空白名单，仅允许同源
            logger.warning("[CORS] 生产环境未设置 CORS_ORIGINS 环境变量，将仅允许同源请求！"
                        " 请通过环境变量配置：CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com")
        else:
            logger.info(f"[CORS] 生产模式允许来源: {cors_origins}")
        if cors_origins:
            CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)
        else:
            # 不注册 CORS，默认仅同源
            pass
    
    # --- API 速率限制 ---
    # 开发环境不启用速率限制；生产环境对敏感接口限流
    limiter = None
    if not app.config.get('DEBUG', False) and Limiter is not None:
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=["200 per minute"],       # 全局默认：每分钟 200 次请求
            storage_uri="memory://",                 # 内存存储（单机够用）
            strategy="fixed-window",                 # 固定窗口算法
        )
        # 自定义超限响应（统一 JSON 格式，不泄露内部信息）
        @limiter.request_filter
        def exempt_options():
            return request.method == 'OPTIONS'
    else:
        if not app.config.get('DEBUG', False) and Limiter is None:
            logger.warning("Flask-Limiter is not installed; rate limiting is disabled.")

        class _NoOpLimiter:
            def limit(self, *a, **kw):
                def decorator(fn):
                    return fn
                return decorator

            def request_filter(self, fn):
                return fn

        limiter = _NoOpLimiter()

    setup_logger(app.config['LOG_LEVEL'], app.config['LOG_FILE'])

    # --- Sentry 错误监控 ---
    sentry_dsn = os.getenv('SENTRY_DSN', '')
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
                environment=os.getenv('FLASK_ENV', 'production'),
                release='1.0.0',
            )
            logger.info("[Sentry] 错误监控已激活")
        except ImportError:
            logger.warning("[Sentry] sentry-sdk 未安装，跳过初始化")

    # --- Prometheus 指标 ---
    try:
        from prometheus_flask_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint='/metrics')
        logger.info("[Prometheus] /metrics 端点已启用")
    except ImportError:
        logger.warning("[Prometheus] prometheus_flask_instrumentator 未安装，跳过")

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
        return {
            'current_user': getattr(g, 'current_user', None),
            'v': app.config.get('STATIC_VERSION', ''),
        }

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

    # --- 健康检查端点 /healthz ---
    @app.route('/healthz')
    def healthz():
        """健康检查：返回 DB 连接状态 + Redis 状态 + 应用版本"""
        import time
        from datetime import datetime

        status = {
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'uptime_s': int(time.time() - getattr(app, '_start_time', time.time())),
            'version': '1.0.0',
            'components': {},
        }

        # 检查数据库连接
        try:
            db.session.execute(db.text('SELECT 1'))
            status['components']['database'] = {'status': 'ok'}
        except Exception as e:
            status['status'] = 'degraded'
            status['components']['database'] = {'status': 'error', 'message': str(e)}

        # 检查 Redis 连接
        try:
            from app.extensions import redis_client
            if redis_client is not None:
                redis_client.ping()
                status['components']['redis'] = {'status': 'ok'}
            else:
                status['components']['redis'] = {'status': 'disabled', 'message': 'using memory cache'}
        except Exception as e:
            status['status'] = 'degraded'
            status['components']['redis'] = {'status': 'error', 'message': str(e)}

        return jsonify(status)

    # 记录启动时间
    import time as _time
    app._start_time = _time.time()

    # --- 全局异常处理器（S5：防止内部信息泄露） ---
    @app.errorhandler(404)
    def not_found(error):
        if _wants_json_response():
            return jsonify({'code': 404, 'message': '请求的资源不存在。', 'data': None}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if _wants_json_response():
            return jsonify({'code': 500, 'message': '服务器内部错误，请稍后重试。', 'data': None}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def rate_limited(error):
        if _wants_json_response():
            return jsonify({'code': 429, 'message': '请求过于频繁，请稍后再试。', 'data': None}), 429
        return render_template('errors/429.html'), 429

    return app
