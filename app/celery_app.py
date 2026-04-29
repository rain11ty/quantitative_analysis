# -*- coding: utf-8 -*-
"""
Celery 异步任务配置
===================
将耗时数据同步任务从 Flask 主进程拆分到 Celery Worker。
"""

import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


def _daily_incremental_update_schedule() -> dict:
    enabled = os.getenv('DAILY_INCREMENTAL_UPDATE_ENABLED', 'true').lower() == 'true'
    if not enabled:
        return {}

    hour = int(os.getenv('DAILY_INCREMENTAL_UPDATE_HOUR', '18'))
    minute = int(os.getenv('DAILY_INCREMENTAL_UPDATE_MINUTE', '5'))
    quick = os.getenv('DAILY_INCREMENTAL_UPDATE_QUICK', 'false').lower() == 'true'

    return {
        'daily-incremental-update-after-close': {
            'task': 'app.tasks.run_daily_incremental_update',
            'schedule': crontab(hour=hour, minute=minute),
            'kwargs': {'quick': quick},
        },
    }


def make_celery(app=None):
    """创建 Celery 实例，可选与 Flask app 绑定。"""
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
        enable_utc=False,
        task_track_started=True,
        task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', '14400')),
        task_soft_time_limit=int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '12600')),
        worker_max_tasks_per_child=100,
        worker_prefetch_multiplier=1,
        beat_schedule=_daily_incremental_update_schedule(),
    )

    if app:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


celery_app = make_celery()
