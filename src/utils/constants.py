"""
Путь: src/utils/constants.py
Описание: Константы приложения для централизованного управления значениями
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Dict, List, Tuple

# ==================== ОБЩИЕ КОНСТАНТЫ ====================

# Версия приложения
APP_VERSION = "1.0.0"
APP_NAME = "Crypto Bot"
API_VERSION = "v1"
SUPPORTED_EXCHANGES = ["binance"]

# Максимальные размеры
MAX_MESSAGE_LENGTH = 4096  # Максимальная длина сообщения в Telegram
MAX_USERNAME_LENGTH = 255
MAX_PAIR_SYMBOL_LENGTH = 20
MAX_TIMEFRAME_LENGTH = 5

# ==================== ИНДИКАТОРЫ ====================

# RSI настройки
DEFAULT_RSI_PERIOD = 14
RSI_MIN_VALUE = 0.0
RSI_MAX_VALUE = 100.0

# RSI зоны
RSI_OVERSOLD_STRONG = 20.0
RSI_OVERSOLD_MEDIUM = 25.0
RSI_OVERSOLD_NORMAL = 30.0
RSI_OVERBOUGHT_NORMAL = 70.0
RSI_OVERBOUGHT_MEDIUM = 75.0
RSI_OVERBOUGHT_STRONG = 80.0

# EMA настройки
DEFAULT_EMA_PERIODS = [20, 50, 100, 200]
EMA_MIN_PERIOD = 2
EMA_MAX_PERIOD = 1000

# ==================== ТАЙМФРЕЙМЫ ====================

# Поддерживаемые таймфреймы Binance
BINANCE_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M"
]

# Таймфреймы бота по умолчанию
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1w"]

# Маппинг таймфреймов в миллисекунды
TIMEFRAME_TO_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "3d": 3 * 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
    "1M": 30 * 24 * 60 * 60 * 1000,  # Приблизительно
}

# Человекочитаемые названия таймфреймов
TIMEFRAME_NAMES = {
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

# ==================== СИГНАЛЫ ====================

# Типы сигналов
SIGNAL_TYPES = {
    "RSI_OVERSOLD_STRONG": "rsi_oversold_strong",
    "RSI_OVERSOLD_MEDIUM": "rsi_oversold_medium",
    "RSI_OVERSOLD_NORMAL": "rsi_oversold_normal",
    "RSI_OVERBOUGHT_NORMAL": "rsi_overbought_normal",
    "RSI_OVERBOUGHT_MEDIUM": "rsi_overbought_medium",
    "RSI_OVERBOUGHT_STRONG": "rsi_overbought_strong",
    "EMA_CROSS_UP": "ema_cross_up",
    "EMA_CROSS_DOWN": "ema_cross_down",
    "VOLUME_SPIKE": "volume_spike",
    "TREND_CHANGE": "trend_change"
}

# Интервалы повторения сигналов (в секундах)
SIGNAL_REPEAT_INTERVALS = {
    "rsi_oversold_strong": 60,    # 1 минута
    "rsi_oversold_medium": 120,   # 2 минуты
    "rsi_oversold_normal": 180,   # 3 минуты
    "rsi_overbought_normal": 180, # 3 минуты
    "rsi_overbought_medium": 120, # 2 минуты
    "rsi_overbought_strong": 60,  # 1 минута
    "ema_cross_up": 300,          # 5 минут
    "ema_cross_down": 300,        # 5 минут
    "volume_spike": 600,          # 10 минут
}

# Эмодзи для сигналов
SIGNAL_EMOJIS = {
    "rsi_oversold_strong": "🔴",
    "rsi_oversold_medium": "🟠",
    "rsi_oversold_normal": "🟡",
    "rsi_overbought_normal": "🟡",
    "rsi_overbought_medium": "🟠",
    "rsi_overbought_strong": "🔴",
    "ema_cross_up": "🚀",
    "ema_cross_down": "💥",
    "volume_spike": "🔥",
    "default": "📊"
}

# ==================== BINANCE API ====================

# URL эндпоинты
BINANCE_REST_API_URL = "https://api.binance.com"
BINANCE_WEBSOCKET_URL = "wss://stream.binance.com:9443/ws"

# Лимиты API
BINANCE_WEIGHT_LIMIT = 1200
BINANCE_ORDER_LIMIT = 10
BINANCE_MAX_CONNECTIONS = 5

# Типичные котируемые валюты
QUOTE_ASSETS = ["USDT", "BTC", "ETH", "BNB", "BUSD", "USDC"]

# Минимальная длина символа
MIN_SYMBOL_LENGTH = 6
MAX_SYMBOL_LENGTH = 12

# ==================== УВЕДОМЛЕНИЯ ====================

# Лимиты уведомлений
MAX_NOTIFICATIONS_PER_MINUTE = 20
MAX_NOTIFICATIONS_PER_HOUR = 100
NOTIFICATION_RATE_LIMIT_WINDOW = 60  # секунд

# Приоритеты уведомлений
NOTIFICATION_PRIORITIES = {
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3
}

# ==================== БАЗА ДАННЫХ ====================

# Лимиты для запросов
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
MAX_CANDLES_PER_REQUEST = 1000

# TTL для кеша (в секундах)
CACHE_TTL = {
    "candles": 86400,        # 1 день
    "indicators": 3600,      # 1 час
    "user_data": 1800,       # 30 минут
    "pairs": 21600,          # 6 часов
    "signals": 7200,         # 2 часа
}

# ==================== ФОРМАТИРОВАНИЕ ====================

# Форматы отображения
PRICE_DECIMAL_PLACES = 8
PERCENTAGE_DECIMAL_PLACES = 2
VOLUME_DECIMAL_PLACES = 2

# Символы валют
CURRENCY_SYMBOLS = {
    "USD": "$",
    "USDT": "$",
    "USDC": "$",
    "BTC": "₿",
    "ETH": "Ξ",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥"
}

# ==================== ЭМОДЗИ И СИМВОЛЫ ====================

# Общие эмодзи
EMOJI = {
    "rocket": "🚀",
    "chart": "📊",
    "bell": "🔔",
    "warning": "⚠️",
    "error": "❌",
    "success": "✅",
    "info": "ℹ️",
    "loading": "⏳",
    "money": "💰",
    "up": "📈",
    "down": "📉",
    "fire": "🔥",
    "target": "🎯",
    "gear": "⚙️",
    "home": "🏠",
    "back": "⬅️",
    "plus": "➕",
    "minus": "➖",
    "question": "❓"
}

# Трендовые эмодзи
TREND_EMOJIS = {
    "bullish": "🐂",
    "bearish": "🐻",
    "sideways": "➡️",
    "strong_up": "🚀",
    "strong_down": "💥"
}

# ==================== СООБЩЕНИЯ ====================

# Шаблоны сообщений
MESSAGE_TEMPLATES = {
    "welcome_new": "🚀 Добро пожаловать в {app_name}!",
    "welcome_back": "👋 С возвращением!",
    "pair_added": "✅ Пара {pair} добавлена в отслеживание",
    "pair_removed": "❌ Пара {pair} удалена из отслеживания",
    "notifications_enabled": "🔔 Уведомления включены",
    "notifications_disabled": "🔕 Уведомления отключены",
    "error_occurred": "❌ Произошла ошибка: {error}",
    "loading": "⏳ Загрузка..."
}

# ==================== РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ ====================

# Паттерны для валидации
PATTERNS = {
    "symbol": r"^[A-Z]{3,12}$",
    "timeframe": r"^(1|3|5|15|30)m|^(1|2|4|6|8|12)h|^(1|3)d|^1w|^1M$",
    "price": r"^\d+\.?\d*$",
    "percentage": r"^-?\d+\.?\d*%?$"
}

# ==================== ПУТИ И ФАЙЛЫ ====================

# Пути к директориям
LOGS_DIR = "logs"
DATA_DIR = "data"
TEMP_DIR = "temp"
STATIC_DIR = "static"

# Имена файлов
LOG_FILE = "crypto_bot.log"
ERROR_LOG_FILE = "errors.log"
ACCESS_LOG_FILE = "access.log"

# ==================== ФУНКЦИИ-ПОМОЩНИКИ ====================

def get_timeframe_ms(timeframe: str) -> int:
    """
    Получить количество миллисекунд для таймфрейма.

    Args:
        timeframe: Таймфрейм (например, '1h')

    Returns:
        int: Количество миллисекунд
    """
    return TIMEFRAME_TO_MS.get(timeframe, 0)


def get_signal_emoji(signal_type: str) -> str:
    """
    Получить эмодзи для типа сигнала.

    Args:
        signal_type: Тип сигнала

    Returns:
        str: Эмодзи
    """
    return SIGNAL_EMOJIS.get(signal_type, "📊")


def get_currency_symbol(currency: str) -> str:
    """
    Получить символ валюты.

    Args:
        currency: Код валюты

    Returns:
        str: Символ валюты
    """
    return CURRENCY_SYMBOLS.get(currency.upper(), currency)


def is_valid_timeframe(timeframe: str) -> bool:
    """
    Проверить валидность таймфрейма.

    Args:
        timeframe: Таймфрейм для проверки

    Returns:
        bool: True если таймфрейм валиден
    """
    return timeframe in BINANCE_TIMEFRAMES


def get_repeat_interval(signal_type: str) -> int:
    """
    Получить интервал повторения для типа сигнала.

    Args:
        signal_type: Тип сигнала

    Returns:
        int: Интервал в секундах
    """
    return SIGNAL_REPEAT_INTERVALS.get(signal_type, 300)  # По умолчанию 5 минут