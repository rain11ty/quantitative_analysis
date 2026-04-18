# -*- coding: utf-8 -*-
from datetime import datetime
from app.extensions import db


class RiskAlerts(db.Model):
    """盘中风控预警表"""
    __tablename__ = 'risk_alerts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键id')
    ts_code = db.Column(db.String(20), db.ForeignKey('stock_basic.ts_code'), comment='触发预警的股票')
    alert_type = db.Column(db.String(50), comment='预警类型(止损/异动)')
    alert_level = db.Column(db.String(20), comment='风险级别(高/中/低)')
    alert_message = db.Column(db.Text, comment='预警内容描述')
    is_resolved = db.Column(db.Boolean, default=False, comment='是否已被用户确认')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='告警触发时间')

    def to_dict(self):
        return {
            'id': self.id,
            'ts_code': self.ts_code,
            'alert_type': self.alert_type,
            'alert_level': self.alert_level,
            'alert_message': self.alert_message,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }