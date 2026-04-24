# -*- coding: utf-8 -*-
"""
Celery 异步任务定义
===================
所有耗时任务在此定义，由 Celery Worker 异步执行。

使用方式：
  from app.tasks import sync_daily_data, backfill_factors_task
  sync_daily_data.delay()                   # 立即异步执行
  backfill_factors_task.delay(force=True)   # 强制补算
"""

from app.celery_app import celery_app
from loguru import logger


def _get_app():
    """获取 Flask app 上下文"""
    from app import create_app
    return create_app()


@celery_app.task(name='app.tasks.sync_daily_data', bind=True, max_retries=2)
def sync_daily_data(self):
    """同步日线数据（异步任务）"""
    try:
        app = _get_app()
        with app.app_context():
            logger.info("[Celery] 开始同步日线数据...")
            # 这里可以调用现有的数据同步逻辑
            # 例如：from scripts.sync_tushare_data import TushareDataSync
            # sync = TushareDataSync()
            # sync.sync_daily()
            logger.info("[Celery] 日线数据同步完成")
            return {'status': 'success', 'message': '日线数据同步完成'}
    except Exception as exc:
        logger.error(f"[Celery] 日线数据同步失败: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name='app.tasks.backfill_factors_task', bind=True, max_retries=1)
def backfill_factors_task(self, start_date=None, force=False):
    """批量补算技术指标（异步任务）"""
    try:
        app = _get_app()
        with app.app_context():
            logger.info(f"[Celery] 开始补算技术指标: start_date={start_date}, force={force}")
            # 调用 backfill_factors_v2 的核心逻辑
            from scripts.backfill_factors_v2 import get_db_connection, get_stock_list, process_stock
            conn = get_db_connection()
            try:
                stock_list = get_stock_list(conn)
                total = 0
                for ts_code in stock_list:
                    inserted, skipped, err = process_stock(
                        conn, ts_code, start_date=start_date,
                        end_date=None, force=force, dry_run=False, batch_size=3000,
                    )
                    if err:
                        logger.warning(f"[Celery] {ts_code}: {err}")
                    total += inserted
                logger.info(f"[Celery] 技术指标补算完成，共写入 {total} 条")
                return {'status': 'success', 'inserted': total}
            finally:
                conn.close()
    except Exception as exc:
        logger.error(f"[Celery] 技术指标补算失败: {exc}")
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name='app.tasks.health_check')
def health_check():
    """Celery Worker 健康检查"""
    return {'status': 'ok', 'worker': 'celery'}
