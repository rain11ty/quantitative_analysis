# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from app.extensions import db


class UserWatchlist(db.Model):
    __tablename__ = 'user_watchlist'
    __table_args__ = (
        UniqueConstraint('user_id', 'ts_code', name='uq_user_watchlist_user_stock'),
    )

    id = Column(Integer, primary_key=True, comment='id')
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=False, index=True, comment='user id')
    ts_code = Column(String(20), nullable=False, index=True, comment='stock ts code')
    stock_name = Column(String(100), nullable=False, comment='stock name snapshot')
    market = Column(String(20), comment='market snapshot')
    note = Column(String(255), comment='备注信息')
    sort_order = Column(Integer, default=0, comment='排序权重(数字越小越靠前)')
    source = Column(String(50), default='manual', comment='add source')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment='created time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ts_code': self.ts_code,
            'stock_name': self.stock_name,
            'market': self.market,
            'note': self.note or '',
            'sort_order': self.sort_order or 0,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserAnalysisRecord(db.Model):
    __tablename__ = 'user_analysis_record'

    id = Column(Integer, primary_key=True, comment='id')
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=False, index=True, comment='user id')
    ts_code = Column(String(20), index=True, comment='stock ts code')
    stock_name = Column(String(100), comment='stock name snapshot')
    module_name = Column(String(50), nullable=False, comment='module name')
    summary = Column(String(500), nullable=False, comment='record summary')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='created time')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='updated time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ts_code': self.ts_code,
            'stock_name': self.stock_name,
            'module_name': self.module_name,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class UserChatHistory(db.Model):
    __tablename__ = 'user_chat_history'

    id = Column(Integer, primary_key=True, comment='id')
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=False, index=True, comment='user id')
    question = Column(Text, nullable=False, comment='user question')
    answer = Column(Text, nullable=False, comment='assistant answer')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='created time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'question': self.question,
            'answer': self.answer,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserBacktestResult(db.Model):
    __tablename__ = 'user_backtest_result'

    id = Column(Integer, primary_key=True, comment='id')
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=False, index=True, comment='user id')
    ts_code = Column(String(20), index=True, comment='stock ts code')
    stock_name = Column(String(100), comment='stock name snapshot')
    strategy_type = Column(String(30), nullable=False, comment='策略类型')
    strategy_label = Column(String(50), comment='策略显示名称')
    params = Column(JSON, comment='策略参数(JSON)')
    start_date = Column(String(20), nullable=False, comment='回测起始日期')
    end_date = Column(String(20), nullable=False, comment='回测结束日期')
    initial_capital = Column(Float, default=100000.0, comment='初始资金')
    performance = Column(JSON, comment='绩效指标(JSON)')
    trades = Column(JSON, comment='最近交易记录(JSON)')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='created time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ts_code': self.ts_code,
            'stock_name': self.stock_name,
            'strategy_type': self.strategy_type,
            'strategy_label': self.strategy_label or '',
            'params': self.params or {},
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'performance': self.performance or {},
            'trades': (self.trades or [])[-10:],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
