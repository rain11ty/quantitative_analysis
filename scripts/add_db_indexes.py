# -*- coding: utf-8 -*-
"""
数据库索引优化脚本
==================
为 stock_daily_history / stock_factor / stock_business 等大表添加辅助索引，
提升按日期全市场查询和筛选的性能。

使用方式：
  python scripts/add_db_indexes.py

注意：
  - 在数据量大时创建索引可能耗时较长（10年数据约需 1~5 分钟/索引）
  - 使用 IF NOT EXISTS 避免重复创建
  - 建议在低峰期执行
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from dotenv import load_dotenv

load_dotenv(override=True, encoding='utf-8')


def get_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', 'root'),
        database=os.getenv('DB_NAME', 'stock_cursor'),
        charset=os.getenv('DB_CHARSET', 'utf8mb4'),
    )


# 索引定义：(表名, 索引名, 索引列, 说明)
INDEXES = [
    # --- stock_daily_history ---
    ('stock_daily_history', 'idx_sdh_trade_date', 'trade_date',
     '按日期查全市场行情（如：某天所有股票）'),

    # --- stock_factor ---
    ('stock_factor', 'idx_sf_trade_date', 'trade_date',
     '按日期查全市场因子'),
    ('stock_factor', 'idx_sf_trade_date_ts_code', 'trade_date, ts_code',
     '按日期+代码联合查因子（覆盖索引）'),

    # --- stock_business ---
    ('stock_business', 'idx_sb_trade_date', 'trade_date',
     '按日期查全市场筛选大宽表'),
    ('stock_business', 'idx_sb_trade_date_pe', 'trade_date, pe',
     '按日期+PE筛选'),
    ('stock_business', 'idx_sb_trade_date_pb', 'trade_date, pb',
     '按日期+PB筛选'),
    ('stock_business', 'idx_sb_trade_date_total_mv', 'trade_date, total_mv',
     '按日期+市值筛选'),

    # --- stock_daily_basic ---
    ('stock_daily_basic', 'idx_sdb_trade_date', 'trade_date',
     '按日期查全市场每日指标'),
    ('stock_daily_basic', 'idx_sdb_trade_date_pe', 'trade_date, pe',
     '按日期+PE筛选'),

    # --- stock_moneyflow ---
    ('stock_moneyflow', 'idx_sm_trade_date', 'trade_date',
     '按日期查全市场资金流向'),

    # --- stock_cyq_perf ---
    ('stock_cyq_perf', 'idx_scp_trade_date', 'trade_date',
     '按日期查全市场筹码分布'),
]


def check_index_exists(cursor, table, index_name):
    """检查索引是否已存在"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
    """, (table, index_name))
    return cursor.fetchone()[0] > 0


def get_table_rows(cursor, table):
    """获取表行数（估算）"""
    try:
        cursor.execute(f"""
            SELECT TABLE_ROWS FROM information_schema.TABLES
            WHERE table_schema = DATABASE() AND table_name = %s
        """, (table,))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def main():
    print("=" * 60)
    print("  数据库索引优化工具")
    print("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        created = 0
        skipped = 0
        errors = []

        for table, idx_name, columns, description in INDEXES:
            print(f"\n  [{table}] {idx_name} ({columns})")
            print(f"    用途: {description}")

            # 检查表是否存在
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE table_schema = DATABASE() AND table_name = %s
            """, (table,))
            if cursor.fetchone()[0] == 0:
                print(f"    跳过: 表 {table} 不存在")
                skipped += 1
                continue

            # 检查索引是否已存在
            if check_index_exists(cursor, table, idx_name):
                print(f"    跳过: 索引 {idx_name} 已存在")
                skipped += 1
                continue

            # 获取行数
            rows = get_table_rows(cursor, table)
            print(f"    表行数(估算): {rows:,}")

            # 创建索引
            sql = f"ALTER TABLE `{table}` ADD INDEX `{idx_name}` ({columns})"
            print(f"    执行: {sql}")

            start = time.time()
            try:
                cursor.execute(sql)
                conn.commit()
                elapsed = time.time() - start
                print(f"    完成! 耗时 {elapsed:.1f}s")
                created += 1
            except Exception as e:
                conn.rollback()
                print(f"    错误: {e}")
                errors.append(f"{table}.{idx_name}: {e}")

        print(f"\n{'=' * 60}")
        print("  索引优化完成")
        print(f"{'=' * 60}")
        print(f"  新建索引: {created}")
        print(f"  已存在跳过: {skipped}")
        print(f"  失败: {len(errors)}")
        if errors:
            print("\n  错误详情:")
            for e in errors:
                print(f"    {e}")
        print()

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
