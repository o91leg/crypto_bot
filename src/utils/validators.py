"""
Путь: src/utils/validators.py
Описание: Валидаторы входных данных для бота
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import re
from typing import Optional, List, Union, Any, Dict
from decimal import Decimal, InvalidOperation
from utils.constants import BINANCE_TIMEFRAMES, QUOTE_ASSETS, MIN_SYMBOL_LENGTH, MAX_SYMBOL_LENGTH


def validate_binance_kline_data_detailed(kline_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Детальная валидация данных kline от Binance.

    Args:
        kline_data: Данные kline от Binance

    Returns:
        tuple[bool, str]: (валидность, сообщение об ошибке)
    """
    try:
        if not isinstance(kline_data, dict):
            return False, "Kline data must be a dictionary"

        # Проверяем обязательные поля
        required_fields = [
            't',  # Open time
            'T',  # Close time
            's',  # Symbol
            'i',  # Interval
            'o',  # Open price
            'c',  # Close price
            'h',  # High price
            'l',  # Low price
            'v',  # Volume
            'q',  # Quote asset volume
            'n',  # Number of trades
            'V',  # Taker buy base asset volume
            'Q',  # Taker buy quote asset volume
            'x',  # Is this kline closed?
        ]

        for field in required_fields:
            if field not in kline_data:
                return False, f"Missing required field: {field}"

        # Проверяем типы данных и значения
        try:
            open_time = int(kline_data['t'])
            close_time = int(kline_data['T'])

            if open_time <= 0 or close_time <= 0:
                return False, "Invalid timestamp values"

            if open_time >= close_time:
                return False, "Open time must be less than close time"

        except (ValueError, TypeError):
            return False, "Invalid timestamp format"

        # Проверяем цены
        try:
            open_price = float(kline_data['o'])
            close_price = float(kline_data['c'])
            high_price = float(kline_data['h'])
            low_price = float(kline_data['l'])

            if any(price <= 0 for price in [open_price, close_price, high_price, low_price]):
                return False, "Prices must be positive"

            if high_price < max(open_price, close_price):
                return False, "High price inconsistency"

            if low_price > min(open_price, close_price):
                return False, "Low price inconsistency"

        except (ValueError, TypeError):
            return False, "Invalid price format"

        # Проверяем объемы
        try:
            volume = float(kline_data['v'])
            quote_volume = float(kline_data['q'])
            taker_buy_volume = float(kline_data['V'])
            taker_buy_quote_volume = float(kline_data['Q'])

            if any(vol < 0 for vol in [volume, quote_volume, taker_buy_volume, taker_buy_quote_volume]):
                return False, "Volumes cannot be negative"

            if taker_buy_volume > volume:
                return False, "Taker buy volume cannot exceed total volume"

        except (ValueError, TypeError):
            return False, "Invalid volume format"

        # Проверяем количество сделок
        try:
            trades_count = int(kline_data['n'])
            if trades_count < 0:
                return False, "Trades count cannot be negative"
        except (ValueError, TypeError):
            return False, "Invalid trades count format"

        # Проверяем символ и интервал
        symbol = str(kline_data['s']).strip()
        interval = str(kline_data['i']).strip()

        if not symbol or len(symbol) < 4:
            return False, "Invalid symbol"

        if not interval:
            return False, "Invalid interval"

        return True, "Valid kline data"

    except Exception as e:
        return False, f"Validation error: {str(e)}"


def validate_binance_kline_data(kline_data: Dict[str, Any]) -> bool:
    """
    Быстрая валидация данных kline от Binance (только bool результат).

    Args:
        kline_data: Данные kline от Binance

    Returns:
        bool: True если данные валидны
    """
    result, _ = validate_binance_kline_data_detailed(kline_data)
    return result


def validate_trading_pair_symbol(symbol: str) -> tuple[bool, Optional[str]]:
    """
    Валидировать символ торговой пары.

    Args:
        symbol: Символ для валидации (например, BTCUSDT)

    Returns:
        tuple: (is_valid, error_message)
    """
    if not symbol or not isinstance(symbol, str):
        return False, "Символ должен быть непустой строкой"

    symbol = symbol.upper().strip()

    # Проверка длины
    if len(symbol) < MIN_SYMBOL_LENGTH:
        return False, f"Символ слишком короткий (минимум {MIN_SYMBOL_LENGTH} символов)"

    if len(symbol) > MAX_SYMBOL_LENGTH:
        return False, f"Символ слишком длинный (максимум {MAX_SYMBOL_LENGTH} символов)"

    # Проверка на наличие только букв и цифр
    if not symbol.isalnum():
        return False, "Символ должен содержать только буквы и цифры"

    # Проверка наличия известной котируемой валюты
    has_valid_quote = False
    for quote in QUOTE_ASSETS:
        if symbol.endswith(quote):
            has_valid_quote = True
            base_asset = symbol[:-len(quote)]
            if len(base_asset) < 2:
                return False, f"Базовая валюта слишком короткая: {base_asset}"
            break

    if not has_valid_quote:
        return False, f"Неизвестная котируемая валюта. Поддерживаемые: {', '.join(QUOTE_ASSETS)}"

    return True, None


