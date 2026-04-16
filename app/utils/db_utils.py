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

    @classmethod
    def reload_from_env(cls):
        load_dotenv(override=True, encoding='utf-8')

        cls._host = os.getenv('DB_HOST', 'localhost')
        cls._user = os.getenv('DB_USER', 'root')
        cls._password = os.getenv('DB_PASSWORD', 'root')
        cls._database = os.getenv('DB_NAME', 'stock_cursor')
        cls._charset = os.getenv('DB_CHARSET', 'utf8mb4')
        cls._tushare_token = (os.getenv('TUSHARE_TOKEN', '') or '').strip()
        cls._tushare_proxy_url = (os.getenv('TUSHARE_PROXY_URL', 'http://tsy.xiaodefa.cn') or '').strip()

    @classmethod
    def get_tushare_proxy_url(cls):
        cls.reload_from_env()
        return cls._tushare_proxy_url

    @classmethod
    def init_tushare_api(cls):
        cls.reload_from_env()
        if not cls._tushare_token:
            raise ValueError('Tushare token is missing in .env.')

        ts.set_token(cls._tushare_token)
        pro = ts.pro_api()
        if cls._tushare_proxy_url:
            pro._DataApi__http_url = cls._tushare_proxy_url
        return pro

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
