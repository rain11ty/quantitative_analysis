# -*- coding: utf-8 -*-
"""
Celery 异步任务配置
===================
将 CPU 密集型或耗时数据同步任务从 Flask 主进程拆分到 Celery Worker。

使用方式：
  # 启动 Celery Worker
  celery -A app.celery_app worker --loglevel=info --concurrency=2

  # 启动 Celery Beat（定时调度，可选）
  celery -A app.celery_app beat --loglevel=info

  # 启动 Flower 监控（可选）
  celery -A app.celery_app flower

在代码中调用：
  from app.tasks import sync_daily_data
  result = sync_daily_data.delay()           # 异步执行
  result = sync_daily_data.apply_async(countdown=60)  # 60秒后执行
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


def make_celery(app=None):
    """创建 Celery 实例，可选与 Flask app 绑定"""
    broker_url = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/1'))
    result_backend = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/2'))

    celery = Celery(
        'stock_analysis',
        broker=broker_url,
        backend=result_backend,
    )

    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,         # 单任务最长1小时
        task_soft_time_limit=3000,    # 软限制50分钟
        worker_max_tasks_per_child=100,
        worker_prefetch_multiplier=1,
        # 定时任务（Celery Beat）
        beat_schedule={
            'sync-daily-data': {
                'task': 'app.tasks.sync_daily_data',
                'schedule': 3600 * 18,   # 每18小时检查一次（收盘后执行）
                'args': (),
            },
        },
    )

    if app:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


# 默认 Celery 实例（不绑定 Flask，任务函数内部自行创建 app context）
celery_app = make_celery()
