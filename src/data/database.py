"""
Путь: src/data/database.py
Описание: Подключение к базе данных и управление сессиями
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool
import structlog

from config.database_config import get_database_config, get_connection_params
from data.models.base_model import Base

# Настройка логирования
logger = structlog.get_logger(__name__)

# Глобальные переменные для движка и фабрики сессий
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    Получить движок базы данных.

    Returns:
        AsyncEngine: Движок SQLAlchemy

    Raises:
        RuntimeError: Если движок не инициализирован
    """
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_database() first.")
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Получить фабрику сессий.

    Returns:
        async_sessionmaker: Фабрика сессий

    Raises:
        RuntimeError: Если фабрика не инициализирована
    """
    global _session_maker
    if _session_maker is None:
        raise RuntimeError("Session maker not initialized. Call init_database() first.")
    return _session_maker


async def init_database(test_mode: bool = False) -> None:
    """
    Инициализировать подключение к базе данных.

    Args:
        test_mode: Использовать тестовую базу данных
    """
    global _engine, _session_maker

    config = get_database_config()
    database_url = config.database_url

    if test_mode:
        # Для тестов используем отдельную БД
        database_url = database_url.replace("/crypto_bot", "/crypto_bot_test")

    logger.info("Initializing database connection", url=database_url.split('@')[1] if '@' in database_url else database_url)

    # Параметры подключения
    connection_params = get_connection_params(test_mode)

    # Создание движка
    _engine = create_async_engine(
        database_url,
        echo=config.echo_queries,
        pool_size=connection_params["pool_size"],
        max_overflow=connection_params["max_overflow"],
        pool_timeout=connection_params["pool_timeout"],
        pool_recycle=connection_params["pool_recycle"],
        poolclass=NullPool if test_mode else None,  # Отключаем пул для тестов
    )

    # Создание фабрики сессий
    _session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False
    )

    # Создание таблиц если необходимо
    if config.create_tables:
        await create_tables()

    logger.info("Database initialized successfully")


async def create_tables() -> None:
    """Создать все таблицы в базе данных."""
    global _engine

    if _engine is None:
        await init_database()

    logger.info("Creating database tables")

    # Импортируем все модели для регистрации в метаданных
    from data.models.user_model import User
    from data.models.pair_model import Pair
    from data.models.user_pair_model import UserPair
    from data.models.candle_model import Candle
    from data.models.signal_history_model import SignalHistory

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def drop_tables() -> None:
    """Удалить все таблицы из базы данных."""
    global _engine

    if _engine is None:
        await init_database()

    logger.info("Dropping database tables")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("Database tables dropped successfully")


async def close_database() -> None:
    """Закрыть подключение к базе данных."""
    global _engine, _session_maker

    if _engine is not None:
        logger.info("Closing database connection")
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("Database connection closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для получения сессии базы данных.

    Yields:
        AsyncSession: Сессия базы данных

    Examples:
        async with get_session() as session:
            user = await session.get(User, user_id)
    """
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def execute_with_session(func, *args, **kwargs):
    """
    Выполнить функцию с сессией базы данных.

    Args:
        func: Функция для выполнения
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы

    Returns:
        Результат выполнения функции
    """
    async with get_session() as session:
        return await func(session, *args, **kwargs)


class DatabaseManager:
    """Менеджер базы данных для управления подключениями."""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self._initialized = False

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        if not self._initialized:
            await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        await self.close()

    async def initialize(self) -> None:
        """Инициализировать менеджер базы данных."""
        await init_database(self.test_mode)
        self._initialized = True
        logger.info("Database manager initialized", test_mode=self.test_mode)

    async def close(self) -> None:
        """Закрыть менеджер базы данных."""
        if self._initialized:
            await close_database()
            self._initialized = False
            logger.info("Database manager closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Получить сессию базы данных.

        Yields:
            AsyncSession: Сессия базы данных
        """
        if not self._initialized:
            await self.initialize()

        async with get_session() as session:
            yield session

    async def create_tables(self) -> None:
        """Создать таблицы."""
        if not self._initialized:
            await self.initialize()
        await create_tables()

    async def drop_tables(self) -> None:
        """Удалить таблицы."""
        if not self._initialized:
            await self.initialize()
        await drop_tables()


async def check_database_connection() -> bool:
    """
    Проверить подключение к базе данных.

    Returns:
        bool: True если подключение успешно
    """
    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection check successful")
        return True
    except Exception as e:
        logger.error("Database connection check failed", error=str(e))
        return False


async def get_database_info() -> dict:
    """
    Получить информацию о базе данных.

    Returns:
        dict: Информация о БД
    """
    try:
        async with get_session() as session:
            # Получаем версию PostgreSQL
            result = await session.execute("SELECT version()")
            version = result.scalar()

            # Получаем информацию о подключении
            result = await session.execute("SELECT current_database(), current_user")
            db_info = result.fetchone()

            return {
                "version": version,
                "database": db_info[0] if db_info else None,
                "user": db_info[1] if db_info else None,
                "engine": str(_engine.url) if _engine else None,
            }
    except Exception as e:
        logger.error("Failed to get database info", error=str(e))
        return {"error": str(e)}


# Функции для упрощения работы с транзакциями
@asynccontextmanager
async def transaction():
    """
    Контекстный менеджер для выполнения транзакций.

    Examples:
        async with transaction() as session:
            user = User(id=123, username="test")
            session.add(user)
            # Автоматический commit при успехе, rollback при ошибке
    """
    async with get_session() as session:
        async with session.begin():
            yield session


async def health_check() -> dict:
    """
    Проверка здоровья базы данных.

    Returns:
        dict: Статус проверки
    """
    try:
        start_time = asyncio.get_event_loop().time()

        # Проверяем подключение
        connection_ok = await check_database_connection()

        # Измеряем время отклика
        response_time = asyncio.get_event_loop().time() - start_time

        # Получаем информацию о БД
        db_info = await get_database_info()

        return {
            "status": "healthy" if connection_ok else "unhealthy",
            "connection": connection_ok,
            "response_time_ms": round(response_time * 1000, 2),
            "database_info": db_info,
            "engine_initialized": _engine is not None,
            "session_maker_initialized": _session_maker is not None,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": False,
        }