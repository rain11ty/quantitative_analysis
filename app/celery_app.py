# -*- coding: utf-8 -*-
"""
Celery 异步任务配置
===================
将耗时数据同步任务从 Flask 主进程拆分到 Celery Worker。
"""

import os

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


def _build_beat_schedule() -> dict:
    schedule = {}

    # 1. 每日收盘后增量更新
    if os.getenv('DAILY_INCREMENTAL_UPDATE_ENABLED', 'true').lower() == 'true':
        hour = int(os.getenv('DAILY_INCREMENTAL_UPDATE_HOUR', '18'))
        minute = int(os.getenv('DAILY_INCREMENTAL_UPDATE_MINUTE', '5'))
        quick = os.getenv('DAILY_INCREMENTAL_UPDATE_QUICK', 'false').lower() == 'true'
        schedule['daily-incremental-update-after-close'] = {
            'task': 'app.tasks.run_daily_incremental_update',
            'schedule': crontab(hour=hour, minute=minute),
            'kwargs': {'quick': quick},
        }

    # 2. 每周六刷新股票基础信息（新股/改名/退市）
    if os.getenv('STOCK_BASIC_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-stock-basic-weekly'] = {
            'task': 'app.tasks.refresh_stock_basic_weekly',
            'schedule': crontab(hour=8, minute=23, day_of_week=6),
        }

    # 3. 每日盘前数据健康检查
    if os.getenv('DATA_HEALTH_CHECK_ENABLED', 'true').lower() == 'true':
        schedule['daily-data-health-check'] = {
            'task': 'app.tasks.run_data_health_check',
            'schedule': crontab(hour=9, minute=7),
        }

    # 4. 交易日收盘后分钟数据归档
    if os.getenv('MINUTE_DATA_SYNC_ENABLED', 'false').lower() == 'true':
        schedule['daily-minute-data-sync'] = {
            'task': 'app.tasks.sync_minute_data_daily',
            'schedule': crontab(hour=15, minute=47),
        }

    # 5. 每日收盘后同步 stock_business 宽表
    if os.getenv('STOCK_BUSINESS_SYNC_ENABLED', 'true').lower() == 'true':
        hour = int(os.getenv('STOCK_BUSINESS_SYNC_HOUR', '18'))
        minute = int(os.getenv('STOCK_BUSINESS_SYNC_MINUTE', '30'))
        schedule['daily-stock-business-sync'] = {
            'task': 'app.tasks.sync_stock_business_wide',
            'schedule': crontab(hour=hour, minute=minute),
            'kwargs': {'days': 30, 'full': False},
        }

    # 6. 新闻快讯定时爬取（每 60 秒）
    if os.getenv('NEWS_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-news-cache'] = {
            'task': 'app.tasks.refresh_news_cache',
            'schedule': timedelta(seconds=60),
        }

    # 7. 涨跌排行定时爬取（每 30 秒）
    if os.getenv('RANKING_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-ranking-cache'] = {
            'task': 'app.tasks.refresh_ranking_cache',
            'schedule': timedelta(seconds=30),
        }

    # 8. 市场概览定时预热（每 30 秒）
    if os.getenv('MARKET_OVERVIEW_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-market-overview-cache'] = {
            'task': 'app.tasks.refresh_market_overview_cache',
            'schedule': timedelta(seconds=30),
        }

    # 9. 热门板块排行定时爬取（每 60 秒）
    if os.getenv('BOARD_RANKING_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-board-ranking-cache'] = {
            'task': 'app.tasks.refresh_board_ranking_cache',
            'schedule': timedelta(seconds=60),
        }

    # 10. 北向资金净流入定时爬取（每 60 秒）
    if os.getenv('NORTHBOUND_FUND_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-northbound-fund-cache'] = {
            'task': 'app.tasks.refresh_northbound_fund_cache',
            'schedule': timedelta(seconds=60),
        }

    # 11. 板块资金流向排名定时爬取（每 120 秒）
    if os.getenv('SECTOR_FUND_FLOW_CACHE_REFRESH_ENABLED', 'true').lower() == 'true':
        schedule['refresh-sector-fund-flow-cache'] = {
            'task': 'app.tasks.refresh_sector_fund_flow_cache',
            'schedule': timedelta(seconds=120),
        }

    return schedule


def make_celery(app=None):
    """创建 Celery 实例，可选与 Flask app 绑定。"""
    broker_url = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/1'))
    result_backend = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/2'))

    celery = Celery(
        'stock_analysis',
        broker=broker_url,
        backend=result_backend,
        include=['app.tasks'],
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
        beat_schedule=_build_beat_schedule(),
    )

    if app:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


celery_app = make_celery()
