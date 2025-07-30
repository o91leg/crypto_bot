"""
Путь: src/main.py
Описание: Главный файл приложения - точка входа крипто-бота
Автор: Crypto Bot Team
Дата создания: 2025-07-28
Обновлено: 2025-07-29 - Добавлена интеграция с системой сигналов
"""

import asyncio
import signal
import sys
import os
import platform
from typing import Optional

# Исправление для Windows - psycopg3 не работает с ProactorEventLoop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.bot_config import get_bot_config, validate_config
from config.database_config import get_database_config
from config.redis_config import get_redis_config
from data.database import init_database, close_database, check_database_connection
from data.redis_client import init_redis, close_redis, check_redis_connection
from bot.handlers.start_handler import register_start_handlers
from bot.middlewares.database_mw import DatabaseMiddleware
from utils.logger import setup_logging
from utils.constants import APP_NAME, APP_VERSION
from utils.exceptions import ConfigurationError, DatabaseError

# Исправленные импорты для разделенных файлов
from bot.handlers.add_pair import register_add_pair_handlers
from bot.handlers.remove_pair_handler import register_remove_pair_handlers
from bot.handlers.my_pairs import register_my_pairs_handlers
from bot.handlers.debug_rsi_handler import register_debug_handlers

# Импорты для системы сигналов и уведомлений
from services.websocket.stream_manager import StreamManager
from services.notifications.notification_queue import notification_queue
from services.notifications.telegram_sender import TelegramSender

# Глобальные переменные
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
stream_manager: Optional[StreamManager] = None
telegram_sender: Optional[TelegramSender] = None
logger = structlog.get_logger(__name__)


async def create_bot() -> Bot:
    """
    Создать экземпляр бота.

    Returns:
        Bot: Экземпляр Telegram бота
    """
    config = get_bot_config()

    # Создаем бота с настройками по умолчанию
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        )
    )

    logger.info("Bot instance created")
    return bot


async def setup_dispatcher() -> Dispatcher:
    """
    Настроить диспетчер и зарегистрировать обработчики.

    Returns:
        Dispatcher: Настроенный диспетчер
    """
    # Создаем диспетчер
    dp = Dispatcher()

    # Добавляем middleware
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Регистрируем обработчики
    register_start_handlers(dp)
    register_add_pair_handlers(dp)
    register_remove_pair_handlers(dp)
    register_my_pairs_handlers(dp)
    register_debug_handlers(dp)

    logger.info("Dispatcher configured and handlers registered")
    return dp


def validate_application_config() -> None:
    """Валидировать конфигурацию приложения."""
    try:
        validate_config()
        logger.info("Application configuration validated successfully")
    except Exception as e:
        logger.error("Configuration validation failed", error=str(e))
        raise ConfigurationError(f"Invalid configuration: {str(e)}")


def setup_signal_handlers() -> None:
    """Настроить обработчики системных сигналов."""
    def signal_handler(signum, frame):
        logger.info("Received signal", signal=signum)
        # Создаем задачу для корректного завершения
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(shutdown_services())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def init_services() -> None:
    """Инициализировать все сервисы."""
    global stream_manager, telegram_sender

    logger.info("Initializing services...")

    # Инициализируем базу данных
    await init_database()
    logger.info("Database initialized")

    # Инициализируем Redis
    await init_redis()
    logger.info("Redis initialized")

    # Создаем отправщик уведомлений
    if bot:
        telegram_sender = TelegramSender(bot)
        logger.info("Telegram sender created")

    # Запускаем очередь уведомлений
    logger.info("Starting notification queue...")
    await notification_queue.start_processing()
    logger.info("Notification queue started")

    # Создаем и запускаем WebSocket stream manager
    logger.info("Starting WebSocket stream manager...")
    stream_manager = StreamManager()
    await stream_manager.start()
    logger.info("WebSocket stream manager started")

    logger.info("All services initialized successfully")


