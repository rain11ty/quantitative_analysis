# -*- coding: utf-8 -*-
from app.extensions import db
from sqlalchemy import Column, String, Date, DECIMAL


class StockCyqChips(db.Model):
    """每日筹码分布数据表（各价位占比）"""
    __tablename__ = 'stock_cyq_chips'

    ts_code = Column(String(20), primary_key=True, comment='股票代码')
    trade_date = Column(Date, primary_key=True, comment='交易日期')
    price = Column(DECIMAL(10, 2), primary_key=True, comment='成本价格')
    percent = Column(DECIMAL(10, 4), comment='价格占比（%）')

    def to_dict(self):
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'price': float(self.price) if self.price is not None else None,
            'percent': float(self.percent) if self.percent is not None else None,
        }

    def __repr__(self):
        return f'<StockCyqChips {self.ts_code} {self.trade_date} {self.price}>'
