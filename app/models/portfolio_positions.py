# -*- coding: utf-8 -*-
from datetime import datetime
from app.extensions import db


class PortfolioPositions(db.Model):
    """模拟持仓管理表"""
    __tablename__ = 'portfolio_positions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键id')
    portfolio_id = db.Column(db.String(50), comment='归属组合ID')
    ts_code = db.Column(db.String(20), db.ForeignKey('stock_basic.ts_code'), comment='持仓股票代码')
    position_size = db.Column(db.Float, comment='持仓数量(股)')
    avg_cost = db.Column(db.Float, comment='持仓均价成本')
    current_price = db.Column(db.Float, comment='最新现价')
    stop_loss_price = db.Column(db.Float, comment='设定的止损价格')
    take_profit_price = db.Column(db.Float, comment='设定的止盈价格')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def to_dict(self):
        return {
            'id': self.id,
            'portfolio_id': self.portfolio_id,
            'ts_code': self.ts_code,
            'position_size': self.position_size,
            'avg_cost': self.avg_cost,
            'current_price': self.current_price,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }