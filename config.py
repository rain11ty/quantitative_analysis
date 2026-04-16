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
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/stock_analysis.log')
    
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

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}