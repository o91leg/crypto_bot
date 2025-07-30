"""
Путь: src/utils/math_helpers.py
Описание: Математические функции для расчета технических индикаторов
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import math
from typing import List, Optional, Union
from decimal import Decimal, ROUND_HALF_UP
import numpy as np


def safe_divide(dividend: Union[float, Decimal], divisor: Union[float, Decimal]) -> float:
    """
    Безопасное деление с обработкой деления на ноль.

    Args:
        dividend: Делимое
        divisor: Делитель

    Returns:
        float: Результат деления или 0.0 при делении на ноль
    """
    try:
        if divisor == 0 or divisor is None:
            return 0.0
        return float(dividend) / float(divisor)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Рассчитать процентное изменение между двумя значениями.

    Args:
        old_value: Старое значение
        new_value: Новое значение

    Returns:
        float: Процентное изменение
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def round_to_precision(value: Union[float, Decimal], precision: int) -> float:
    """
    Округлить значение до указанной точности.

    Args:
        value: Значение для округления
        precision: Количество знаков после запятой

    Returns:
        float: Округленное значение
    """
    if isinstance(value, Decimal):
        return float(value.quantize(Decimal('0.1') ** precision, rounding=ROUND_HALF_UP))
    else:
        return round(float(value), precision)


def calculate_simple_moving_average(values: List[float], period: int) -> Optional[float]:
    """
    Рассчитать простое скользящее среднее (SMA).

    Args:
        values: Список значений
        period: Период для расчета

    Returns:
        Optional[float]: SMA или None если недостаточно данных
    """
    if len(values) < period:
        return None

    recent_values = values[-period:]
    return sum(recent_values) / period


def calculate_exponential_moving_average(
    values: List[float],
    period: int,
    previous_ema: Optional[float] = None
) -> Optional[float]:
    """
    Рассчитать экспоненциальное скользящее среднее (EMA).

    Args:
        values: Список значений
        period: Период для расчета
        previous_ema: Предыдущее значение EMA

    Returns:
        Optional[float]: EMA или None если недостаточно данных
    """
    if len(values) == 0:
        return None

    current_value = values[-1]
    multiplier = 2.0 / (period + 1)

    if previous_ema is None:
        # Первый расчет - используем SMA
        if len(values) < period:
            return None
        previous_ema = calculate_simple_moving_average(values[-period:], period)
        if previous_ema is None:
            return None

    return (current_value * multiplier) + (previous_ema * (1 - multiplier))


def calculate_rsi_values(prices: List[float], period: int = 14) -> List[float]:
    """
    Рассчитать значения RSI для массива цен.

    Args:
        prices: Список цен закрытия
        period: Период для расчета RSI

    Returns:
        List[float]: Список значений RSI
    """
    if len(prices) < period + 1:
        return []

    deltas = []
    for i in range(1, len(prices)):
        deltas.append(prices[i] - prices[i - 1])

    gains = []
    losses = []

    for delta in deltas:
        if delta > 0:
            gains.append(delta)
            losses.append(0)
        elif delta < 0:
            gains.append(0)
            losses.append(-delta)
        else:
            gains.append(0)
            losses.append(0)

    rsi_values = []

    # Первый RSI с простым средним
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))

    # Последующие RSI с экспоненциальным сглаживанием
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    return rsi_values


def calculate_single_rsi_value(price_changes: List[float], period: int = 14) -> Optional[float]:
    """
    Рассчитать одно значение RSI из изменений цен.

    Args:
        price_changes: Список изменений цен
        period: Период для расчета RSI

    Returns:
        Optional[float]: Значение RSI или None при ошибке
    """
    if len(price_changes) < period:
        return None

    gains = []
    losses = []

    for change in price_changes:
        if change > 0:
            gains.append(change)
            losses.append(0)
        elif change < 0:
            gains.append(0)
            losses.append(-change)
        else:
            gains.append(0)
            losses.append(0)

    # Берем последние `period` значений для расчета
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]

    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_rsi_from_prices(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Рассчитать RSI напрямую из цен (удобная функция).

    Args:
        prices: Список цен закрытия
        period: Период для расчета RSI

    Returns:
        Optional[float]: Значение RSI или None при ошибке
    """
    if len(prices) < period + 1:
        return None

    # Вычисляем изменения цен
    price_changes = []
    for i in range(1, len(prices)):
        price_changes.append(prices[i] - prices[i - 1])

    return calculate_single_rsi_value(price_changes, period)

def calculate_smoothed_rsi(prices: List[float], period: int = 14, smoothing: int = 3) -> List[float]:
    """
    Рассчитать сглаженные значения RSI.

    Args:
        prices: Список цен закрытия
        period: Период для расчета RSI
        smoothing: Период сглаживания

    Returns:
        List[float]: Список сглаженных значений RSI
    """
    rsi_values = calculate_rsi_values(prices, period)

    if len(rsi_values) < smoothing:
        return rsi_values

    smoothed_rsi = []

    # Первые значения без сглаживания
    for i in range(smoothing - 1):
        smoothed_rsi.append(rsi_values[i])

    # Сглаженные значения
    for i in range(smoothing - 1, len(rsi_values)):
        smooth_value = sum(rsi_values[i - smoothing + 1:i + 1]) / smoothing
        smoothed_rsi.append(smooth_value)

    return smoothed_rsi


