# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

load_dotenv(encoding='utf-8')


class Config:
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
    DB_NAME = os.getenv('DB_NAME', 'stock_cursor')
    DB_CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?charset={DB_CHARSET}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
    }
    
    # --- 安全配置 ---
    # 生产环境必须通过 .env 设置 SECRET_KEY，禁止使用弱默认值
    _secret_key = os.getenv('SECRET_KEY', '')
    if not _secret_key or _secret_key == 'your-secret-key-here':
        import sys
        if os.getenv('FLASK_ENV') == 'production' or os.getenv('DEBUG', '').lower() == 'false':
            print(
                '[FATAL] SECRET_KEY 未设置或使用了不安全的默认值！'
                '请在 .env 中设置：SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")',
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print('[WARNING] 使用默认 SECRET_KEY（仅限开发环境），生产环境必须设置！', file=sys.stderr)
            _secret_key = 'dev-secret-key-for-testing-only'
    SECRET_KEY = _secret_key

    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/stock_analysis.log')

    # --- Redis 配置 ---
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '') or None
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'

    # --- 静态文件版本号（每次更新代码后修改此值，强制浏览器刷新缓存）---
    STATIC_VERSION = '20260427'

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # --- 邮件配置（Resend SMTP，需在 .env 中设置）---
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.resend.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '465'))
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'true').lower() == 'true'
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')                     # Resend 固定填 resend
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')                     # Resend API Token（勿提交到 Git）
    _MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '')
    if _MAIL_DEFAULT_SENDER:
        MAIL_DEFAULT_SENDER = (_MAIL_DEFAULT_SENDER, _MAIL_DEFAULT_SENDER.split('@')[0] if '@' in _MAIL_DEFAULT_SENDER else 'StockAnalysis')
    else:
        MAIL_DEFAULT_SENDER = ('noreply@stock-analysis.local', 'StockAnalysis')
    MAIL_VERIFY_CODE_EXPIRE = int(os.getenv('MAIL_VERIFY_CODE_EXPIRE', '300'))   # 验证码有效期(秒)，默认5分钟

    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'deepseek' if os.getenv('DEEPSEEK_API_KEY') else 'ollama')

    LLM_CONFIG = {
        'provider': LLM_PROVIDER,
        'ollama': {
            'base_url': os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
            'model': os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:latest'),
            'timeout': int(os.getenv('OLLAMA_TIMEOUT', '60')),
            'temperature': float(os.getenv('OLLAMA_TEMPERATURE', '0.1')),
            'max_tokens': int(os.getenv('OLLAMA_MAX_TOKENS', '2048'))
        },
        'deepseek': {
            'api_key': os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY'),
            'model': os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
            'base_url': os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
            'timeout': int(os.getenv('DEEPSEEK_TIMEOUT', '60')),
            'temperature': float(os.getenv('DEEPSEEK_TEMPERATURE', '0.1')),
            'max_tokens': int(os.getenv('DEEPSEEK_MAX_TOKENS', '2048'))
        },
        'openai': {
            'api_key': os.getenv('OPENAI_API_KEY'),
            'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            'base_url': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
            'timeout': int(os.getenv('OPENAI_TIMEOUT', '60')),
            'temperature': float(os.getenv('OPENAI_TEMPERATURE', '0.1')),
            'max_tokens': int(os.getenv('OPENAI_MAX_TOKENS', '2048'))
        }
    }


class DevelopmentConfig(Config):
    DEBUG = True
    # 开发环境也启用 HttpOnly 和 SameSite（Secure 仅 HTTPS 下生效，开发环境不设）
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

class ProductionConfig(Config):
    DEBUG = False

    # --- Session Cookie 安全配置 ---
    # Secure: 仅 HTTPS 传输（可通过 .env 设为 False 用于 HTTP 测试）
    # HttpOnly: 禁止 JavaScript 读取 Cookie（防 XSS 窃取）
    # SameSite=Lax: 跨站请求不携带 Cookie，防止 CSRF
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = os.getenv('REMEMBER_COOKIE_SECURE', 'true').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}