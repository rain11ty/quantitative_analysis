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
        'max_overflow': 20,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'pool_timeout': 60,
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
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

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
    # Secure: 仅 HTTPS 传输（Nginx 做 SSL 终结时，后端 Gunicorn 是 HTTP，需视情况调整）
    # HttpOnly: 禁止 JavaScript 读取 Cookie（防 XSS 窃取）
    # SameSite=Lax: 跨站请求不携带 Cookie，防止 CSRF
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}