# -*- coding: utf-8 -*-
from app.extensions import db
from sqlalchemy import Column, String, Date, Text


class StockShock(db.Model):
    """个股异常波动数据表"""
    __tablename__ = 'stock_shock'

    id = Column(db.Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(20), nullable=False, index=True, comment='股票代码')
    trade_date = Column(Date, nullable=False, index=True, comment='公告日期')
    name = Column(String(40), comment='股票名称')
    trade_market = Column(String(20), comment='交易所')
    reason = Column(Text, comment='异常说明')
    period = Column(String(40), comment='异常期间')

    def to_dict(self):
        return {
            'ts_code': self.ts_code,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'name': self.name,
            'trade_market': self.trade_market,
            'reason': self.reason,
            'period': self.period,
        }

    def __repr__(self):
        return f'<StockShock {self.ts_code} {self.trade_date}>'
