# -*- coding: utf-8 -*-
"""
Gunicorn 生产环境配置文件
基于 LLM 与 Flask 的股票量化分析系统

使用方式:
    gunicorn -c gunicorn.conf.py run:app

或指定环境变量:
    FLASK_ENV=production gunicorn -c gunicorn.conf.py run:app
"""

import multiprocessing
import os

# ============================================================
# 服务器绑定配置
# ============================================================
bind = os.getenv('GUNICORN_BIND', '0.0.0.0:5001')

# ============================================================
# Worker 进程配置
# ============================================================
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'sync')  # 生产环境推荐 gevent
workers = int(os.getenv('GUNICORN_WORKERS', min(multiprocessing.cpu_count() * 2 + 1, 8)))
worker_connections = int(os.getenv('GUNICORN_CONNECTIONS', 1000))
threads = int(os.getenv('GUNICORN_THREADS', 1))

# ============================================================
# 超时配置
# ============================================================
timeout = int(os.getenv('GUNICORN_TIMEOUT', 180))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', 5))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', 30))
worker_silent_timeout = int(os.getenv('GUNICORN_SILENT_TIMEOUT', 60))

# ============================================================
# 日志配置
# ============================================================
log_dir = os.getenv('LOG_DIR', 'logs')
os.makedirs(log_dir, exist_ok=True)

accesslog = os.path.join(log_dir, 'gunicorn_access.log')
errorlog = os.path.join(log_dir, 'gunicorn_error.log')
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ============================================================
# 进程管理配置
# ============================================================
pidfile = os.path.join(log_dir, 'gunicorn.pid')
preload_app = True
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', 5000))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', 500))

# ============================================================
# 安全配置
# ============================================================
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ============================================================
# 服务器机制
# ============================================================
daemon = os.getenv('GUNICORN_DAEMON', 'False').lower() == 'true'
tmp_upload_dir = None

# SSL/TLS 配置（可选）
# certfile = "/path/to/cert.pem"
# keyfile = "/path/to/key.pem"
