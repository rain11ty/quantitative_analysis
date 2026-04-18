# -*- coding: utf-8 -*-
from flask import request
from app.extensions import db
from app.models import SystemLog


class SystemLogService:
    @staticmethod
    def write(action_type, message, user=None, status='success'):
        ip = request.headers.get('X-Forwarded-For', request.remote_addr) if request else None
        user_agent = request.headers.get('User-Agent', '')[:255] if request else ''

        log = SystemLog(
            user_id=getattr(user, 'id', None),
            username=getattr(user, 'username', None),
            role=getattr(user, 'role', None),
            action_type=action_type,
            message=message,
            ip=ip,
            status=status,
            user_agent=user_agent,
        )
        db.session.add(log)
        db.session.commit()
        return log
