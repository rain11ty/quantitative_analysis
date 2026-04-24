# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy

# 数据库实例
db = SQLAlchemy()

# Redis 实例（可能为 None，如果连接失败则降级为内存缓存）
redis_client = None


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
