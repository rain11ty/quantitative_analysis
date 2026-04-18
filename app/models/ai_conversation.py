# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.extensions import db


class UserAiConversation(db.Model):
    __tablename__ = 'user_ai_conversation'

    id = Column(Integer, primary_key=True, comment='id')
    user_id = Column(Integer, ForeignKey('user_account.id'), nullable=False, index=True, comment='user id')
    title = Column(String(120), nullable=False, default='新对话', comment='conversation title')
    summary = Column(String(255), nullable=True, comment='latest message preview')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment='created time')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True, comment='updated time')
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='last message time')

    messages = db.relationship('UserAiMessage', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
        }


class UserAiMessage(db.Model):
    __tablename__ = 'user_ai_message'

    STATUS_COMPLETED = 'completed'
    STATUS_STREAMING = 'streaming'
    STATUS_FAILED = 'failed'

    id = Column(Integer, primary_key=True, comment='id')
    conversation_id = Column(Integer, ForeignKey('user_ai_conversation.id'), nullable=False, index=True, comment='conversation id')
    role = Column(String(20), nullable=False, index=True, comment='message role')
    content = Column(Text, nullable=False, comment='message content')
    status = Column(String(20), nullable=False, default=STATUS_COMPLETED, index=True, comment='message status')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='created time')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment='updated time')

    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
