from app.extensions import db
from app.models import StockBasic, UserAnalysisRecord, UserChatHistory, UserWatchlist


class UserActivityService:
    @staticmethod
    def normalize_ts_code(ts_code):
        return (ts_code or '').strip().upper()

    @staticmethod
    def resolve_stock_snapshot(ts_code, stock_name=None):
        code = UserActivityService.normalize_ts_code(ts_code)
        if not code:
            return '', (stock_name or '').strip(), ''

        stock = StockBasic.query.filter_by(ts_code=code).first()
        resolved_name = (stock_name or (stock.name if stock else '') or code).strip()
        market = '\u6caa\u5e02' if code.endswith('.SH') else '\u6df1\u5e02' if code.endswith('.SZ') else ''
        return code, resolved_name, market

    @staticmethod
    def add_to_watchlist(user_id, ts_code, stock_name=None, source='manual'):
        code, resolved_name, market = UserActivityService.resolve_stock_snapshot(ts_code, stock_name)
        if not code:
            return False, '\u8bf7\u9009\u62e9\u6709\u6548\u7684\u80a1\u7968\u540e\u518d\u52a0\u5165\u81ea\u9009\u3002', None

        existing = UserWatchlist.query.filter_by(user_id=user_id, ts_code=code).first()
        if existing:
            return True, '\u8be5\u80a1\u7968\u5df2\u5728\u4f60\u7684\u81ea\u9009\u80a1\u4e2d\u3002', existing

        item = UserWatchlist(
            user_id=user_id,
            ts_code=code,
            stock_name=resolved_name,
            market=market,
            source=(source or 'manual').strip() or 'manual',
        )
        db.session.add(item)
        db.session.commit()
        return True, f'\u5df2\u5c06 {resolved_name} \u52a0\u5165\u81ea\u9009\u80a1\u3002', item

    @staticmethod
    def remove_from_watchlist(user_id, ts_code):
        code = UserActivityService.normalize_ts_code(ts_code)
        item = UserWatchlist.query.filter_by(user_id=user_id, ts_code=code).first()
        if item is None:
            return False, '\u672a\u627e\u5230\u5bf9\u5e94\u7684\u81ea\u9009\u80a1\u8bb0\u5f55\u3002'

        db.session.delete(item)
        db.session.commit()
        return True, f'\u5df2\u4ece\u81ea\u9009\u80a1\u4e2d\u79fb\u9664 {item.stock_name or code}\u3002'

    @staticmethod
    def record_analysis(user_id, module_name, summary, ts_code=None, stock_name=None):
        if not summary:
            return None

        code, resolved_name, _ = UserActivityService.resolve_stock_snapshot(ts_code, stock_name)
        record = UserAnalysisRecord(
            user_id=user_id,
            ts_code=code or None,
            stock_name=resolved_name or None,
            module_name=(module_name or '\u80a1\u7968\u5206\u6790').strip() or '\u80a1\u7968\u5206\u6790',
            summary=summary.strip(),
        )
        db.session.add(record)
        db.session.commit()
        return record

    @staticmethod
    def record_chat(user_id, question, answer):
        if not question or not answer:
            return None

        record = UserChatHistory(
            user_id=user_id,
            question=question.strip(),
            answer=answer.strip(),
        )
        db.session.add(record)
        db.session.commit()
        return record
