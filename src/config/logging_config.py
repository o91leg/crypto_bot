"""
Путь: src/config/logging_config.py
Описание: Конфигурация системы логирования
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from enum import Enum


class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Форматы логирования."""
    CONSOLE = "console"
    JSON = "json"
    STRUCTURED = "structured"


class LoggingConfig(BaseSettings):
    """Конфигурация системы логирования."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    # Основные настройки
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    log_format: LogFormat = Field(default=LogFormat.CONSOLE, env="LOG_FORMAT")

    # Файловое логирование
    log_to_file: bool = Field(default=False, env="LOG_TO_FILE")
    log_file_path: str = Field(default="logs/crypto_bot.log", env="LOG_FILE_PATH")
    log_file_max_size: int = Field(default=10485760, env="LOG_FILE_MAX_SIZE")  # 10MB
    log_file_backup_count: int = Field(default=5, env="LOG_FILE_BACKUP_COUNT")

    # Консольное логирование
    log_to_console: bool = Field(default=True, env="LOG_TO_CONSOLE")
    console_colors: bool = Field(default=True, env="LOG_CONSOLE_COLORS")

    # Уровни для различных компонентов
    aiogram_log_level: LogLevel = Field(default=LogLevel.WARNING, env="AIOGRAM_LOG_LEVEL")
    sqlalchemy_log_level: LogLevel = Field(default=LogLevel.WARNING, env="SQLALCHEMY_LOG_LEVEL")
    websocket_log_level: LogLevel = Field(default=LogLevel.INFO, env="WEBSOCKET_LOG_LEVEL")
    database_log_level: LogLevel = Field(default=LogLevel.INFO, env="DATABASE_LOG_LEVEL")

    # Специальные настройки
    log_sql_queries: bool = Field(default=False, env="LOG_SQL_QUERIES")
    log_request_details: bool = Field(default=False, env="LOG_REQUEST_DETAILS")
    log_user_actions: bool = Field(default=True, env="LOG_USER_ACTIONS")
    log_signals: bool = Field(default=True, env="LOG_SIGNALS")

    # Фильтрация логов
    exclude_health_checks: bool = Field(default=True, env="EXCLUDE_HEALTH_CHECKS")
    exclude_ping_messages: bool = Field(default=True, env="EXCLUDE_PING_MESSAGES")

    # Контекстная информация
    include_user_context: bool = Field(default=True, env="INCLUDE_USER_CONTEXT")
    include_request_id: bool = Field(default=True, env="INCLUDE_REQUEST_ID")
    include_trace_id: bool = Field(default=False, env="INCLUDE_TRACE_ID")

    # Производительность
    async_logging: bool = Field(default=True, env="ASYNC_LOGGING")
    buffer_size: int = Field(default=1000, env="LOG_BUFFER_SIZE")
    flush_interval: int = Field(default=1, env="LOG_FLUSH_INTERVAL")


# Предустановленные конфигурации
DEVELOPMENT_CONFIG = {
    "log_level": LogLevel.DEBUG,
    "log_format": LogFormat.CONSOLE,
    "console_colors": True,
    "log_to_file": False,
    "log_sql_queries": True,
    "log_request_details": True,
    "exclude_health_checks": False,
    "exclude_ping_messages": False,
}

PRODUCTION_CONFIG = {
    "log_level": LogLevel.INFO,
    "log_format": LogFormat.JSON,
    "console_colors": False,
    "log_to_file": True,
    "log_sql_queries": False,
    "log_request_details": False,
    "exclude_health_checks": True,
    "exclude_ping_messages": True,
    "async_logging": True,
}

TESTING_CONFIG = {
    "log_level": LogLevel.WARNING,
    "log_format": LogFormat.CONSOLE,
    "console_colors": False,
    "log_to_file": False,
    "log_sql_queries": False,
    "log_request_details": False,
    "exclude_health_checks": True,
    "exclude_ping_messages": True,
}


# Глобальный экземпляр конфигурации
logging_config = LoggingConfig()


def get_logging_config() -> LoggingConfig:
    """
    Получить конфигурацию логирования.

    Returns:
        LoggingConfig: Конфигурация логирования
    """
    return logging_config


def get_logger_config_dict() -> Dict[str, Any]:
    """
    Получить конфигурацию в формате словаря для logging.dictConfig.

    Returns:
        Dict[str, Any]: Конфигурация для logging.dictConfig
    """
    config = get_logging_config()

    formatters = {
        "console": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        },
        "structured": {
            "format": "%(asctime)s | %(levelname)8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    }

    handlers = {}

    # Консольный handler
    if config.log_to_console:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": config.log_level.value,
            "formatter": config.log_format.value,
            "stream": "ext://sys.stdout"
        }

    # Файловый handler
    if config.log_to_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": config.log_level.value,
            "formatter": "json" if config.log_format == LogFormat.JSON else "structured",
            "filename": config.log_file_path,
            "maxBytes": config.log_file_max_size,
            "backupCount": config.log_file_backup_count,
            "encoding": "utf-8"
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            "": {  # Root logger
                "level": config.log_level.value,
                "handlers": list(handlers.keys())
            },
            "aiogram": {
                "level": config.aiogram_log_level.value,
                "handlers": list(handlers.keys()),
                "propagate": False
            },
            "sqlalchemy": {
                "level": config.sqlalchemy_log_level.value,
                "handlers": list(handlers.keys()),
                "propagate": False
            },
            "websocket": {
                "level": config.websocket_log_level.value,
                "handlers": list(handlers.keys()),
                "propagate": False
            },
            "database": {
                "level": config.database_log_level.value,
                "handlers": list(handlers.keys()),
                "propagate": False
            }
        }
    }


def apply_config_preset(preset_name: str) -> None:
    """
    Применить предустановленную конфигурацию.

    Args:
        preset_name: Название пресета (development, production, testing)
    """
    global logging_config

    presets = {
        "development": DEVELOPMENT_CONFIG,
        "production": PRODUCTION_CONFIG,
        "testing": TESTING_CONFIG,
    }

    if preset_name not in presets:
        raise ValueError(f"Unknown preset: {preset_name}")

    preset = presets[preset_name]
    for key, value in preset.items():
        setattr(logging_config, key, value)