async def shutdown_services() -> None:
    """Корректно остановить все сервисы."""
    global stream_manager, telegram_sender

    logger.info("Shutting down services...")

    try:
        # Останавливаем WebSocket stream manager
        if stream_manager:
            logger.info("Stopping stream manager...")
            await stream_manager.stop()
            logger.info("Stream manager stopped")
        else:
            logger.debug("Stream manager was not initialized")

        # Останавливаем очередь уведомлений
        logger.info("Stopping notification queue...")
        await notification_queue.stop_processing()
        logger.info("Notification queue stopped")

        # Закрываем Telegram sender (если есть активные сессии)
        if telegram_sender:
            logger.info("Closing Telegram sender...")
            try:
                # Telegram бот автоматически закрывает сессии при завершении
                # Дополнительное закрытие не требуется для aiogram 3.x
                logger.info("Telegram sender closed")
            except Exception as e:
                logger.error("Error closing Telegram sender", error=str(e))
        else:
            logger.debug("Telegram sender was not initialized")

        # Закрываем соединения
        logger.info("Closing Redis connection...")
        await close_redis()
        logger.info("Redis connection closed")

        logger.info("Closing database connection...")
        await close_database()
        logger.info("Database connection closed")

        logger.info("All services shut down successfully")

    except Exception as e:
        logger.error("Error during services shutdown", error=str(e))
        # Не re-raise ошибку, чтобы позволить другим ресурсам закрыться

async def create_default_data():
    """Создать данные по умолчанию при первом запуске."""
    from data.database import get_session_maker
    from data.models.pair_model import Pair
    from config.bot_config import get_bot_config

    config = get_bot_config()
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Проверяем, есть ли уже пары в БД
        existing_pair = await Pair.get_by_symbol(session, config.default_pair)

        if not existing_pair:
            logger.info("Creating default trading pair", symbol=config.default_pair)

            # Создаем дефолтную пару BTC/USDT
            try:
                default_pair = await Pair.create_from_symbol(
                    session,
                    config.default_pair
                )
                await session.commit()
                logger.info("Default trading pair created", pair_id=default_pair.id)
            except Exception as e:
                logger.error("Failed to create default pair", error=str(e))
                await session.rollback()


async def on_startup():
    """Функция, выполняемая при запуске бота."""
    logger.info("Bot starting up...")

    # Проверяем подключение к базе данных
    if not await check_database_connection():
        logger.error("Database connection failed")
        raise DatabaseError("Cannot connect to database")

    # Проверяем подключение к Redis
    if not await check_redis_connection():
        logger.error("Redis connection failed")
        raise DatabaseError("Cannot connect to Redis")

    # Получаем информацию о боте
    global bot
    if bot:
        bot_info = await bot.get_me()
        logger.info(
            "Bot information retrieved",
            id=bot_info.id,
            username=bot_info.username,
            first_name=bot_info.first_name
        )

    logger.info("Bot startup completed successfully")


async def on_shutdown():
    """Функция, выполняемая при остановке бота."""
    logger.info("Bot shutting down...")

    try:
        # Останавливаем все сервисы
        await shutdown_services()
        logger.info("All services stopped")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

    logger.info("Bot shutdown completed")


async def main():
    """Главная функция приложения."""
    global bot, dp

    # Настраиваем логирование
    setup_logging()
    logger.info("🚀 Starting Crypto Bot application", version=APP_VERSION)

    # Валидируем конфигурацию
    validate_application_config()

    # Настраиваем обработчики сигналов
    setup_signal_handlers()

    try:
        # Создаем экземпляры бота и диспетчера СНАЧАЛА
        bot = await create_bot()
        dp = await setup_dispatcher()

        # Инициализируем сервисы (после создания бота)
        await init_services()

        # Создаем данные по умолчанию
        await create_default_data()

        # Выполняем действия при запуске
        await on_startup()

        # Запускаем polling
        logger.info("Starting bot polling...")
        await dp.start_polling(
            bot,
            skip_updates=True,  # Пропускаем накопившиеся обновления
            allowed_updates=["message", "callback_query"],  # Обрабатываем только нужные типы
        )

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error in main function", error=str(e), exc_info=True)
        raise
    finally:
        # Корректное завершение
        await on_shutdown()


def run_bot():
    """Запустить бота (синхронная функция для вызова извне)."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_bot()