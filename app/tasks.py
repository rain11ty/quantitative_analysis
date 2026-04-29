# -*- coding: utf-8 -*-
"""
Celery 异步任务定义
===================
所有耗时任务在此定义，由 Celery Worker 异步执行。
"""

from __future__ import annotations

from app.celery_app import celery_app
from loguru import logger


def _get_app():
    """获取 Flask app 上下文。"""
    from app import create_app

    return create_app()


def _run_daily_update_job(*, quick: bool = False):
    """执行每日增量更新脚本并返回结果。"""
    from scripts.daily_auto_update import DailyAutoUpdater

    updater = DailyAutoUpdater()
    try:
        return updater.run_all(quick=quick)
    finally:
        updater.close()


def _execute_daily_update_task(task, *, quick: bool = False):
    app = _get_app()
    with app.app_context():
        mode_label = 'quick' if quick else 'full'
        logger.info(f'[Celery] 开始执行每日增量更新任务: mode={mode_label}')
        results = _run_daily_update_job(quick=quick)
        logger.info(f'[Celery] 每日增量更新完成: mode={mode_label}, results={results}')
        return {
            'status': 'success',
            'mode': mode_label,
            'results': results,
        }


@celery_app.task(name='app.tasks.run_daily_incremental_update', bind=True, max_retries=2)
def run_daily_incremental_update(self, quick: bool = False):
    """执行收盘后的每日增量更新。"""
    try:
        return _execute_daily_update_task(self, quick=quick)
    except Exception as exc:
        logger.error(f'[Celery] 每日增量更新失败: {exc}')
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name='app.tasks.sync_daily_data', bind=True, max_retries=2)
def sync_daily_data(self, quick: bool = False):
    """兼容旧任务名，内部转到每日增量更新脚本。"""
    try:
        return _execute_daily_update_task(self, quick=quick)
    except Exception as exc:
        logger.error(f'[Celery] 日线同步任务失败: {exc}')
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name='app.tasks.backfill_factors_task', bind=True, max_retries=1)
def backfill_factors_task(self, start_date=None, force=False):
    """批量补算技术指标。"""
    try:
        app = _get_app()
        with app.app_context():
            logger.info(f'[Celery] 开始补算技术指标: start_date={start_date}, force={force}')
            from scripts.backfill_factors_v2 import get_db_connection, get_stock_list, process_stock

            conn = get_db_connection()
            try:
                stock_list = get_stock_list(conn)
                total = 0
                for ts_code in stock_list:
                    inserted, skipped, err = process_stock(
                        conn,
                        ts_code,
                        start_date=start_date,
                        end_date=None,
                        force=force,
                        dry_run=False,
                        batch_size=3000,
                    )
                    if err:
                        logger.warning(f'[Celery] {ts_code}: {err}')
                    total += inserted

                logger.info(f'[Celery] 技术指标补算完成，共写入 {total} 条')
                return {'status': 'success', 'inserted': total}
            finally:
                conn.close()
    except Exception as exc:
        logger.error(f'[Celery] 技术指标补算失败: {exc}')
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name='app.tasks.health_check')
def health_check():
    """Celery Worker 健康检查。"""
    return {'status': 'ok', 'worker': 'celery'}