def calculate_ema_values(prices: List[float], period: int) -> List[float]:
    """
    Рассчитать экспоненциальное скользящее среднее.

    Args:
        prices: Список цен
        period: Период EMA

    Returns:
        List[float]: Список значений EMA
    """
    if len(prices) < period:
        return []

    ema_values = []
    multiplier = 2 / (period + 1)

    # Первое значение EMA = SMA
    sma = sum(prices[:period]) / period
    ema_values.append(sma)

    # Последующие значения EMA
    for i in range(period, len(prices)):
        ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
        ema_values.append(ema)

    return ema_values


def calculate_sma_values(prices: List[float], period: int) -> List[float]:
    """
    Рассчитать простое скользящее среднее.

    Args:
        prices: Список цен
        period: Период SMA

    Returns:
        List[float]: Список значений SMA
    """
    if len(prices) < period:
        return []

    sma_values = []
    for i in range(period - 1, len(prices)):
        sma = sum(prices[i - period + 1:i + 1]) / period
        sma_values.append(sma)

    return sma_values

def calculate_standard_deviation(values: List[float]) -> float:
    """
    Рассчитать стандартное отклонение.

    Args:
        values: Список значений

    Returns:
        float: Стандартное отклонение
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5

def calculate_bollinger_bands(
    values: List[float],
    period: int = 20,
    std_dev_multiplier: float = 2.0
) -> tuple:
    """
    Рассчитать полосы Боллинджера.

    Args:
        values: Список значений цен
        period: Период для расчета
        std_dev_multiplier: Множитель стандартного отклонения

    Returns:
        tuple: (верхняя полоса, средняя линия, нижняя полоса) или (None, None, None)
    """
    if len(values) < period:
        return None, None, None

    middle_band = calculate_simple_moving_average(values, period)
    if middle_band is None:
        return None, None, None

    std_dev = calculate_standard_deviation(values, period)
    if std_dev is None:
        return None, None, None

    upper_band = middle_band + (std_dev * std_dev_multiplier)
    lower_band = middle_band - (std_dev * std_dev_multiplier)

    return upper_band, middle_band, lower_band


def calculate_true_range(high: float, low: float, previous_close: float) -> float:
    """
    Рассчитать истинный диапазон (True Range).

    Args:
        high: Максимальная цена
        low: Минимальная цена
        previous_close: Предыдущая цена закрытия

    Returns:
        float: Значение истинного диапазона
    """
    tr1 = high - low
    tr2 = abs(high - previous_close)
    tr3 = abs(low - previous_close)

    return max(tr1, tr2, tr3)


def is_valid_price(price: Union[float, str, Decimal]) -> bool:
    """
    Проверить, является ли цена валидной.

    Args:
        price: Цена для проверки

    Returns:
        bool: True если цена валидна
    """
    try:
        price_float = float(price)
        return price_float > 0 and not math.isnan(price_float) and not math.isinf(price_float)
    except (ValueError, TypeError):
        return False


def normalize_price_array(prices: List[Union[float, str, Decimal]]) -> List[float]:
    """
    Нормализовать массив цен, убрав невалидные значения.

    Args:
        prices: Список цен

    Returns:
        List[float]: Нормализованный список цен
    """
    normalized = []
    for price in prices:
        if is_valid_price(price):
            normalized.append(float(price))

    return normalized


def calculate_price_momentum(prices: List[float], period: int = 10) -> Optional[float]:
    """
    Рассчитать моментум цены.

    Args:
        prices: Список цен
        period: Период для расчета

    Returns:
        Optional[float]: Моментум или None
    """
    if len(prices) < period + 1:
        return None

    current_price = prices[-1]
    previous_price = prices[-(period + 1)]

    return current_price - previous_price


def calculate_rate_of_change(prices: List[float], period: int = 12) -> Optional[float]:
    """
    Рассчитать скорость изменения (ROC).

    Args:
        prices: Список цен
        period: Период для расчета

    Returns:
        Optional[float]: ROC в процентах или None
    """
    if len(prices) < period + 1:
        return None

    current_price = prices[-1]
    previous_price = prices[-(period + 1)]

    if previous_price == 0:
        return 0.0

    return ((current_price - previous_price) / previous_price) * 100


def calculate_williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """
    Рассчитать индикатор Williams %R.

    Args:
        highs: Список максимальных цен
        lows: Список минимальных цен
        closes: Список цен закрытия
        period: Период для расчета

    Returns:
        Optional[float]: Williams %R или None
    """
    if len(highs) < period or len(lows) < period or len(closes) < period:
        return None

    highest_high = max(highs[-period:])
    lowest_low = min(lows[-period:])
    current_close = closes[-1]

    if highest_high == lowest_low:
        return -50.0  # Средний уровень при равных значениях

    williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100

    return williams_r


def calculate_correlation(x_values: List[float], y_values: List[float]) -> float:
    """
    Рассчитать коэффициент корреляции между двумя рядами.

    Args:
        x_values: Первый ряд значений
        y_values: Второй ряд значений

    Returns:
        float: Коэффициент корреляции (-1 до 1)
    """
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return 0.0

    n = len(x_values)
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_x2 = sum(x * x for x in x_values)
    sum_y2 = sum(y * y for y in y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))

    numerator = n * sum_xy - sum_x * sum_y
    denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

    if denominator == 0:
        return 0.0

    return numerator / denominator

def format_number_for_display(value: float, precision: int = 2) -> str:
    """
    Форматировать число для отображения пользователю.

    Args:
        value: Значение для форматирования
        precision: Точность (знаков после запятой)

    Returns:
        str: Отформатированное число
    """
    if abs(value) >= 1000000:
        return f"{value / 1000000:.{precision}f}M"
    elif abs(value) >= 1000:
        return f"{value / 1000:.{precision}f}K"
    else:
        return f"{value:.{precision}f}"