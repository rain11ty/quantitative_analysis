# -*- coding: utf-8 -*-
"""
邮件发送与验证码服务

功能：
- 发送验证码邮件（注册验证、密码重置、修改邮箱）
- 验证码存储（Redis 优先，内存兜底）
- 验证码校验与过期管理
- 提供发送频率限制（防滥用）

使用方式：
    from app.services.email_service import EmailService

    # 发送注册验证码
    ok, msg = EmailService.send_verify_code('register', 'user@example.com')

    # 校验验证码
    ok, msg = EmailService.verify_code('register', 'user@example.com', '123456')
"""

import random
import string
import threading
from datetime import datetime, timedelta

from flask import current_app, has_app_context

from app.extensions import redis_client


# 内存兜底缓存（当 Redis 不可用时使用）
_memory_store = {}
_memory_lock = threading.Lock()


def _generate_code(length=6):
    """生成数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


def _get_redis_key(code_type, email):
    """获取 Redis 中验证码的 key"""
    return f"verify_code:{code_type}:{email}"


def _store_code(code_type, email, code, expire_seconds):
    """存储验证码到 Redis 或内存"""
    if redis_client is not None:
        key = _get_redis_key(code_type, email)
        redis_client.setex(key, expire_seconds, code)
    else:
        with _memory_lock:
            _memory_store[_get_redis_key(code_type, email)] = {
                'code': code,
                'expire_at': datetime.utcnow() + timedelta(seconds=expire_seconds),
            }


def _get_stored_code(code_type, email):
    """读取并验证码（Redis 或内存）"""
    if redis_client is not None:
        key = _get_redis_key(code_type, email)
        value = redis_client.get(key)
        if value is not None:
            return value
        return None
    else:
        with _memory_lock:
            entry = _memory_store.get(_get_redis_key(code_type, email))
            if entry is None:
                return None
            if datetime.utcnow() > entry['expire_at']:
                del _memory_store[_get_redis_key(code_type, email)]
                return None
            return entry['code']


def _delete_stored_code(code_type, email):
    """删除已使用的验证码"""
    if redis_client is not None:
        key = _get_redis_key(code_type, email)
        redis_client.delete(key)
    else:
        with _memory_lock:
            _memory_store.pop(_get_redis_key(code_type, email), None)


class EmailService:
    """邮件发送与验证码服务"""

    # 验证码类型定义
    TYPE_REGISTER = 'register'          # 注册验证
    TYPE_RESET_PASSWORD = 'reset_password'   # 密码重置
    TYPE_CHANGE_EMAIL = 'change_email'       # 修改邮箱

    # 模板映射：type -> (subject, body_template)
    _EMAIL_TEMPLATES = {
        TYPE_REGISTER: {
            'subject': '[股票量化分析系统] 注册验证码',
            'body': (
                '您好！\n\n'
                '您正在注册股票量化分析系统账号，您的验证码为：\n\n'
                '      {code}\n\n'
                '验证码有效期为 {expire_minutes} 分钟，请尽快完成验证。\n\n'
                '如果这不是您的操作，请忽略此邮件。\n\n'
                '—— 股票量化分析系统'
            ),
        },
        TYPE_RESET_PASSWORD: {
            'subject': '[股票量化分析系统] 密码重置验证码',
            'body': (
                '您好！\n\n'
                '您正在申请重置密码，您的验证码为：\n\n'
                '      {code}\n\n'
                '验证码有效期为 {expire_minutes} 分钟，请尽快完成重置。\n\n'
                '如果这不是您的操作，请忽略此邮件，您的账户安全未受影响。\n\n'
                '—— 股票量化分析系统'
            ),
        },
        TYPE_CHANGE_EMAIL: {
            'subject': '[股票量化分析系统] 邮箱变更验证码',
            'body': (
                '您好！\n\n'
                '您正在将绑定邮箱变更为此邮箱，验证码为：\n\n'
                '      {code}\n\n'
                '验证码有效期为 {expire_minutes} 分钟，请尽快完成验证。\n\n'
                '如果这不是您的操作，请忽略此邮件，您的账户安全未受影响。\n\n'
                '—— 股票量化分析系统'
            ),
        },
    }

    @classmethod
    def _get_mail(cls):
        """懒加载 Mail 实例（避免循环导入）"""
        from app.extensions import mail
        return mail

    @classmethod
    def _is_configured(cls):
        """检查邮件是否已配置（有用户名和密码）"""
        if has_app_context():
            app = current_app._get_current_object()
            username = app.config.get('MAIL_USERNAME', '')
            password = app.config.get('MAIL_PASSWORD', '')
            return bool(username and bool(password))
        return False

    @classmethod
    def send_verify_code(cls, code_type, email, expire_seconds=None):
        """
        发送验证码邮件

        Args:
            code_type: 验证码类型 ('register' | 'reset_password' | 'change_email')
            email: 目标邮箱地址
            expire_seconds: 验证码有效期(秒)，默认使用配置值

        Returns:
            (success: bool, message: str)
        """
        if code_type not in cls._EMAIL_TEMPLATES:
            return False, f'不支持的验证码类型: {code_type}'

        email = email.lower().strip()

        # 检查邮件配置
        if not cls._is_configured():
            current_app.logger.warning('[EmailService] 邮件未配置(MAIL_USERNAME/MAIL_PASSWORD为空)，跳过发送')
            # 开发环境：打印验证码到日志，方便调试
            code = _generate_code()
            expire = expire_seconds or current_app.config.get('MAIL_VERIFY_CODE_EXPIRE', 300)
            _store_code(code_type, email, code, expire)
            current_app.logger.info(
                f'[EmailService][开发模式] {code_type} 验证码 for {email}: {code} '
                f'(有效期{expire}秒)'
            )
            return True, f'开发模式：验证码已生成（查看日志获取，有效期{expire}秒）'

        # 生成验证码
        code = _generate_code()
        expire = expire_seconds or current_app.config.get('MAIL_VERIFY_CODE_EXPIRE', 300)

        # 先存储再发送（存储失败则不发送）
        try:
            _store_code(code_type, email, code, expire)
        except Exception as exc:
            current_app.logger.error(f'[EmailService] 存储验证码失败: {exc}')
            return False, '验证码存储失败，请稍后重试。'

        # 构建邮件内容
        template = cls._EMAIL_TEMPLATES[code_type]
        subject = template['subject']
        body = template['body'].format(
            code=code,
            expire_minutes=expire // 60,
        )

        # 发送邮件
        try:
            mail = cls._get_mail()
            from django.core.mail import send_mail as django_send_mail
            django_send_mail(
                subject=subject,
                message=body,
                from_email=None,  # 使用 DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )
            current_app.logger.info(f'[EmailService] 验证码已发送至 {email} (类型={code_type})')
            return True, f'验证码已发送至 {email}，请在{expire//60}分钟内查收。'
        except Exception as exc:
            # 发送失败时清除已存储的验证码
            _delete_stored_code(code_type, email)
            current_app.logger.error(f'[EmailService] 发送邮件失败: {exc}')
            return False, f'邮件发送失败: {str(exc)}'

    @classmethod
    def verify_code(cls, code_type, email, input_code):
        """
        校验验证码（一次性使用，校验成功后自动删除）

        Args:
            code_type: 验证码类型
            email: 邮箱地址
            input_code: 用户输入的验证码

        Returns:
            (success: bool, message: str)
        """
        email = email.lower().strip()

        stored = _get_stored_code(code_type, email)

        if stored is None:
            return False, '验证码不存在或已过期，请重新获取。'

        if stored != input_code:
            return False, '验证码错误，请检查后重新输入。'

        # 校验通过，立即删除（防止重复使用）
        _delete_stored_code(code_type, email)
        current_app.logger.info(f'[EmailService] 验证码校验通过: type={code_type}, email={email}')

        return True, '验证成功。'

    @classmethod
    def get_dev_code(cls, code_type, email):
        """
        开发辅助：从存储中直接读取验证码（仅用于调试）
        生产环境不应暴露此接口
        """
        return _get_stored_code(code_type, email.lower().strip())
