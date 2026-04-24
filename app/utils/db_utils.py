# -*- coding: utf-8 -*-
import os

import pymysql
import tushare as ts
from dotenv import load_dotenv


load_dotenv(encoding='utf-8')


class DatabaseUtils:
    _host = 'localhost'
    _user = 'root'
    _password = 'root'
    _database = 'stock_cursor'
    _charset = 'utf8mb4'
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

        cls._host = os.getenv('DB_HOST', 'localhost')
        cls._user = os.getenv('DB_USER', 'root')
        cls._password = os.getenv('DB_PASSWORD', 'root')
        cls._database = os.getenv('DB_NAME', 'stock_cursor')
        cls._charset = os.getenv('DB_CHARSET', 'utf8mb4')
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
