"""
Путь: src/utils/rsi_helpers.py
Описание: Вспомогательные функции для работы с RSI.

Этот модуль содержит небольшие утилиты и константы,
необходимые для корректной проверки входных данных
и формирования сообщений об ошибках при расчёте RSI.
"""

from typing import Iterable, Tuple, Optional


# Минимально допустимый период RSI
MIN_RSI_PERIOD: int = 2
# Минимальное количество свечей для расчёта RSI (period + 1)
MIN_RSI_CANDLES: int = MIN_RSI_PERIOD + 1


def format_rsi_error(error_type: str, candle_count: int, required_count: int) -> str:
    """Сформировать сообщение об ошибке для расчёта RSI.

    Args:
        error_type: Тип ошибки (например, "insufficient_candles").
        candle_count: Количество предоставленных свечей.
        required_count: Требуемое количество свечей.

    Returns:
        str: Текст ошибки.
    """
    if error_type == "insufficient_candles":
        return (
            f"Недостаточно данных для расчёта RSI: "
            f"предоставлено {candle_count}, требуется {required_count}"
        )
    return "Неизвестная ошибка RSI"


def validate_rsi_data(candles: Iterable, required_period: int) -> Tuple[bool, Optional[str]]:
    """Проверить данные перед расчётом RSI.

    Args:
        candles: Итерация свечей (объекты со свойством ``close_price``).
        required_period: Период RSI.

    Returns:
        tuple: (валидность, сообщение об ошибке)
    """
    if required_period < MIN_RSI_PERIOD:
        return False, format_rsi_error(
            "insufficient_candles",
            candle_count=0,
            required_count=MIN_RSI_CANDLES,
        )

    candle_list = list(candles)
    required_candles = required_period + 1

    if len(candle_list) < required_candles:
        return False, format_rsi_error(
            "insufficient_candles",
            candle_count=len(candle_list),
            required_count=required_candles,
        )

    for candle in candle_list:
        close = getattr(candle, "close_price", None)
        if close is None:
            return False, "Отсутствует цена закрытия в одной из свечей"

    return True, None