def validate_timeframe(timeframe: str) -> tuple[bool, Optional[str]]:
    """
    Валидировать таймфрейм.

    Args:
        timeframe: Таймфрейм для проверки

    Returns:
        tuple: (is_valid, error_message)
    """
    if not timeframe or not isinstance(timeframe, str):
        return False, "Таймфрейм должен быть непустой строкой"

    timeframe = timeframe.lower().strip()

    if timeframe not in BINANCE_TIMEFRAMES:
        return False, f"Неподдерживаемый таймфрейм. Доступные: {', '.join(BINANCE_TIMEFRAMES)}"

    return True, None


def validate_price(price: Union[str, float, Decimal]) -> tuple[bool, Optional[str]]:
    """
    Валидировать цену.

    Args:
        price: Цена для валидации

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        if isinstance(price, str):
            price = price.strip()
            if not price:
                return False, "Цена не может быть пустой"

        price_decimal = Decimal(str(price))

        if price_decimal <= 0:
            return False, "Цена должна быть положительным числом"

        if price_decimal > Decimal('1000000000'):
            return False, "Цена слишком большая"

        return True, None

    except (InvalidOperation, ValueError, TypeError):
        return False, "Неверный формат цены"


def validate_volume(volume: Union[str, float, Decimal]) -> tuple[bool, Optional[str]]:
    """
    Валидировать объем торгов.

    Args:
        volume: Объем для валидации

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        if isinstance(volume, str):
            volume = volume.strip()
            if not volume:
                return False, "Объем не может быть пустым"

        volume_decimal = Decimal(str(volume))

        if volume_decimal < 0:
            return False, "Объем не может быть отрицательным"

        return True, None

    except (InvalidOperation, ValueError, TypeError):
        return False, "Неверный формат объема"


def validate_user_id(user_id: Union[str, int]) -> tuple[bool, Optional[str]]:
    """
    Валидировать ID пользователя Telegram.

    Args:
        user_id: ID пользователя

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        user_id_int = int(user_id)

        if user_id_int <= 0:
            return False, "ID пользователя должен быть положительным числом"

        if user_id_int > 2147483647:  # Максимальное значение для int32
            return False, "ID пользователя слишком большой"

        return True, None

    except (ValueError, TypeError):
        return False, "Неверный формат ID пользователя"


def validate_rsi_value(rsi: Union[str, float]) -> tuple[bool, Optional[str]]:
    """
    Валидировать значение RSI.

    Args:
        rsi: Значение RSI

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        rsi_float = float(rsi)

        if rsi_float < 0 or rsi_float > 100:
            return False, "RSI должен быть в диапазоне от 0 до 100"

        return True, None

    except (ValueError, TypeError):
        return False, "Неверный формат RSI"


def validate_ema_period(period: Union[str, int]) -> tuple[bool, Optional[str]]:
    """
    Валидировать период EMA.

    Args:
        period: Период EMA

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        period_int = int(period)

        if period_int < 2:
            return False, "Период EMA должен быть не менее 2"

        if period_int > 1000:
            return False, "Период EMA слишком большой (максимум 1000)"

        return True, None

    except (ValueError, TypeError):
        return False, "Неверный формат периода EMA"


def validate_percentage(percentage: Union[str, float]) -> tuple[bool, Optional[str]]:
    """
    Валидировать процентное значение.

    Args:
        percentage: Процентное значение

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        if isinstance(percentage, str):
            percentage = percentage.strip().replace('%', '')

        percentage_float = float(percentage)

        if abs(percentage_float) > 1000:
            return False, "Процентное значение слишком большое"

        return True, None

    except (ValueError, TypeError):
        return False, "Неверный формат процентного значения"


