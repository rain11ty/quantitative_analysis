# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from app.extensions import db


class SystemLog(db.Model):
    __tablename__ = 'system_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=True, index=True)
    username = Column(String(50), nullable=True, index=True)
    role = Column(String(20), nullable=True, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    ip = Column(String(64), nullable=True)
    status = Column(String(20), default='success', nullable=False, index=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'role': self.role,
            'action_type': self.action_type,
            'message': self.message,
            'ip': self.ip,
            'status': self.status,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
