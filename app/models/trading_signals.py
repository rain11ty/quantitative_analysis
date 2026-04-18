# -*- coding: utf-8 -*-
from datetime import datetime
from app.extensions import db


class TradingSignals(db.Model):
    """交易信号记录表"""
    __tablename__ = 'trading_signals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键id')
    ts_code = db.Column(db.String(20), db.ForeignKey('stock_basic.ts_code'), comment='股票代码')
    datetime = db.Column(db.DateTime, default=datetime.utcnow, comment='触发时间')
    strategy_name = db.Column(db.String(100), comment='触发的策略名称')
    signal_type = db.Column(db.String(20), comment='信号(买入/卖出)')
    trigger_price = db.Column(db.Float, comment='触发时价格')
    status = db.Column(db.String(20), default='active', comment='信号状态(活跃/过期)')
    profit_loss_pct = db.Column(db.Float, comment='回测平仓盈亏比(%)')

    def to_dict(self):
        return {
            'id': self.id,
            'ts_code': self.ts_code,
            'datetime': self.datetime.strftime('%Y-%m-%d %H:%M:%S') if self.datetime else None,
            'strategy_name': self.strategy_name,
            'signal_type': self.signal_type,
            'trigger_price': self.trigger_price,
            'status': self.status,
            'profit_loss_pct': self.profit_loss_pct
        }