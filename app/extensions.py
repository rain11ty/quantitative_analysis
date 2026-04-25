# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy

# 数据库实例
db = SQLAlchemy()

# Redis 实例（可能为 None，如果连接失败则降级为内存缓存）
redis_client = None

# 邮件实例（可能为 None，如果未配置或导入失败）
mail = None


def init_mail(app):
    """初始化 Flask-Mailman 邮件服务"""
    global mail

    username = app.config.get('MAIL_USERNAME', '')
    password = app.config.get('MAIL_PASSWORD', '')

    if not username or not password:
        app.logger.info('[Mail] MAIL_USERNAME 或 MAIL_PASSWORD 未配置，邮件功能禁用')
        mail = None
        return

    try:
        from django.conf import settings as django_settings
        from django.core.mail import backend as django_mail_backend

        # 配置 Django 邮件后端（flask-mailman 底层使用 Django 的邮件系统）
        django_settings.EMAIL_HOST = app.config.get('MAIL_SERVER', 'localhost')
        django_settings.EMAIL_PORT = int(app.config.get('MAIL_PORT', '25'))
        django_settings.EMAIL_USE_SSL = app.config.get('MAIL_USE_SSL', False)
        django_settings.EMAIL_USE_TLS = app.config.get('MAIL_USE_TLS', False)
        django_settings.EMAIL_HOST_USER = username
        django_settings.EMAIL_HOST_PASSWORD = password
        DEFAULT_SENDER = app.config.get('MAIL_DEFAULT_SENDER', ('noreply@stock-analysis.local', 'StockAnalysis'))
        django_settings.DEFAULT_FROM_EMAIL = DEFAULT_SENDER[0] if isinstance(DEFAULT_SENDER, tuple) else DEFAULT_SENDER

        mail = True  # 标记为已配置
        sender_name = DEFAULT_SENDER[1] if isinstance(DEFAULT_SENDER, tuple) else 'Stock'
        app.logger.info(f'[Mail] 邮件服务初始化成功: {username} (发件人: {sender_name})')
    except ImportError:
        app.logger.warning('[Mail] flask-mailman/Django 未安装，邮件功能禁用')
        mail = None
    except Exception as exc:
        app.logger.warning(f'[Mail] 邮件服务初始化失败: {exc}')
        mail = None


def init_redis(app):
    """初始化 Redis 连接，失败则降级为 None（使用内存缓存）"""
    global redis_client

    if not app.config.get('REDIS_ENABLED', True):
        app.logger.info('[Redis] REDIS_ENABLED=false，使用内存缓存')
        return

    try:
        import redis as _redis

        host = app.config.get('REDIS_HOST', 'localhost')
        port = app.config.get('REDIS_PORT', 6379)
        db_num = app.config.get('REDIS_DB', 0)
        password = app.config.get('REDIS_PASSWORD')

        redis_client = _redis.Redis(
            host=host,
            port=port,
            db=db_num,
            password=password,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        redis_client.ping()
        app.logger.info(f'[Redis] 连接成功: {host}:{port}/{db_num}')
    except Exception as exc:
        redis_client = None
        app.logger.warning(f'[Redis] 连接失败，降级为内存缓存: {exc}')
