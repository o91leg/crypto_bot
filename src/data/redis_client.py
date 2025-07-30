"""
Путь: src/data/redis_client.py
Описание: Подключение к Redis для кеширования данных
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
from typing import Optional, Any, Dict, List, Union
from contextlib import asynccontextmanager
import redis.asyncio as redis
import json
import structlog

from config.redis_config import get_redis_config, get_redis_connection_params, get_cache_key, get_ttl_for_key_type
from utils.exceptions import CacheError, CacheConnectionError, CacheKeyError

# Настройка логирования
logger = structlog.get_logger(__name__)

# Глобальные переменные для подключения
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


async def init_redis(test_mode: bool = False) -> None:
    """
    Инициализировать подключение к Redis.

    Args:
        test_mode: Использовать тестовую конфигурацию
    """
    global _redis_pool, _redis_client

    try:
        # Получаем параметры подключения
        connection_params = get_redis_connection_params(test_mode)
        config = get_redis_config()

        logger.info("Initializing Redis connection", **connection_params)

        # Создаем пул соединений
        _redis_pool = redis.ConnectionPool(
            **connection_params
        )

        # Создаем клиент
        _redis_client = redis.Redis(
            connection_pool=_redis_pool,
            decode_responses=config.decode_responses
        )

        # Проверяем подключение
        await _redis_client.ping()

        logger.info("Redis connection initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize Redis connection", error=str(e))
        raise CacheConnectionError(f"Failed to connect to Redis: {str(e)}")


async def close_redis() -> None:
    """Закрыть подключение к Redis."""
    global _redis_pool, _redis_client

    try:
        if _redis_client:
            await _redis_client.aclose()
            logger.info("Redis client closed")

        if _redis_pool:
            await _redis_pool.aclose()
            logger.info("Redis pool closed")

        _redis_client = None
        _redis_pool = None

    except Exception as e:
        logger.error("Error closing Redis connection", error=str(e))


def get_redis_client() -> redis.Redis:
    """
    Получить клиент Redis.

    Returns:
        redis.Redis: Клиент Redis

    Raises:
        CacheConnectionError: Если клиент не инициализирован
    """
    if _redis_client is None:
        raise CacheConnectionError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


@asynccontextmanager
async def get_redis_connection():
    """
    Контекстный менеджер для получения соединения Redis.

    Yields:
        redis.Redis: Клиент Redis
    """
    client = get_redis_client()
    try:
        yield client
    except Exception as e:
        logger.error("Redis operation error", error=str(e))
        raise CacheError(f"Redis operation failed: {str(e)}")


class RedisCache:
    """Класс для работы с кешем Redis."""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self._client: Optional[redis.Redis] = None

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        if _redis_client is None:
            await init_redis(self.test_mode)
        self._client = get_redis_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        # Не закрываем глобальное подключение
        pass

    async def set(
        self,
        key_type: str,
        key_parts: List[str],
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Установить значение в кеш.

        Args:
            key_type: Тип ключа (candle, indicator, user, etc.)
            key_parts: Части ключа
            value: Значение для сохранения
            ttl: TTL в секундах (если None, берется из конфигурации)

        Returns:
            bool: True если операция успешна
        """
        try:
            cache_key = get_cache_key(key_type, *key_parts, test_mode=self.test_mode)

            # Сериализуем значение в JSON
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)

            # Определяем TTL
            if ttl is None:
                ttl = get_ttl_for_key_type(key_type, self.test_mode)

            # Сохраняем в Redis
            result = await self._client.setex(cache_key, ttl, serialized_value)

            logger.debug("Cache set", key=cache_key, ttl=ttl)
            return bool(result)

        except Exception as e:
            logger.error("Cache set error", key_type=key_type, error=str(e))
            raise CacheKeyError(cache_key, "set")

    async def get(self, key_type: str, *key_parts: str) -> Optional[Any]:
        """
        Получить значение из кеша.

        Args:
            key_type: Тип ключа
            *key_parts: Части ключа

        Returns:
            Optional[Any]: Значение из кеша или None
        """
        try:
            cache_key = get_cache_key(key_type, *key_parts, test_mode=self.test_mode)

            # Получаем значение из Redis
            value = await self._client.get(cache_key)

            if value is None:
                logger.debug("Cache miss", key=cache_key)
                return None

            # Пытаемся десериализовать JSON
            try:
                result = json.loads(value)
            except json.JSONDecodeError:
                # Если не JSON, возвращаем как строку
                result = value

            logger.debug("Cache hit", key=cache_key)
            return result

        except Exception as e:
            logger.error("Cache get error", key_type=key_type, error=str(e))
            raise CacheKeyError(cache_key, "get")

    async def delete(self, key_type: str, *key_parts: str) -> bool:
        """
        Удалить значение из кеша.

        Args:
            key_type: Тип ключа
            *key_parts: Части ключа

        Returns:
            bool: True если ключ был удален
        """
        try:
            cache_key = get_cache_key(key_type, *key_parts, test_mode=self.test_mode)

            result = await self._client.delete(cache_key)

            logger.debug("Cache delete", key=cache_key, deleted=bool(result))
            return bool(result)

        except Exception as e:
            logger.error("Cache delete error", key_type=key_type, error=str(e))
            raise CacheKeyError(cache_key, "delete")

    async def exists(self, key_type: str, *key_parts: str) -> bool:
        """
        Проверить существование ключа в кеше.

        Args:
            key_type: Тип ключа
            *key_parts: Части ключа

        Returns:
            bool: True если ключ существует
        """
        try:
            cache_key = get_cache_key(key_type, *key_parts, test_mode=self.test_mode)
            result = await self._client.exists(cache_key)
            return bool(result)

        except Exception as e:
            logger.error("Cache exists error", key_type=key_type, error=str(e))
            return False

    async def expire(self, key_type: str, ttl: int, *key_parts: str) -> bool:
        """
        Установить TTL для ключа.

        Args:
            key_type: Тип ключа
            ttl: TTL в секундах
            *key_parts: Части ключа

        Returns:
            bool: True если TTL установлен
        """
        try:
            cache_key = get_cache_key(key_type, *key_parts, test_mode=self.test_mode)
            result = await self._client.expire(cache_key, ttl)
            return bool(result)

        except Exception as e:
            logger.error("Cache expire error", key_type=key_type, error=str(e))
            return False

    async def get_many(self, key_type: str, key_parts_list: List[List[str]]) -> Dict[str, Any]:
        """
        Получить множественные значения из кеша.

        Args:
            key_type: Тип ключа
            key_parts_list: Список списков частей ключей

        Returns:
            Dict[str, Any]: Словарь ключ -> значение
        """
        try:
            # Формируем ключи
            cache_keys = [
                get_cache_key(key_type, *key_parts, test_mode=self.test_mode)
                for key_parts in key_parts_list
            ]

            # Получаем значения
            values = await self._client.mget(cache_keys)

            # Формируем результат
            result = {}
            for cache_key, value in zip(cache_keys, values):
                if value is not None:
                    try:
                        result[cache_key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[cache_key] = value

            logger.debug("Cache mget", keys_count=len(cache_keys), hits=len(result))
            return result

        except Exception as e:
            logger.error("Cache mget error", key_type=key_type, error=str(e))
            return {}

    async def clear_pattern(self, pattern: str) -> int:
        """
        Удалить все ключи по паттерну.

        Args:
            pattern: Паттерн для поиска ключей

        Returns:
            int: Количество удаленных ключей
        """
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info("Cache pattern clear", pattern=pattern, deleted=deleted)
                return deleted

            return 0

        except Exception as e:
            logger.error("Cache pattern clear error", pattern=pattern, error=str(e))
            return 0


# Глобальный экземпляр кеша
_global_cache: Optional[RedisCache] = None


async def get_cache(test_mode: bool = False) -> RedisCache:
    """
    Получить глобальный экземпляр кеша.

    Args:
        test_mode: Использовать тестовый режим

    Returns:
        RedisCache: Экземпляр кеша
    """
    global _global_cache

    if _global_cache is None:
        _global_cache = RedisCache(test_mode)
        await _global_cache.__aenter__()

    return _global_cache


async def check_redis_connection() -> bool:
    """
    Проверить подключение к Redis.

    Returns:
        bool: True если подключение успешно
    """
    try:
        client = get_redis_client()
        await client.ping()
        logger.info("Redis connection check successful")
        return True

    except Exception as e:
        logger.error("Redis connection check failed", error=str(e))
        return False


async def get_redis_info() -> Dict[str, Any]:
    """
    Получить информацию о Redis.

    Returns:
        Dict[str, Any]: Информация о Redis
    """
    try:
        client = get_redis_client()
        info = await client.info()

        return {
            "redis_version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory": info.get("used_memory"),
            "used_memory_human": info.get("used_memory_human"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
        }

    except Exception as e:
        logger.error("Failed to get Redis info", error=str(e))
        return {"error": str(e)}


async def redis_health_check() -> Dict[str, Any]:
    """
    Проверка здоровья Redis.

    Returns:
        Dict[str, Any]: Статус проверки
    """
    try:
        start_time = asyncio.get_event_loop().time()

        # Проверяем подключение
        connection_ok = await check_redis_connection()

        # Измеряем время отклика
        response_time = asyncio.get_event_loop().time() - start_time

        # Получаем информацию о Redis
        redis_info = await get_redis_info()

        return {
            "status": "healthy" if connection_ok else "unhealthy",
            "connection": connection_ok,
            "response_time_ms": round(response_time * 1000, 2),
            "redis_info": redis_info,
            "client_initialized": _redis_client is not None,
            "pool_initialized": _redis_pool is not None,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": False,
        }