def validate_timeframes_config(timeframes_config: dict) -> tuple[bool, Optional[str]]:
    """
    Валидировать конфигурацию таймфреймов пользователя.

    Args:
        timeframes_config: Словарь конфигурации таймфреймов

    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(timeframes_config, dict):
        return False, "Конфигурация таймфреймов должна быть словарем"

    if not timeframes_config:
        return False, "Должен быть включен хотя бы один таймфрейм"

    for timeframe, enabled in timeframes_config.items():
        # Валидируем таймфрейм
        is_valid_tf, error = validate_timeframe(timeframe)
        if not is_valid_tf:
            return False, f"Неверный таймфрейм: {error}"

        # Проверяем тип значения
        if not isinstance(enabled, bool):
            return False, f"Значение для таймфрейма {timeframe} должно быть boolean"

    # Проверяем, что хотя бы один таймфрейм включен
    enabled_count = sum(1 for enabled in timeframes_config.values() if enabled)
    if enabled_count == 0:
        return False, "Должен быть включен хотя бы один таймфрейм"

    return True, None


def validate_signal_type(signal_type: str) -> tuple[bool, Optional[str]]:
    """
    Валидировать тип сигнала.

    Args:
        signal_type: Тип сигнала

    Returns:
        tuple: (is_valid, error_message)
    """
    if not signal_type or not isinstance(signal_type, str):
        return False, "Тип сигнала должен быть непустой строкой"

    valid_signal_types = [
        "rsi_oversold_strong",
        "rsi_oversold_medium",
        "rsi_oversold_normal",
        "rsi_overbought_normal",
        "rsi_overbought_medium",
        "rsi_overbought_strong",
        "ema_cross_up",
        "ema_cross_down",
        "volume_spike",
        "trend_change"
    ]

    if signal_type not in valid_signal_types:
        return False, f"Неподдерживаемый тип сигнала. Доступные: {', '.join(valid_signal_types)}"

    return True, None


def sanitize_user_input(text: str, max_length: int = 100) -> str:
    """
    Очистить пользовательский ввод от потенциально опасных символов.

    Args:
        text: Текст для очистки
        max_length: Максимальная длина

    Returns:
        str: Очищенный текст
    """
    if not text or not isinstance(text, str):
        return ""

    # Убираем лишние пробелы
    text = text.strip()

    # Ограничиваем длину
    if len(text) > max_length:
        text = text[:max_length]

    # Убираем потенциально опасные символы
    dangerous_chars = ['<', '>', '"', "'", '&', '\n', '\r', '\t']
    for char in dangerous_chars:
        text = text.replace(char, '')

    return text


def validate_binance_ticker_data(ticker_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Валидация данных ticker от Binance.

    Args:
        ticker_data: Данные ticker от Binance

    Returns:
        tuple[bool, str]: (валидность, сообщение об ошибке)
    """
    try:
        if not isinstance(ticker_data, dict):
            return False, "Ticker data must be a dictionary"

        required_fields = ['s', 'c', 'o', 'h', 'l', 'v', 'q', 'P', 'p']

        for field in required_fields:
            if field not in ticker_data:
                return False, f"Missing required field: {field}"

        # Проверяем цены
        try:
            current_price = float(ticker_data['c'])
            open_price = float(ticker_data['o'])
            high_price = float(ticker_data['h'])
            low_price = float(ticker_data['l'])

            if any(price <= 0 for price in [current_price, open_price, high_price, low_price]):
                return False, "Prices must be positive"

        except (ValueError, TypeError):
            return False, "Invalid price format"

        return True, "Valid ticker data"

    except Exception as e:
        return False, f"Validation error: {str(e)}"


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

    symbol = symbol.upper().strip()

    # Базовые проверки
    if len(symbol) < 4 or len(symbol) > 20:
        return False

    # Должен содержать только буквы и цифры
    if not symbol.isalnum():
        return False

    # Не должен начинаться с цифры
    if symbol[0].isdigit():
        return False

    return True

def extract_base_quote_assets(symbol: str) -> tuple[Optional[str], Optional[str]]:
    """
    Извлечь базовую и котируемую валюты из символа.

    Args:
        symbol: Символ торговой пары

    Returns:
        tuple: (base_asset, quote_asset) или (None, None) если не удалось распарсить
    """
    if not symbol:
        return None, None

    symbol = symbol.upper().strip()

    # Пробуем найти известную котируемую валюту
    for quote in sorted(QUOTE_ASSETS, key=len, reverse=True):  # Сначала длинные
        if symbol.endswith(quote):
            base_asset = symbol[:-len(quote)]
            if len(base_asset) >= 2:  # Минимум 2 символа для базовой валюты
                return base_asset, quote

    return None, None


def is_test_user(user_id: int) -> bool:
    """
    Проверить, является ли пользователь тестовым.

    Args:
        user_id: ID пользователя

    Returns:
        bool: True если пользователь тестовый
    """
    # Тестовые пользователи в Telegram имеют ID больше 10^9
    return user_id > 1000000000