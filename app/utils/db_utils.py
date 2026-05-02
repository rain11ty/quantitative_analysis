# -*- coding: utf-8 -*-
import os

import pymysql
import tushare as ts
from dotenv import load_dotenv


load_dotenv(encoding='utf-8')

# 默认值与 config.py Config 类保持一致，避免两处维护
_DEFAULT_HOST = 'localhost'
_DEFAULT_USER = 'root'
_DEFAULT_PASSWORD = 'root'
_DEFAULT_DB_NAME = 'stock_cursor'
_DEFAULT_CHARSET = 'utf8mb4'


class DatabaseUtils:
    _host = _DEFAULT_HOST
    _user = _DEFAULT_USER
    _password = _DEFAULT_PASSWORD
    _database = _DEFAULT_DB_NAME
    _charset = _DEFAULT_CHARSET
    _tushare_token = ''
    _tushare_proxy_url = 'http://tsy.xiaodefa.cn'
    _env_loaded = False

    @classmethod
    def reload_from_env(cls):
        """从 .env 重新加载配置（仅在首次或强制时调用）"""
        if cls._env_loaded:
            return
        cls._force_reload_from_env()

    @classmethod
    def _force_reload_from_env(cls):
        """强制重新加载 .env 配置"""
        load_dotenv(override=True, encoding='utf-8')

        cls._host = os.getenv('DB_HOST', _DEFAULT_HOST)
        cls._user = os.getenv('DB_USER', _DEFAULT_USER)
        cls._password = os.getenv('DB_PASSWORD', _DEFAULT_PASSWORD)
        cls._database = os.getenv('DB_NAME', _DEFAULT_DB_NAME)
        cls._charset = os.getenv('DB_CHARSET', _DEFAULT_CHARSET)
        cls._tushare_token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
        cls._tushare_proxy_url = (os.getenv('TUSHARE_PROXY_URL', 'http://tsy.xiaodefa.cn') or '').strip()
        cls._env_loaded = True

    @classmethod
    def get_tushare_proxy_url(cls):
        return cls._tushare_proxy_url

    @classmethod
    def init_tushare_api(cls):
        """初始化 Tushare Pro API 对象（常规接口：daily/adj_factor/daily_basic 等）"""
        cls.reload_from_env()
        if not cls._tushare_token:
            raise ValueError('Tushare token is missing in .env.')

        ts.set_token(cls._tushare_token)
        pro = ts.pro_api()
        if cls._tushare_proxy_url:
            pro._DataApi__http_url = cls._tushare_proxy_url
        return pro

    @classmethod
    def init_tushare_realtime(cls):
        """初始化 Tushare 实时行情接口（realtime_quote/realtime_tick/realtime_list）

        实时接口为模块级函数，需额外设置 cons.verify_token_url 以通过鉴权。
        返回 tushare 模块本身，调用方式：
            ts_mod = DatabaseUtils.init_tushare_realtime()
            df = ts_mod.realtime_quote(ts_code='600000.SH')
            df = ts_mod.realtime_list(src='dc')
        """
        cls.reload_from_env()
        if not cls._tushare_token:
            raise ValueError('Tushare token is missing in .env.')

        ts.set_token(cls._tushare_token)
        pro = ts.pro_api()
        if cls._tushare_proxy_url:
            pro._DataApi__http_url = cls._tushare_proxy_url

        # 实时爬虫接口需额外设置 verify_token_url
        if cls._tushare_proxy_url:
            from tushare.stock import cons as ct
            ct.verify_token_url = cls._tushare_proxy_url + "/dataapi/sdk-event"

        return ts

    @classmethod
    def connect_to_mysql(cls):
        cls.reload_from_env()
        conn = pymysql.connect(
            host=cls._host,
            user=cls._user,
            password=cls._password,
            database=cls._database,
            charset=cls._charset,
        )
        cursor = conn.cursor()
        return conn, cursor


def get_db_connection():
    """统一数据库连接入口，返回 (conn, cursor)。

    供 scripts/ 和 Celery 任务使用，避免各处重复连接参数。
    """
    return DatabaseUtils.connect_to_mysql()
