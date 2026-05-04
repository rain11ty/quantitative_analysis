# -*- coding: utf-8 -*-
"""统一缓存工具 - 自动选择 Redis 或内存缓存

使用方式：
    from app.utils.cache_utils import cache

    # 设置缓存（TTL 30秒）
    cache.set('my_key', data, ttl=30)

    # 获取缓存
    result = cache.get('my_key')

    # 删除缓存
    cache.delete('my_key')

特性：
    - Redis 可用时使用 Redis（跨进程共享、持久化）
    - Redis 不可用时自动降级为进程内内存缓存
    - 支持 JSON 序列化/反序列化
"""

import json
import threading
import time
from typing import Any, Callable, Optional

from loguru import logger

# Per-key locks for thundering herd protection
_locks: dict = {}
_locks_lock = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    """Get or create a per-key lock."""
    with _locks_lock:
        if key not in _locks:
            _locks[key] = threading.Lock()
        return _locks[key]


class MemoryCache:
    """进程内 TTL 缓存（降级方案）"""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry['ts'] > entry['ttl']:
            del self._store[key]
            return None
        return entry['data']

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        self._store[key] = {'ts': time.time(), 'data': value, 'ttl': ttl}

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self, prefix: str = '') -> None:
        if not prefix:
            self._store.clear()
            return
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl: int = 30) -> Any:
        """Thundering-herd-safe get-or-compute. Uses a per-key lock so that
        only one thread executes *compute_fn* for a given *key* at a time."""
        result = self.get(key)
        if result is not None:
            return result

        lock = _get_lock(key)
        with lock:
            # Double-check after acquiring lock
            result = self.get(key)
            if result is not None:
                return result
            value = compute_fn()
            self.set(key, value, ttl=ttl)
            return value

    def is_redis(self) -> bool:
        return False


class RedisCache:
    """Redis 缓存（主方案）"""

    PREFIX = 'qa:'

    def __init__(self, redis_client):
        self._client = redis_client

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(f'{self.PREFIX}{key}')
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning(f'[RedisCache] get failed for {key}: {exc}')
            return None

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            self._client.setex(f'{self.PREFIX}{key}', ttl, serialized)
        except Exception as exc:
            logger.warning(f'[RedisCache] set failed for {key}: {exc}')

    def delete(self, key: str) -> None:
        try:
            self._client.delete(f'{self.PREFIX}{key}')
        except Exception as exc:
            logger.warning(f'[RedisCache] delete failed for {key}: {exc}')

    def clear(self, prefix: str = '') -> None:
        try:
            pattern = f'{self.PREFIX}{prefix}*'
            keys = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
        except Exception as exc:
            logger.warning(f'[RedisCache] clear failed for prefix={prefix}: {exc}')

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl: int = 30) -> Any:
        """Thundering-herd-safe get-or-compute. Uses a per-key lock so that
        only one thread executes *compute_fn* for a given *key* at a time."""
        result = self.get(key)
        if result is not None:
            return result

        lock = _get_lock(key)
        with lock:
            # Double-check after acquiring lock
            result = self.get(key)
            if result is not None:
                return result
            value = compute_fn()
            self.set(key, value, ttl=ttl)
            return value

    def is_redis(self) -> bool:
        return True


# 全局缓存实例（懒初始化）
_cache_instance: Optional[Any] = None


def init_cache(app=None):
    """初始化缓存实例，在 Flask app 创建后调用"""
    global _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    # 尝试使用 Redis
    try:
        from app.extensions import redis_client
        if redis_client is not None:
            redis_client.ping()  # 二次确认连接正常
            _cache_instance = RedisCache(redis_client)
            logger.info('[Cache] 使用 Redis 缓存')
            return _cache_instance
    except Exception as exc:
        logger.warning(f'[Cache] Redis 不可用，降级为内存缓存: {exc}')

    _cache_instance = MemoryCache()
    logger.info('[Cache] 使用内存缓存')
    return _cache_instance


def get_cache():
    """获取缓存实例，首次调用时自动尝试连接 Redis"""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance
    # 优先尝试通过 Flask extensions 获取 Redis
    try:
        from app.extensions import redis_client
        if redis_client is not None:
            redis_client.ping()
            _cache_instance = RedisCache(redis_client)
            logger.info('[Cache] 使用 Redis 缓存（via extensions）')
            return _cache_instance
    except Exception:
        pass
    # 降级：直接从环境变量连接 Redis（Celery worker 没有 Flask app context）
    try:
        import os
        import redis as _redis
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        db_num = int(os.getenv('REDIS_DB', '0'))
        password = os.getenv('REDIS_PASSWORD') or None
        if os.getenv('REDIS_ENABLED', 'true').lower() != 'true':
            raise RuntimeError('Redis disabled')
        client = _redis.Redis(host=host, port=port, db=db_num, password=password,
                              decode_responses=True, socket_connect_timeout=3,
                              socket_timeout=5, retry_on_timeout=True)
        client.ping()
        _cache_instance = RedisCache(client)
        logger.info(f'[Cache] 使用 Redis 缓存（直连 {host}:{port}/{db_num}）')
        return _cache_instance
    except Exception as exc:
        logger.warning(f'[Cache] Redis 不可用，降级为内存缓存: {exc}')
    _cache_instance = MemoryCache()
    logger.info('[Cache] 使用内存缓存')
    return _cache_instance



class CacheProxy:
    """模块级代理，方便 from app.utils.cache_utils import cache 直接使用"""

    def get(self, key: str) -> Optional[Any]:
        return get_cache().get(key)

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        get_cache().set(key, value, ttl=ttl)

    def delete(self, key: str) -> None:
        get_cache().delete(key)

    def clear(self, prefix: str = '') -> None:
        get_cache().clear(prefix)

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl: int = 30) -> Any:
        return get_cache().get_or_compute(key, compute_fn, ttl=ttl)

    def is_redis(self) -> bool:
        return get_cache().is_redis()


cache = CacheProxy()
