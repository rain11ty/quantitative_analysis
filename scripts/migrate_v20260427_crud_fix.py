# -*- coding: utf-8 -*-
"""
数据库迁移脚本 — CRUD审计修复 (2026-04-27)

变更内容:
1. UserWatchlist: 新增 note, sort_order 列
2. UserAnalysisRecord: summary 255→500, 新增 updated_at 列
3. 新建表: user_backtest_result

使用方式:
  # Docker环境:
  docker exec -it stock-analysis-web python /app/scripts/migrate_v20260427_crud_fix.py
  
  # 本地环境:
  python scripts/migrate_v20260427_crud_fix.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 必须在import app之前设置，否则Flask找不到config
os.environ.setdefault('FLASK_ENV', 'production')


def migrate():
    print("=" * 56)
    print("  CRUD修复迁移脚本 v2026.04.27")
    print("=" * 56)

    from app import create_app
    from app.extensions import db
    import sqlalchemy as sa

    app = create_app()
    with app.app_context():
        # ---- 1. UserWatchlist: 添加 note, sort_order 列 ----
        inspector = sa.inspect(db.engine)
        wl_columns = [c['name'] for c in inspector.get_columns('user_watchlist')]

        if 'note' not in wl_columns:
            print("[1/4] user_watchlist: 添加 note 列...")
            db.session.execute(sa.text(
                "ALTER TABLE user_watchlist ADD COLUMN note VARCHAR(255) COMMENT '备注信息'"
            ))
            db.session.commit()
            print("      ✅ note 列已添加")
        else:
            print("[1/4] user_watchlist.note 列已存在，跳过")

        if 'sort_order' not in wl_columns:
            print("      添加 sort_order 列...")
            db.session.execute(sa.text(
                "ALTER TABLE user_watchlist ADD COLUMN sort_order INT DEFAULT 0 COMMENT '排序权重'"
            ))
            db.session.commit()
            print("      ✅ sort_order 列已添加")
        else:
            print("      user_watchlist.sort_order 列已存在，跳过")

        # ---- 2. UserAnalysisRecord: 扩展summary长度 + updated_at ----
        ar_columns = {c['name']: c for c in inspector.get_columns('user_analysis_record')}

        ar_summary_col = ar_columns.get('summary', {})
        if ar_summary_col.get('type') and hasattr(ar_summary_col['type'], 'length') and ar_summary_col['type'].length < 500:
            print("[2/4] user_analysis_record: 扩展 summary VARCHAR(255→500)...")
            # MySQL: MODIFY COLUMN
            db.session.execute(sa.text(
                "ALTER TABLE user_analysis_record MODIFY COLUMN summary VARCHAR(500) NOT NULL COMMENT 'record summary'"
            ))
            db.session.commit()
            print("      ✅ summary 已扩展为 VARCHAR(500)")
        else:
            print("[2/4] user_analysis_record.summary 长度已满足或无需修改")

        if 'updated_at' not in ar_columns:
            print("      添加 updated_at 列...")
            db.session.execute(sa.text(
                "ALTER TABLE user_analysis_record ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'updated time'"
            ))
            db.session.commit()
            print("      ✅ updated_at 已添加")
        else:
            print("      user_analysis_record.updated_at 列已存在，跳过")

        # ---- 3. 创建 user_backtest_result 表 ----
        existing_tables = inspector.get_table_names()

        if 'user_backtest_result' not in existing_tables:
            print("[3/4] 创建表 user_backtest_result...")
            db.session.execute(sa.text("""
                CREATE TABLE user_backtest_result (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'id',
                    user_id INT NOT NULL COMMENT 'user id',
                    ts_code VARCHAR(20) COMMENT 'stock ts code',
                    stock_name VARCHAR(100) COMMENT 'stock name snapshot',
                    strategy_type VARCHAR(30) NOT NULL COMMENT '策略类型',
                    strategy_label VARCHAR(50) COMMENT '策略显示名称',
                    params JSON COMMENT '策略参数(JSON)',
                    start_date VARCHAR(20) NOT NULL COMMENT '回测起始日期',
                    end_date VARCHAR(20) NOT NULL COMMENT '回测结束日期',
                    initial_capital FLOAT DEFAULT 100000.0 COMMENT '初始资金',
                    performance JSON COMMENT '绩效指标(JSON)',
                    trades JSON COMMENT '最近交易记录(JSON)',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
                    INDEX ix_user_backtest_result_user_id (user_id),
                    INDEX ix_user_backtest_result_ts_code (ts_code),
                    INDEX ix_user_backtest_result_created_at (created_at),
                    CONSTRAINT fk_backtest_user FOREIGN KEY (user_id) REFERENCES user_account (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='用户回测结果记录'
            """))
            db.session.commit()
            print("      ✅ user_backtest_result 表已创建")
        else:
            print("[3/4] user_backtest_result 表已存在，跳过")

        # ---- 4. 验证: 用create_all创建其他可能缺失的表（幂等操作）----
        print("[4/4] 验证/补齐所有ORM表...")
        db.create_all()
        db.session.commit()
        print("      ✅ 所有表结构验证完成")

    print("")
    print("=" * 56)
    print("  ✅ 迁移完成！")
    print("=" * 56)


if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
