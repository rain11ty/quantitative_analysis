#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tushare connectivity check."""

from app.utils.db_utils import DatabaseUtils
from app.services.minute_data_sync_service import MinuteDataSyncService


def _mask_token(token: str) -> str:
    if not token:
        return ''
    return f"{token[:10]}...{token[-10:]}" if len(token) >= 20 else token


def test_tushare_connection():
    """Verify Tushare basic connectivity."""
    print('[INFO] Checking Tushare configuration...')

    token, http_url = DatabaseUtils.get_tushare_config()
    print(f'Token: {_mask_token(token)}')
    print(f'HTTP URL: {http_url}')

    if not token:
        print('[ERROR] TUSHARE_TOKEN is not set')
        return False, None

    try:
        pro = DatabaseUtils.init_tushare_api(token=token, http_url=http_url)
        print('[OK] Token and custom HTTP URL applied')

        print('\n[TEST] Requesting basic stock list...')
        basic_df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name', limit=5)
        if basic_df is None or basic_df.empty:
            print('[ERROR] Empty stock_basic response received')
            return False, None

        print(f'[OK] stock_basic succeeded, fetched {len(basic_df)} rows')
        for _, row in basic_df.iterrows():
            print(f"  {row['ts_code']} - {row['name']}")

        print('\n[TEST] Requesting daily data...')
        daily_df = pro.daily(ts_code='000001.SZ', start_date='20260101', end_date='20260110')
        if daily_df is None:
            print('[ERROR] daily returned None')
            return False, pro

        print(f'[OK] daily succeeded, fetched {len(daily_df)} rows')
        return True, pro
    except Exception as exc:
        print(f'[ERROR] Tushare connection failed: {exc}')
        print('\n[TROUBLESHOOT] Suggestions:')
        print('1. Check whether the token is valid')
        print('2. Check network accessibility')
        print('3. Check whether the account has enough permissions')
        print('4. Check whether the custom HTTP URL is reachable')
        return False, None


def test_minute_data():
    """Verify minute data fetch path."""
    print('\n[TEST] Checking minute data fetch...')

    try:
        service = MinuteDataSyncService()
        df = service._fetch_minute_data(
            ts_code='000001.SZ',
            start_date='2024-01-01',
            end_date='2024-01-10',
            period_type='1min',
        )

        if df is None or df.empty:
            print('[WARN] Minute data returned empty result')
            return False

        print(f'[OK] Minute data fetch succeeded, fetched {len(df)} rows')
        print(f"Columns: {', '.join(df.columns.tolist())}")
        return True
    except Exception as exc:
        print(f'[ERROR] Minute data test failed: {exc}')
        return False


if __name__ == '__main__':
    print('=' * 50)
    print('Tushare connection test tool')
    print('=' * 50)

    connection_ok, _ = test_tushare_connection()
    minute_ok = False

    if connection_ok:
        minute_ok = test_minute_data()

    print('\n' + '=' * 50)
    if connection_ok and minute_ok:
        print('[SUCCESS] Basic and minute tests passed')
    elif connection_ok:
        print('[PARTIAL] Basic APIs passed, but minute data is unavailable or not permitted')
    else:
        print('[FAILED] Tests failed, please review configuration')
    print('=' * 50)
