"""
Путь: src/config/redis_config.py
Описание: Конфигурация подключения к Redis для кеширования
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict


class RedisConfig(BaseSettings):
    """Конфигурация Redis для кеширования."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    # Основные параметры подключения
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # URL подключения (альтернативный способ)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")

    # Настройки соединения
    socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(default=5, env="REDIS_CONNECT_TIMEOUT")
    socket_keepalive: bool = Field(default=True, env="REDIS_KEEPALIVE")
    socket_keepalive_options: dict = Field(default_factory=dict)

    # Настройки пула соединений
    max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    retry_on_timeout: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")

    # Настройки кодировки
    encoding: str = Field(default="utf-8", env="REDIS_ENCODING")
    decode_responses: bool = Field(default=True, env="REDIS_DECODE_RESPONSES")

    # Префиксы для ключей кеша
    key_prefix: str = Field(default="crypto_bot", env="REDIS_KEY_PREFIX")

    # TTL для различных типов данных (в секундах)
    candle_ttl: int = Field(default=86400, env="REDIS_CANDLE_TTL")  # 1 день
    indicator_ttl: int = Field(default=3600, env="REDIS_INDICATOR_TTL")  # 1 час
    user_cache_ttl: int = Field(default=1800, env="REDIS_USER_CACHE_TTL")  # 30 минут
    signal_history_ttl: int = Field(default=7200, env="REDIS_SIGNAL_HISTORY_TTL")  # 2 часа

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, v):
        """Валидация URL подключения к Redis."""
        if v:
            return v

        # Если URL не предоставлен, он будет создан в методе get_redis_url()
        return None

    def get_redis_url(self) -> str:
        """
        Получить URL подключения к Redis.

        Returns:
            str: URL подключения к Redis
        """
        if self.redis_url:
            return self.redis_url

        # Собираем URL из компонентов
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        else:
            return f"redis://{self.host}:{self.port}/{self.db}"


class TestRedisConfig(RedisConfig):
    """Конфигурация тестового Redis."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    db: int = Field(default=1, env="TEST_REDIS_DB")  # Используем другую БД для тестов
    key_prefix: str = Field(default="crypto_bot_test", env="TEST_REDIS_KEY_PREFIX")


# Глобальные экземпляры конфигурации
redis_config = RedisConfig()
test_redis_config = TestRedisConfig()


def get_redis_config() -> RedisConfig:
    """
    Получить конфигурацию основного Redis.

    Returns:
        RedisConfig: Конфигурация Redis
    """
    return redis_config


def get_test_redis_config() -> TestRedisConfig:
    """
    Получить конфигурацию тестового Redis.

    Returns:
        TestRedisConfig: Конфигурация тестового Redis
    """
    return test_redis_config


def get_redis_url(test_mode: bool = False) -> str:
    """
    Получить URL подключения к Redis.

    Args:
        test_mode: Если True, возвращает URL тестового Redis

    Returns:
        str: URL подключения к Redis
    """
    config = test_redis_config if test_mode else redis_config
    return config.get_redis_url()


def get_redis_connection_params(test_mode: bool = False) -> dict:
    """
    Получить параметры подключения к Redis.

    Args:
        test_mode: Если True, возвращает параметры тестового Redis

    Returns:
        dict: Параметры подключения к Redis
    """
    config = test_redis_config if test_mode else redis_config

    return {
        "host": config.host,
        "port": config.port,
        "db": config.db,
        "password": config.password,
        "socket_timeout": config.socket_timeout,
        "socket_connect_timeout": config.socket_connect_timeout,
        "socket_keepalive": config.socket_keepalive,
        "socket_keepalive_options": config.socket_keepalive_options,
        "max_connections": config.max_connections,
        "retry_on_timeout": config.retry_on_timeout,
        "encoding": config.encoding,
        "decode_responses": config.decode_responses,
    }


def get_cache_key(key_type: str, *args, test_mode: bool = False) -> str:
    """
    Сгенерировать ключ для кеша с префиксом.

    Args:
        key_type: Тип ключа (candle, indicator, user, etc.)
        *args: Дополнительные части ключа
        test_mode: Если True, использует тестовый префикс

    Returns:
        str: Сгенерированный ключ для кеша
    """
    config = test_redis_config if test_mode else redis_config

    key_parts = [config.key_prefix, key_type] + [str(arg) for arg in args]
    return ":".join(key_parts)


def get_ttl_for_key_type(key_type: str, test_mode: bool = False) -> int:
    """
    Получить TTL для определенного типа ключа.

    Args:
        key_type: Тип ключа (candle, indicator, user, signal_history)
        test_mode: Если True, возвращает значения для тестовой конфигурации

    Returns:
        int: TTL в секундах
    """
    config = test_redis_config if test_mode else redis_config

    ttl_mapping = {
        "candle": config.candle_ttl,
        "indicator": config.indicator_ttl,
        "user": config.user_cache_ttl,
        "signal_history": config.signal_history_ttl,
    }

    return ttl_mapping.get(key_type, 3600)  # По умолчанию 1 час