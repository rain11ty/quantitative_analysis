# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    source = Column(String(50), default='manual', comment='add source')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment='created time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ts_code': self.ts_code,
            'stock_name': self.stock_name,
            'market': self.market,
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
    summary = Column(String(255), nullable=False, comment='record summary')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='created time')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ts_code': self.ts_code,
            'stock_name': self.stock_name,
            'module_name': self.module_name,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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
