"""
Путь: src/config/database_config.py
Описание: Конфигурация подключения к базе данных PostgreSQL
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()


class DatabaseConfig(BaseSettings):
    """Конфигурация базы данных PostgreSQL."""

    model_config = ConfigDict(
        case_sensitive=False,
        extra='ignore'
    )

    # Основные параметры подключения
    host: str = Field(default=os.getenv("DB_HOST", "localhost"))
    port: int = Field(default=int(os.getenv("DB_PORT", "5432")))
    database: str = Field(default=os.getenv("DB_NAME", "crypto_bot"))
    username: str = Field(default=os.getenv("DB_USER", "crypto_user"))
    password: str = Field(default=os.getenv("DB_PASSWORD", "crypto_pass"))

    # URL подключения (альтернативный способ)
    database_url: str = Field(default=os.getenv("DATABASE_URL", ""))

    # Настройки пула соединений
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=3600)

    # Настройки соединения
    connect_timeout: int = Field(default=10)
    command_timeout: int = Field(default=30)

    # Настройки для разработки
    echo_queries: bool = Field(default=False)
    create_tables: bool = Field(default=True)

    def get_database_url(self) -> str:
        """Получить URL подключения к БД."""
        # Если есть готовый URL, используем его
        if self.database_url and self.database_url.strip():
            return self.database_url

        # Создаем URL из компонентов
        try:
            url = URL.create(
                drivername="postgresql+asyncpg",
                username=self.username,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database,
            )

            return url.render_as_string(hide_password=False)

        except Exception as e:
            # Fallback - возвращаем простую строку URL
            return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class TestDatabaseConfig(DatabaseConfig):
    """Конфигурация тестовой базы данных."""

    model_config = ConfigDict(
        case_sensitive=False,
        extra='ignore'
    )

    database: str = Field(default="crypto_bot_test")

    # Тестовая база должна пересоздаваться
    drop_tables: bool = Field(default=True)
    create_tables: bool = Field(default=True)


# Глобальные экземпляры конфигурации
database_config = DatabaseConfig()
test_database_config = TestDatabaseConfig()


def get_database_config() -> DatabaseConfig:
    """
    Получить конфигурацию основной базы данных.

    Returns:
        DatabaseConfig: Конфигурация базы данных
    """
    return database_config


def get_test_database_config() -> TestDatabaseConfig:
    """
    Получить конфигурацию тестовой базы данных.

    Returns:
        TestDatabaseConfig: Конфигурация тестовой базы данных
    """
    return test_database_config


def get_database_url(test_mode: bool = False) -> str:
    """
    Получить URL подключения к базе данных.

    Args:
        test_mode: Если True, возвращает URL тестовой базы

    Returns:
        str: URL подключения к базе данных
    """
    config = test_database_config if test_mode else database_config
    return config.get_database_url()


def get_sync_database_url(test_mode: bool = False) -> str:
    """
    Получить синхронный URL подключения к БД (для миграций).

    Args:
        test_mode: Если True, возвращает URL тестовой базы

    Returns:
        str: Синхронный URL подключения к базе данных
    """
    async_url = get_database_url(test_mode)
    return async_url.replace("postgresql+psycopg://", "postgresql://")


def get_connection_params(test_mode: bool = False) -> dict:
    """
    Получить параметры подключения к базе данных.

    Args:
        test_mode: Если True, возвращает параметры тестовой базы

    Returns:
        dict: Параметры подключения
    """
    config = test_database_config if test_mode else database_config

    return {
        "pool_size": config.pool_size,
        "max_overflow": config.max_overflow,
        "pool_timeout": config.pool_timeout,
        "pool_recycle": config.pool_recycle,
        "echo": config.echo_queries,
    }