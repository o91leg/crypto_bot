"""
Путь: src/config/bot_config.py
Описание: Конфигурация Telegram бота
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from dotenv import load_dotenv

# Загружаем .env файл вручную
load_dotenv()


class BotConfig(BaseSettings):
    """Конфигурация Telegram бота."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    # Основные настройки бота
    bot_token: str = Field(default=os.getenv("BOT_TOKEN", ""), env="BOT_TOKEN")
    debug: bool = Field(default=os.getenv("DEBUG", "False").lower() == "true", env="DEBUG")
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"), env="LOG_LEVEL")

    # Настройки подключений
    max_connections: int = Field(default=100, env="MAX_CONNECTIONS")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")

    # Настройки уведомлений
    notification_rate_limit: int = Field(default=10, env="NOTIFICATION_RATE_LIMIT")
    signal_check_interval: int = Field(default=60, env="SIGNAL_CHECK_INTERVAL")

    # Дефолтные настройки пользователей (НЕ из ENV)
    default_timeframes: List[str] = Field(
        default=["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1w"],
        description="Дефолтные таймфреймы для новых пользователей"
    )
    default_pair: str = Field(default="BTCUSDT", env="DEFAULT_PAIR")

    # Настройки индикаторов
    rsi_period: int = Field(default=14, env="DEFAULT_RSI_PERIOD")
    ema_periods: List[int] = Field(
        default=[20, 50, 100, 200],
        description="Периоды EMA для расчета"
    )

    # RSI зоны для сигналов
    rsi_oversold_strong: float = Field(default=20.0)
    rsi_oversold_medium: float = Field(default=25.0)
    rsi_oversold_normal: float = Field(default=30.0)
    rsi_overbought_normal: float = Field(default=70.0)
    rsi_overbought_medium: float = Field(default=75.0)
    rsi_overbought_strong: float = Field(default=80.0)

    # Настройки повторных сигналов
    signal_repeat_interval: int = Field(default=120)  # 2 минуты в секундах


# Глобальный экземпляр конфигурации
bot_config = BotConfig()


def get_bot_config() -> BotConfig:
    """
    Получить конфигурацию бота.

    Returns:
        BotConfig: Экземпляр конфигурации бота
    """
    return bot_config


def is_debug_mode() -> bool:
    """
    Проверить, включен ли режим отладки.

    Returns:
        bool: True если включен debug режим
    """
    return bot_config.debug


def get_rsi_zones() -> dict:
    """
    Получить зоны RSI для генерации сигналов.

    Returns:
        dict: Словарь с зонами RSI
    """
    return {
        "oversold": {
            "strong": bot_config.rsi_oversold_strong,
            "medium": bot_config.rsi_oversold_medium,
            "normal": bot_config.rsi_oversold_normal,
        },
        "overbought": {
            "normal": bot_config.rsi_overbought_normal,
            "medium": bot_config.rsi_overbought_medium,
            "strong": bot_config.rsi_overbought_strong,
        }
    }


def get_ema_periods() -> List[int]:
    """
    Получить периоды EMA для расчета.

    Returns:
        List[int]: Список периодов EMA
    """
    return bot_config.ema_periods


def get_default_timeframes() -> List[str]:
    """
    Получить дефолтные таймфреймы для новых пользователей.

    Returns:
        List[str]: Список таймфреймов
    """
    return bot_config.default_timeframes


def get_rsi_period() -> int:
    """
    Получить период RSI по умолчанию.

    Returns:
        int: Период RSI
    """
    return bot_config.rsi_period


def get_signal_check_interval() -> int:
    """
    Получить интервал проверки сигналов в секундах.

    Returns:
        int: Интервал в секундах
    """
    return bot_config.signal_check_interval


def get_notification_rate_limit() -> int:
    """
    Получить лимит уведомлений в минуту.

    Returns:
        int: Лимит уведомлений
    """
    return bot_config.notification_rate_limit


def get_default_pair() -> str:
    """
    Получить дефолтную торговую пару.

    Returns:
        str: Символ торговой пары
    """
    return bot_config.default_pair


def validate_config() -> bool:
    """
    Валидировать конфигурацию бота.

    Returns:
        bool: True если конфигурация валидна

    Raises:
        ValueError: При невалидной конфигурации
    """
    if not bot_config.bot_token:
        raise ValueError("Bot token is required")

    if not bot_config.default_timeframes:
        raise ValueError("Default timeframes must be specified")

    if bot_config.rsi_period <= 0:
        raise ValueError("RSI period must be positive")

    if not bot_config.ema_periods or min(bot_config.ema_periods) <= 0:
        raise ValueError("EMA periods must be positive")

    # Проверка RSI зон
    if not (0 < bot_config.rsi_oversold_strong < bot_config.rsi_oversold_medium <
            bot_config.rsi_oversold_normal < bot_config.rsi_overbought_normal <
            bot_config.rsi_overbought_medium < bot_config.rsi_overbought_strong < 100):
        raise ValueError("RSI zones must be in correct order")

    return True