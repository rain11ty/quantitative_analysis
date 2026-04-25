# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

# 强制使用 pbkdf2:sha256，兼容 Werkzeug 1.x / 2.x
_HASH_METHOD = 'pbkdf2:sha256'


class User(db.Model):
    __tablename__ = 'user_account'

    ROLE_USER = 'user'
    ROLE_ADMIN = 'admin'
    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_BANNED = 'banned'

    id = Column(Integer, primary_key=True, comment='id')
    username = Column(String(50), unique=True, nullable=False, index=True, comment='username')
    email = Column(String(120), unique=True, nullable=False, index=True, comment='email')
    email_verified = Column(db.Boolean, default=False, nullable=False, comment='邮箱是否已验证')
    password_hash = Column(String(255), nullable=False, comment='password hash')
    nickname = Column(String(50), nullable=True, comment='nickname')
    avatar = Column(String(255), nullable=True, comment='avatar url')
    phone = Column(String(20), nullable=True, comment='phone')
    role = Column(String(20), default=ROLE_USER, nullable=False, index=True, comment='role')
    status = Column(String(20), default=STATUS_ACTIVE, nullable=False, index=True, comment='status')
    last_login_at = Column(DateTime, nullable=True, comment='last login time')
    last_login_ip = Column(String(64), nullable=True, comment='last login ip')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment='created time')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment='updated time')

    watchlist_items = db.relationship('UserWatchlist', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    analysis_records = db.relationship('UserAnalysisRecord', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    chat_records = db.relationship('UserChatHistory', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    ai_conversations = db.relationship('UserAiConversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_active_user(self):
        return self.status == self.STATUS_ACTIVE

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method=_HASH_METHOD)

    def check_password(self, password):
        try:
            result = check_password_hash(self.password_hash, password)
            if result:
                self._upgrade_hash_if_needed(password)
            return result
        except ValueError:
            # scrypt 等不支持的哈希算法 —— 旧密码需重置
            return False

    def _upgrade_hash_if_needed(self, password):
        """如果当前哈希不是 pbkdf2:sha256，自动升级"""
        if not self.password_hash.startswith('pbkdf2:sha256'):
            self.password_hash = generate_password_hash(password, method=_HASH_METHOD)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'email_verified': self.email_verified,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'phone': self.phone,
            'role': self.role,
            'status': self.status,
            'is_admin': self.is_admin,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'last_login_ip': self.last_login_ip,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'
