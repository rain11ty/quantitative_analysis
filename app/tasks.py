# -*- coding: utf-8 -*-
"""
Celery 异步任务定义
===================
所有耗时任务在此定义，由 Celery Worker 异步执行。

定时任务一览：
  - run_daily_incremental_update  每日 18:05  收盘后增量更新
  - refresh_stock_basic_weekly    每周六 08:23 刷新股票基础信息
  - run_data_health_check         每日 09:07  数据完整性检查
  - sync_minute_data_daily        每日 15:47  分钟数据归档
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from app.celery_app import celery_app
from loguru import logger


def _get_app():
    """获取 Flask app 上下文。"""
    from app import create_app

    return create_app()


def _get_admin_email() -> Optional[str]:
    """获取管理员告警邮箱。"""
    return (os.getenv('ADMIN_EMAIL', '') or '').strip() or None


def _send_failure_alert(task_name: str, error_msg: str):
    """发送同步失败告警邮件（仅在最终失败时调用）。"""
    admin_email = _get_admin_email()
    if not admin_email:
        logger.warning(f'[Alert] ADMIN_EMAIL 未配置，跳过告警: {task_name}')
        return

    try:
        from app.services.email_service import EmailService

        app = _get_app()
        with app.app_context():
            EmailService.send_alert(
                to=admin_email,
                subject=f'[数据同步告警] {task_name} 执行失败',
                body=(
                    f'任务: {task_name}\n'
                    f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
                    f'错误: {error_msg}\n\n'
                    f'请检查 Tushare API、数据库连接和 Redis 状态。'
                ),
            )
            logger.info(f'[Alert] 告警邮件已发送至 {admin_email}')
    except Exception as exc:
        logger.error(f'[Alert] 发送告警邮件失败: {exc}')


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


# ================================================================
#  已有任务
# ================================================================

@celery_app.task(name='app.tasks.run_daily_incremental_update', bind=True, max_retries=2)
def run_daily_incremental_update(self, quick: bool = False):
    """每日收盘后的增量数据更新（日线/复权/指标/资金流向/北向资金/技术指标）。"""
    try:
        return _execute_daily_update_task(self, quick=quick)
    except Exception as exc:
        logger.error(f'[Celery] 每日增量更新失败: {exc}')
        if self.request.retries >= self.max_retries:
            _send_failure_alert('每日增量更新', str(exc))
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


# ================================================================
#  新增任务
# ================================================================

@celery_app.task(name='app.tasks.refresh_stock_basic_weekly', bind=True, max_retries=1)
def refresh_stock_basic_weekly(self):
    """每周刷新股票基础信息（新股上市/改名/退市）。"""
    try:
        import tushare as ts

        token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
        if not token:
            raise ValueError('TUSHARE_TOKEN 未设置')

        ts.set_token(token)
        pro = ts.pro_api()
        proxy_url = (os.getenv('TUSHARE_PROXY_URL', '') or '').strip()
        if proxy_url:
            pro._DataApi__http_url = proxy_url

        from app.utils.db_utils import get_db_connection
        conn, cursor = get_db_connection()

        try:
            logger.info('[Celery] 开始刷新股票基础信息...')
            df = pro.stock_basic(exchange='', list_status='L',
                                 fields='ts_code,symbol,name,area,industry,market,list_date')
            if df is None or df.empty:
                logger.warning('[Celery] stock_basic 返回空数据')
                return {'status': 'warning', 'message': 'stock_basic 返回空数据'}

            import numpy as np
            df = df.replace({np.nan: None}).where(df.notnull(), None)

            columns = ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 'list_date']
            cursor.execute('DELETE FROM stock_basic')

            cols_str = ', '.join(f'`{c}`' for c in columns)
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f'INSERT INTO `stock_basic` ({cols_str}) VALUES ({placeholders})'

            data = []
            for _, row in df.iterrows():
                ld = row.get('list_date')
                if ld and str(ld) not in ('', 'None', 'nan'):
                    try:
                        ld = datetime.strptime(str(ld)[:8], '%Y%m%d').date()
                    except ValueError:
                        ld = None
                else:
                    ld = None
                data.append((
                    row.get('ts_code'), row.get('symbol'), row.get('name'),
                    row.get('area'), row.get('industry'), row.get('market'), ld,
                ))

            for i in range(0, len(data), 5000):
                cursor.executemany(sql, data[i:i + 5000])
                conn.commit()

            logger.info(f'[Celery] 股票基础信息刷新完成: {len(data)} 条')
            return {'status': 'success', 'count': len(data)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as exc:
        logger.error(f'[Celery] 股票基础信息刷新失败: {exc}')
        if self.request.retries >= self.max_retries:
            _send_failure_alert('股票基础信息周刷新', str(exc))
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(name='app.tasks.run_data_health_check', bind=True)
def run_data_health_check(self):
    """每日盘前数据完整性健康检查，异常时邮件告警，结果写入 system_log。"""
    try:
        from app.utils.db_utils import get_db_connection

        conn, cursor = get_db_connection()

        try:
            issues = []

            # 检查交易日历是否覆盖到昨天
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            cursor.execute(
                'SELECT MAX(cal_date) FROM stock_trade_calendar'
            )
            max_cal = cursor.fetchone()[0]
            if max_cal:
                max_cal_str = max_cal.strftime('%Y%m%d') if hasattr(max_cal, 'strftime') else str(max_cal).replace('-', '')
                if max_cal_str < yesterday:
                    issues.append(f'交易日历滞后: 最新={max_cal_str}, 期望>={yesterday}')

            # 检查最近交易日日线数据量
            cursor.execute("""
                SELECT trade_date, COUNT(*) FROM stock_daily_history
                WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL 10 DAY)
                GROUP BY trade_date ORDER BY trade_date DESC LIMIT 3
            """)
            recent_counts = cursor.fetchall()
            if len(recent_counts) >= 2:
                latest_cnt = recent_counts[0][1]
                prev_cnt = recent_counts[1][1]
                if prev_cnt > 0 and (latest_cnt < prev_cnt * 0.7 or latest_cnt > prev_cnt * 1.3):
                    issues.append(
                        f'日线数据量异常: {recent_counts[0][0]}={latest_cnt}条, '
                        f'{recent_counts[1][0]}={prev_cnt}条'
                    )

            # 检查技术指标填充率
            cursor.execute('SELECT COUNT(*) FROM stock_factor')
            factor_total = cursor.fetchone()[0]
            if factor_total > 0:
                cursor.execute(
                    'SELECT COUNT(*) FROM stock_factor WHERE macd_dif IS NOT NULL'
                )
                filled = cursor.fetchone()[0]
                fill_rate = filled / factor_total * 100
                if fill_rate < 90:
                    issues.append(f'技术指标(MACD)填充率偏低: {fill_rate:.1f}%')

            # 检查 stock_basic 数量
            cursor.execute('SELECT COUNT(*) FROM stock_basic')
            stock_count = cursor.fetchone()[0]
            if stock_count < 4000:
                issues.append(f'股票基础信息数量偏少: {stock_count} 只')

            status = 'ok' if not issues else 'degraded'
            issue_text = '; '.join(issues) if issues else '无异常'
            logger.info(f'[Celery] 数据健康检查完成: status={status}, issues={issues}')

            # 写入 system_log 表
            try:
                cursor.execute(
                    'INSERT INTO system_log (action_type, message, status, created_at) VALUES (%s, %s, %s, NOW())',
                    ('data_health_check', f'[{status}] {issue_text}', status),
                )
                conn.commit()
            except Exception as log_exc:
                logger.warning(f'[Celery] 健康检查写入 system_log 失败: {log_exc}')

            if issues:
                _send_failure_alert('数据健康检查', '\n'.join(issues))

            return {'status': status, 'issues': issues}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as exc:
        logger.error(f'[Celery] 数据健康检查执行异常: {exc}')
        return {'status': 'error', 'message': str(exc)}


@celery_app.task(name='app.tasks.sync_minute_data_daily', bind=True, max_retries=1)
def sync_minute_data_daily(self):
    """收盘后同步当日分钟K线数据（归档到 stock_minute_data 表）。"""
    try:
        from app.services.minute_data_sync_service import MinuteDataSyncService

        logger.info('[Celery] 开始分钟数据归档...')

        with MinuteDataSyncService() as svc:
            today = datetime.now().strftime('%Y-%m-%d')
            stock_list = svc.get_stock_list_from_db()[:500]
            result = svc.sync_multiple_stocks_data(
                stock_list=stock_list,
                start_date=today,
                end_date=today,
            )
            logger.info(f'[Celery] 分钟数据归档完成: {result}')
            return {'status': 'success', 'result': result}

    except Exception as exc:
        logger.error(f'[Celery] 分钟数据归档失败: {exc}')
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(name='app.tasks.sync_stock_business_wide', bind=True, max_retries=1)
def sync_stock_business_wide(self, days=30, full=False):
    """同步 stock_business 宽表：将源表数据合并到筛选宽表。"""
    try:
        app = _get_app()
        with app.app_context():
            import time as _time

            from scripts.sync_stock_business import (
                _get_db_connection,
                get_target_dates,
                sync_one_date,
            )

            logger.info(f'[Celery] 开始同步 stock_business 宽表: days={days}, full={full}')

            conn = _get_db_connection()
            try:
                dates = get_target_dates(conn, days=days, full=full)
                if not dates:
                    logger.warning('[Celery] 没有找到需要同步的交易日数据')
                    return {'status': 'success', 'days': days, 'full': full, 'total_rows': 0}

                mode = '全量' if full else f'最近{days}天'
                logger.info('[Celery] 模式: %s，共 %d 个交易日待同步', mode, len(dates))

                total_rows = 0
                start_time = _time.time()

                for i, trade_date in enumerate(dates, 1):
                    try:
                        count = sync_one_date(conn, trade_date)
                        total_rows += count
                        elapsed = _time.time() - start_time
                        avg = elapsed / i
                        eta = avg * (len(dates) - i)
                        logger.info(
                            '[Celery] [%d/%d] %s: %d 条 | 累计 %d 条 | 耗时 %.0fs | 预计剩余 %.0fs',
                            i, len(dates), trade_date, count, total_rows, elapsed, eta,
                        )
                    except Exception as e:
                        logger.error('[Celery] [%d/%d] %s: 失败 - %s', i, len(dates), trade_date, e)
                        conn.ping(reconnect=True)

                elapsed = _time.time() - start_time
                logger.info(
                    '[Celery] stock_business 宽表同步完成: %d 个交易日, %d 条数据, 耗时 %.1fs',
                    len(dates), total_rows, elapsed,
                )
            finally:
                conn.close()

            # 写入 system_log
            db_conn = None
            cursor = None
            try:
                from app.utils.db_utils import get_db_connection
                db_conn, cursor = get_db_connection()
                cursor.execute(
                    'INSERT INTO system_log (action_type, message, status, created_at) VALUES (%s, %s, %s, NOW())',
                    ('sync_stock_business', f'宽表同步完成: days={days}, full={full}', 'success'),
                )
                db_conn.commit()
            except Exception as log_exc:
                logger.warning(f'[Celery] 写入 system_log 失败: {log_exc}')
            finally:
                if cursor:
                    cursor.close()
                if db_conn:
                    db_conn.close()

            return {'status': 'success', 'days': days, 'full': full, 'total_rows': total_rows}

    except Exception as exc:
        logger.error(f'[Celery] stock_business 宽表同步失败: {exc}')
        if self.request.retries >= self.max_retries:
            _send_failure_alert('stock_business 宽表同步', str(exc))
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(name='app.tasks.refresh_news_cache')
def refresh_news_cache():
    """每 60 秒爬取 4 个新闻源，聚合后写入 Redis（news_aggregate:all，TTL 120s）。"""
    try:
        from app.services.news_service import NewsService
        from app.utils.cache_utils import get_cache

        cache = get_cache()

        all_items: list = []
        source_errors: list = []
        sources = [
            ('cjzc', NewsService.get_cjzc),
            ('global_em', NewsService.get_global_em),
            ('cls', NewsService.get_global_cls),
            ('ths', NewsService.get_global_ths),
        ]

        for name, func in sources:
            try:
                data = func()
                if data.get('items'):
                    all_items.extend(data['items'])
                elif data.get('error'):
                    source_errors.append(f"{data.get('source', name)}: {data['error']}")
            except Exception as exc:
                source_errors.append(f'{name}: {exc}')
                logger.warning(f'[Celery] 新闻源 {name} 爬取失败: {exc}')

        all_items.sort(key=lambda x: x.get('time', ''), reverse=True)

        result = {
            'items': all_items,
            'count': len(all_items),
            'source': '全部来源',
            'errors': source_errors if source_errors else None,
        }
        cache.set('news_aggregate:all', result, ttl=120)
        logger.info(f'[Celery] 新闻缓存已刷新: {len(all_items)} 条')
    except Exception as exc:
        logger.error(f'[Celery] 新闻缓存刷新失败: {exc}')


@celery_app.task(name='app.tasks.refresh_ranking_cache')
def refresh_ranking_cache():
    """每 30 秒爬取涨跌排行，写入 Redis（realtime_ranking_pct_change / realtime_ranking_turnover_rate / realtime_ranking_amount，TTL 90s）。"""
    try:
        from app.services.realtime_monitor_service import RealtimeMonitorService
        from app.utils.cache_utils import get_cache

        cache = get_cache()

        for sort_by, cache_keys in [
            ('pct_change', ['realtime_ranking_pct_change']),
            ('turnover_rate', ['realtime_ranking_turnover_rate']),
            ('amount', ['realtime_ranking_amount', 'realtime_ranking_volume']),
        ]:
            try:
                result = RealtimeMonitorService.get_realtime_ranking(sort_by=sort_by)
                for key in cache_keys:
                    cache.set(key, result, ttl=90)
            except Exception as exc:
                logger.warning(f'[Celery] 排行缓存刷新失败 (sort_by={sort_by}): {exc}')

        logger.info('[Celery] 涨跌排行缓存已刷新')
    except Exception as exc:
        logger.error(f'[Celery] 涨跌排行缓存刷新失败: {exc}')


@celery_app.task(name='app.tasks.refresh_market_overview_cache')
def refresh_market_overview_cache():
    """每 30 秒预热市场概览和指数 K 线，写入 Redis（TTL 90s）。"""
    try:
        from app.services.market_overview_service import MarketOverviewService
        from app.utils.cache_utils import get_cache

        cache = get_cache()

        try:
            overview = MarketOverviewService.get_market_overview()
            cache.set('market_overview', overview, ttl=90)
        except Exception as exc:
            logger.warning(f'[Celery] 市场概览缓存刷新失败: {exc}')

        # 预热所有指数的所有周期
        all_indices = ('000001.SH', '399001.SZ', '399006.SZ', '000016.SH', '000300.SH', '000905.SH', '000688.SH')
        all_periods = ('1M', '3M', '1Y', '3Y')
        for idx in all_indices:
            for period in all_periods:
                try:
                    kline = MarketOverviewService.get_index_kline(idx, period)
                    cache.set(f'index_kline_{idx}_{period}', kline, ttl=90)
                except Exception as exc:
                    logger.warning(f'[Celery] K线缓存刷新失败 {idx} {period}: {exc}')

        logger.info('[Celery] 市场概览缓存已刷新')
    except Exception as exc:
        logger.error(f'[Celery] 市场概览缓存刷新失败: {exc}')


@celery_app.task(name='app.tasks.health_check')
def health_check():
    """Celery Worker 健康检查。"""
    return {'status': 'ok', 'worker': 'celery'}
