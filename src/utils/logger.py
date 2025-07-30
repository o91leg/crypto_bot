"""
Путь: src/utils/logger.py
Описание: Настройка системы логирования для приложения
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import structlog
from structlog.stdlib import LoggerFactory, add_logger_name, add_log_level

from config.bot_config import get_bot_config, is_debug_mode


def setup_logging(
    log_level: Optional[str] = None,
    json_logs: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    Настроить систему логирования.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        json_logs: Использовать JSON формат для логов
        log_file: Путь к файлу для записи логов
    """
    # Получаем конфигурацию
    config = get_bot_config()

    # Определяем уровень логирования
    if log_level is None:
        log_level = config.log_level

    # Преобразуем строковый уровень в числовой
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Настраиваем стандартный logging
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        stream=sys.stdout
    )

    # Подавляем слишком подробные логи внешних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # Настраиваем процессоры для structlog
    processors = [
        # Добавляем имя логгера
        add_logger_name,
        # Добавляем уровень лога
        add_log_level,
        # Добавляем timestamp
        structlog.processors.TimeStamper(fmt="ISO"),
        # Добавляем информацию о стеке при ошибках
        structlog.processors.StackInfoRenderer(),
        # Добавляем информацию об исключениях
        structlog.dev.set_exc_info,
    ]

    # Выбираем финальный процессор в зависимости от формата
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Красивый консольный вывод для разработки
        if is_debug_mode():
            processors.append(
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.plain_traceback
                )
            )
        else:
            processors.append(
                structlog.processors.KeyValueRenderer(
                    key_order=["timestamp", "level", "logger", "event"]
                )
            )

    # Настраиваем structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True
    )

    # Настраиваем файловое логирование если нужно
    if log_file:
        setup_file_logging(log_file, numeric_level)

    # Получаем logger и записываем сообщение о запуске
    logger = structlog.get_logger("app.startup")
    logger.info(
        "Logging configured",
        level=log_level,
        json_format=json_logs,
        file_logging=bool(log_file),
        debug_mode=is_debug_mode()
    )


def setup_file_logging(log_file: str, level: int) -> None:
    """
    Настроить логирование в файл.

    Args:
        log_file: Путь к файлу логов
        level: Уровень логирования
    """
    # Создаем форматтер для файлов
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Создаем файловый handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

    # Добавляем handler к root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Получить logger с заданным именем.

    Args:
        name: Имя логгера

    Returns:
        structlog.BoundLogger: Настроенный logger
    """
    return structlog.get_logger(name)


def log_function_call(func_name: str, **kwargs) -> None:
    """
    Залогировать вызов функции.

    Args:
        func_name: Имя функции
        **kwargs: Дополнительные параметры для логирования
    """
    logger = structlog.get_logger("function_calls")
    logger.debug("Function called", function=func_name, **kwargs)


def log_user_action(user_id: int, action: str, **kwargs) -> None:
    """
    Залогировать действие пользователя.

    Args:
        user_id: ID пользователя
        action: Действие пользователя
        **kwargs: Дополнительные параметры
    """
    logger = structlog.get_logger("user_actions")
    logger.info("User action", user_id=user_id, action=action, **kwargs)


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """
    Залогировать ошибку с контекстом.

    Args:
        error: Исключение
        context: Дополнительный контекст
    """
    logger = structlog.get_logger("errors")

    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        error_data.update(context)

    logger.error("Error occurred", **error_data, exc_info=True)


def log_database_operation(operation: str, table: str, **kwargs) -> None:
    """
    Залогировать операцию с базой данных.

    Args:
        operation: Тип операции (SELECT, INSERT, UPDATE, DELETE)
        table: Имя таблицы
        **kwargs: Дополнительные параметры
    """
    logger = structlog.get_logger("database")
    logger.debug("Database operation", operation=operation, table=table, **kwargs)


def log_websocket_event(event_type: str, symbol: str = None, **kwargs) -> None:
    """
    Залогировать событие WebSocket.

    Args:
        event_type: Тип события
        symbol: Символ торговой пары
        **kwargs: Дополнительные параметры
    """
    logger = structlog.get_logger("websocket")
    logger.debug("WebSocket event", event=event_type, symbol=symbol, **kwargs)


def log_signal_generated(user_id: int, symbol: str, timeframe: str, signal_type: str, **kwargs) -> None:
    """
    Залогировать генерацию сигнала.

    Args:
        user_id: ID пользователя
        symbol: Символ пары
        timeframe: Таймфрейм
        signal_type: Тип сигнала
        **kwargs: Дополнительные параметры
    """
    logger = structlog.get_logger("signals")
    logger.info(
        "Signal generated",
        user_id=user_id,
        symbol=symbol,
        timeframe=timeframe,
        signal_type=signal_type,
        **kwargs
    )


def log_notification_sent(user_id: int, message_type: str, success: bool = True, **kwargs) -> None:
    """
    Залогировать отправку уведомления.

    Args:
        user_id: ID пользователя
        message_type: Тип сообщения
        success: Успешно ли отправлено
        **kwargs: Дополнительные параметры
    """
    logger = structlog.get_logger("notifications")

    if success:
        logger.info("Notification sent", user_id=user_id, type=message_type, **kwargs)
    else:
        logger.warning("Notification failed", user_id=user_id, type=message_type, **kwargs)


class LoggerMixin:
    """Миксин для добавления логирования в классы."""

    @property
    def logger(self) -> structlog.BoundLogger:
        """
        Получить logger для класса.

        Returns:
            structlog.BoundLogger: Logger привязанный к классу
        """
        return structlog.get_logger(self.__class__.__module__ + "." + self.__class__.__name__)


def configure_aiogram_logging():
    """Настроить логирование для aiogram."""
    # Устанавливаем уровень для aiogram логгеров
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(logging.INFO)

    # Создаем фильтр для подавления избыточных сообщений
    class AiogramFilter(logging.Filter):
        def filter(self, record):
            # Подавляем слишком подробные сообщения
            if "Received update" in record.getMessage():
                return False
            if "Process update" in record.getMessage():
                return False
            return True

    aiogram_logger.addFilter(AiogramFilter())


def setup_production_logging():
    """Настроить логирование для продакшн среды."""
    setup_logging(
        log_level="INFO",
        json_logs=True,
        log_file="/app/logs/crypto_bot.log"
    )


def setup_development_logging():
    """Настроить логирование для разработки."""
    setup_logging(
        log_level="DEBUG",
        json_logs=False
    )


# Декораторы для автоматического логирования
def log_async_function(func):
    """
    Декоратор для логирования асинхронных функций.

    Args:
        func: Функция для декорирования

    Returns:
        Декорированная функция
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = structlog.get_logger(func.__module__)

        logger.debug(
            "Function start",
            function=func.__name__,
            args_count=len(args),
            kwargs_count=len(kwargs)
        )

        try:
            start_time = datetime.now()
            result = await func(*args, **kwargs)
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            logger.debug(
                "Function completed",
                function=func.__name__,
                duration_seconds=duration
            )

            return result

        except Exception as e:
            logger.error(
                "Function failed",
                function=func.__name__,
                error=str(e),
                exc_info=True
            )
            raise

    return wrapper