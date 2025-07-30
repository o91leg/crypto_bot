"""
Путь: src/utils/exceptions.py
Описание: Кастомные исключения для приложения
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Optional, Dict, Any


class CryptoBotError(Exception):
    """Базовое исключение для всех ошибок крипто-бота."""

    def __init__(
            self,
            message: str,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация базового исключения.

        Args:
            message: Сообщение об ошибке
            error_code: Код ошибки
            details: Дополнительные детали ошибки
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать исключение в словарь.

        Returns:
            Dict[str, Any]: Данные исключения
        """
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


# ==================== ОШИБКИ КОНФИГУРАЦИИ ====================

class ConfigurationError(CryptoBotError):
    """Ошибка конфигурации приложения."""
    pass


class MissingConfigError(ConfigurationError):
    """Отсутствует обязательный параметр конфигурации."""

    def __init__(self, config_key: str):
        super().__init__(
            f"Missing required configuration: {config_key}",
            error_code="MISSING_CONFIG",
            details={"config_key": config_key}
        )


class InvalidConfigError(ConfigurationError):
    """Неверное значение параметра конфигурации."""

    def __init__(self, config_key: str, value: Any, expected: str):
        super().__init__(
            f"Invalid configuration value for {config_key}: {value}. Expected: {expected}",
            error_code="INVALID_CONFIG",
            details={"config_key": config_key, "value": value, "expected": expected}
        )


# ==================== ОШИБКИ БАЗЫ ДАННЫХ ====================

class DatabaseError(CryptoBotError):
    """Базовая ошибка базы данных."""
    pass


class ConnectionError(DatabaseError):
    """Ошибка подключения к базе данных."""

    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message, error_code="DB_CONNECTION_ERROR")


class QueryError(DatabaseError):
    """Ошибка выполнения запроса к базе данных."""

    def __init__(self, query: str, original_error: str):
        super().__init__(
            f"Query execution failed: {original_error}",
            error_code="DB_QUERY_ERROR",
            details={"query": query, "original_error": original_error}
        )


class RecordNotFoundError(DatabaseError):
    """Запись не найдена в базе данных."""

    def __init__(self, model: str, identifier: Any):
        super().__init__(
            f"{model} with identifier {identifier} not found",
            error_code="RECORD_NOT_FOUND",
            details={"model": model, "identifier": identifier}
        )


class RecordAlreadyExistsError(DatabaseError):
    """Запись уже существует в базе данных."""

    def __init__(self, model: str, identifier: Any):
        super().__init__(
            f"{model} with identifier {identifier} already exists",
            error_code="RECORD_ALREADY_EXISTS",
            details={"model": model, "identifier": identifier}
        )


# ==================== ОШИБКИ ПОЛЬЗОВАТЕЛЕЙ ====================

class UserError(CryptoBotError):
    """Базовая ошибка пользователя."""
    pass


class UserNotFoundError(UserError):
    """Пользователь не найден."""

    def __init__(self, user_id: int):
        super().__init__(
            f"User {user_id} not found",
            error_code="USER_NOT_FOUND",
            details={"user_id": user_id}
        )


class UserBlockedError(UserError):
    """Пользователь заблокирован."""

    def __init__(self, user_id: int):
        super().__init__(
            f"User {user_id} is blocked",
            error_code="USER_BLOCKED",
            details={"user_id": user_id}
        )


class UserInactiveError(UserError):
    """Пользователь неактивен."""

    def __init__(self, user_id: int):
        super().__init__(
            f"User {user_id} is inactive",
            error_code="USER_INACTIVE",
            details={"user_id": user_id}
        )


# ==================== ОШИБКИ ТОРГОВЫХ ПАР ====================

class PairError(CryptoBotError):
    """Базовая ошибка торговых пар."""
    pass


class PairNotFoundError(PairError):
    """Торговая пара не найдена."""

    def __init__(self, symbol: str):
        super().__init__(
            f"Trading pair {symbol} not found",
            error_code="PAIR_NOT_FOUND",
            details={"symbol": symbol}
        )


class InvalidPairError(PairError):
    """Неверный формат торговой пары."""

    def __init__(self, symbol: str, reason: str = "Invalid format"):
        super().__init__(
            f"Invalid trading pair {symbol}: {reason}",
            error_code="INVALID_PAIR",
            details={"symbol": symbol, "reason": reason}
        )


class PairAlreadyExistsError(PairError):
    """Торговая пара уже добавлена."""

    def __init__(self, symbol: str, user_id: int):
        super().__init__(
            f"Trading pair {symbol} already exists for user {user_id}",
            error_code="PAIR_ALREADY_EXISTS",
            details={"symbol": symbol, "user_id": user_id}
        )


# ==================== ОШИБКИ BINANCE API ====================

class BinanceAPIError(CryptoBotError):
    """Базовая ошибка Binance API."""
    pass


class BinanceConnectionError(BinanceAPIError):
    """Ошибка подключения к Binance API."""

    def __init__(self, message: str = "Failed to connect to Binance API"):
        super().__init__(message, error_code="BINANCE_CONNECTION_ERROR")


