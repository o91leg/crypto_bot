"""
Путь: src/config/binance_config.py
Описание: Конфигурация для работы с Binance API
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Dict
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict


class BinanceConfig(BaseSettings):
    """Конфигурация для Binance API."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'  # Игнорируем лишние поля
    )

    # URL-адреса API
    websocket_url: str = Field(
        default="wss://stream.binance.com:9443/ws",
        env="BINANCE_WEBSOCKET_URL"
    )
    rest_api_url: str = Field(
        default="https://api.binance.com",
        env="BINANCE_REST_URL"
    )

    # Настройки WebSocket соединения
    ping_interval: int = Field(default=20, env="BINANCE_PING_INTERVAL")
    ping_timeout: int = Field(default=10, env="BINANCE_PING_TIMEOUT")
    close_timeout: int = Field(default=10, env="BINANCE_CLOSE_TIMEOUT")

    # Настройки переподключения
    max_reconnect_attempts: int = Field(default=5, env="BINANCE_MAX_RECONNECT_ATTEMPTS")
    reconnect_delay: int = Field(default=5, env="BINANCE_RECONNECT_DELAY")
    backoff_multiplier: float = Field(default=2.0, env="BINANCE_BACKOFF_MULTIPLIER")
    max_reconnect_delay: int = Field(default=300, env="BINANCE_MAX_RECONNECT_DELAY")

    # Настройки REST API
    request_timeout: int = Field(default=30, env="BINANCE_REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, env="BINANCE_MAX_RETRIES")
    retry_delay: int = Field(default=1, env="BINANCE_RETRY_DELAY")
    max_connections: int = Field(default=100, env="BINANCE_MAX_CONNECTIONS")
    max_connections_per_host: int = Field(default=50, env="BINANCE_MAX_CONNECTIONS_PER_HOST")
    # Лимиты запросов
    requests_per_minute: int = Field(default=1200, env="BINANCE_REQUESTS_PER_MINUTE")
    orders_per_second: int = Field(default=10, env="BINANCE_ORDERS_PER_SECOND")

    # Поддерживаемые таймфреймы
    supported_timeframes: List[str] = Field(
        default=["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"],
        env="BINANCE_SUPPORTED_TIMEFRAMES"
    )

    # Таймфреймы по умолчанию для бота
    default_bot_timeframes: List[str] = Field(
        default=["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1w"],
        env="BINANCE_DEFAULT_BOT_TIMEFRAMES"
    )

    # Маппинг таймфреймов Binance к человекочитаемым названиям
    timeframe_display_names: Dict[str, str] = Field(
        default={
            "1m": "1 минута",
            "3m": "3 минуты",
            "5m": "5 минут",
            "15m": "15 минут",
            "30m": "30 минут",
            "1h": "1 час",
            "2h": "2 часа",
            "4h": "4 часа",
            "6h": "6 часов",
            "8h": "8 часов",
            "12h": "12 часов",
            "1d": "1 день",
            "3d": "3 дня",
            "1w": "1 неделя",
            "1M": "1 месяц"
        }
    )

    # Настройки исторических данных
    max_candles_per_request: int = Field(default=1000, env="BINANCE_MAX_CANDLES")
    historical_data_limit: int = Field(default=500, env="BINANCE_HISTORICAL_LIMIT")

    # Настройки валидации пар
    min_symbol_length: int = Field(default=6, env="BINANCE_MIN_SYMBOL_LENGTH")
    max_symbol_length: int = Field(default=12, env="BINANCE_MAX_SYMBOL_LENGTH")
    default_quote_asset: str = Field(default="USDT", env="BINANCE_DEFAULT_QUOTE")

    @field_validator("supported_timeframes", mode="before")
    @classmethod
    def validate_timeframes(cls, v):
        """Валидация поддерживаемых таймфреймов."""
        if isinstance(v, str):
            return [tf.strip() for tf in v.split(",")]
        return v

    @field_validator("default_bot_timeframes", mode="before")
    @classmethod
    def validate_bot_timeframes(cls, v, info):
        """Валидация таймфреймов бота."""
        if isinstance(v, str):
            bot_timeframes = [tf.strip() for tf in v.split(",")]
        else:
            bot_timeframes = v

        # Получаем supported_timeframes из данных валидации
        supported = getattr(info.data, 'supported_timeframes', None) or [
            "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
        ]

        for tf in bot_timeframes:
            if tf not in supported:
                raise ValueError(f"Timeframe {tf} not in supported timeframes")

        return bot_timeframes


# Глобальный экземпляр конфигурации
binance_config = BinanceConfig()


def get_binance_config() -> BinanceConfig:
    """
    Получить конфигурацию Binance API.

    Returns:
        BinanceConfig: Конфигурация Binance API
    """
    return binance_config


def get_websocket_url() -> str:
    """
    Получить URL для WebSocket подключения.

    Returns:
        str: WebSocket URL
    """
    return binance_config.websocket_url


def get_rest_api_url() -> str:
    """
    Получить URL для REST API.

    Returns:
        str: REST API URL
    """
    return binance_config.rest_api_url


def is_timeframe_supported(timeframe: str) -> bool:
    """
    Проверить, поддерживается ли таймфрейм.

    Args:
        timeframe: Таймфрейм для проверки

    Returns:
        bool: True если таймфрейм поддерживается
    """
    return timeframe in binance_config.supported_timeframes


def get_timeframe_display_name(timeframe: str) -> str:
    """
    Получить человекочитаемое название таймфрейма.

    Args:
        timeframe: Таймфрейм

    Returns:
        str: Человекочитаемое название
    """
    return binance_config.timeframe_display_names.get(timeframe, timeframe)


def get_supported_timeframes() -> List[str]:
    """
    Получить список поддерживаемых таймфреймов.

    Returns:
        List[str]: Список таймфреймов
    """
    return binance_config.supported_timeframes.copy()


def get_default_bot_timeframes() -> List[str]:
    """
    Получить список таймфреймов по умолчанию для бота.

    Returns:
        List[str]: Список таймфреймов по умолчанию
    """
    return binance_config.default_bot_timeframes.copy()


def validate_symbol_format(symbol: str) -> bool:
    """
    Проверить формат символа торговой пары.

    Args:
        symbol: Символ для проверки

    Returns:
        bool: True если формат корректен
    """
    if not symbol or not isinstance(symbol, str):
        return False

    symbol_len = len(symbol.strip())
    return (binance_config.min_symbol_length <= symbol_len <= binance_config.max_symbol_length)


def get_connection_settings() -> Dict[str, int]:
    """
    Получить настройки соединения WebSocket.

    Returns:
        Dict[str, int]: Настройки соединения
    """
    return {
        "ping_interval": binance_config.ping_interval,
        "ping_timeout": binance_config.ping_timeout,
        "close_timeout": binance_config.close_timeout,
        "max_reconnect_attempts": binance_config.max_reconnect_attempts,
        "reconnect_delay": binance_config.reconnect_delay,
        "max_reconnect_delay": binance_config.max_reconnect_delay
    }