class BinanceRateLimitError(BinanceAPIError):
    """Превышен лимит запросов к Binance API."""

    def __init__(self, retry_after: Optional[int] = None):
        message = "Binance API rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"

        super().__init__(
            message,
            error_code="BINANCE_RATE_LIMIT",
            details={"retry_after": retry_after}
        )


class BinanceDataError(BinanceAPIError):
    """Ошибка данных от Binance API."""

    def __init__(self, symbol: str, timeframe: str, message: str):
        super().__init__(
            f"Data error for {symbol} {timeframe}: {message}",
            error_code="BINANCE_DATA_ERROR",
            details={"symbol": symbol, "timeframe": timeframe}
        )


# ==================== ОШИБКИ WEBSOCKET ====================

class WebSocketError(CryptoBotError):
    """Базовая ошибка WebSocket."""
    pass


class WebSocketConnectionError(WebSocketError):
    """Ошибка подключения WebSocket."""

    def __init__(self, url: str, reason: str = "Connection failed"):
        super().__init__(
            f"WebSocket connection to {url} failed: {reason}",
            error_code="WEBSOCKET_CONNECTION_ERROR",
            details={"url": url, "reason": reason}
        )


class WebSocketReconnectError(WebSocketError):
    """Ошибка переподключения WebSocket."""

    def __init__(self, attempts: int, max_attempts: int):
        super().__init__(
            f"WebSocket reconnection failed after {attempts}/{max_attempts} attempts",
            error_code="WEBSOCKET_RECONNECT_ERROR",
            details={"attempts": attempts, "max_attempts": max_attempts}
        )


# ==================== ОШИБКИ ИНДИКАТОРОВ ====================

class IndicatorError(CryptoBotError):
    """Базовая ошибка индикаторов."""
    pass


class InsufficientDataError(IndicatorError):
    """Недостаточно данных для расчета индикатора."""

    def __init__(self, indicator: str, required: int, provided: int):
        super().__init__(
            f"Insufficient data for {indicator}: required {required}, provided {provided}",
            error_code="INSUFFICIENT_DATA",
            details={"indicator": indicator, "required": required, "provided": provided}
        )


class InvalidIndicatorParameterError(IndicatorError):
    """Неверный параметр индикатора."""

    def __init__(self, indicator: str, parameter: str, value: Any, reason: str):
        super().__init__(
            f"Invalid parameter {parameter}={value} for {indicator}: {reason}",
            error_code="INVALID_INDICATOR_PARAMETER",
            details={"indicator": indicator, "parameter": parameter, "value": value, "reason": reason}
        )


# ==================== ОШИБКИ УВЕДОМЛЕНИЙ ====================

class NotificationError(CryptoBotError):
    """Базовая ошибка уведомлений."""
    pass


class NotificationSendError(NotificationError):
    """Ошибка отправки уведомления."""

    def __init__(self, user_id: int, message: str, reason: str):
        super().__init__(
            f"Failed to send notification to user {user_id}: {reason}",
            error_code="NOTIFICATION_SEND_ERROR",
            details={"user_id": user_id, "message": message, "reason": reason}
        )


class NotificationRateLimitError(NotificationError):
    """Превышен лимит уведомлений."""

    def __init__(self, user_id: int, limit: int, window: int):
        super().__init__(
            f"Notification rate limit exceeded for user {user_id}: {limit} per {window} seconds",
            error_code="NOTIFICATION_RATE_LIMIT",
            details={"user_id": user_id, "limit": limit, "window": window}
        )


# ==================== ОШИБКИ ВАЛИДАЦИИ ====================

class ValidationError(CryptoBotError):
    """Базовая ошибка валидации."""
    pass


class InvalidTimeframeError(ValidationError):
    """Неверный таймфрейм."""

    def __init__(self, timeframe: str):
        super().__init__(
            f"Invalid timeframe: {timeframe}",
            error_code="INVALID_TIMEFRAME",
            details={"timeframe": timeframe}
        )


class InvalidPriceError(ValidationError):
    """Неверный формат цены."""

    def __init__(self, price: str):
        super().__init__(
            f"Invalid price format: {price}",
            error_code="INVALID_PRICE",
            details={"price": price}
        )


class InvalidVolumeError(ValidationError):
    """Неверный формат объема."""

    def __init__(self, volume: str):
        super().__init__(
            f"Invalid volume format: {volume}",
            error_code="INVALID_VOLUME",
            details={"volume": volume}
        )


# ==================== ОШИБКИ КЕШИРОВАНИЯ ====================

class CacheError(CryptoBotError):
    """Базовая ошибка кеширования."""
    pass


class CacheConnectionError(CacheError):
    """Ошибка подключения к кешу."""

    def __init__(self, message: str = "Failed to connect to cache"):
        super().__init__(message, error_code="CACHE_CONNECTION_ERROR")


class CacheKeyError(CacheError):
    """Ошибка ключа кеша."""

    def __init__(self, key: str, operation: str):
        super().__init__(
            f"Cache key error for '{key}' during {operation}",
            error_code="CACHE_KEY_ERROR",
            details={"key": key, "operation": operation}
        )