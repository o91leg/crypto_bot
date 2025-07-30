"""
Путь: src/utils/time_helpers.py
Описание: Функции для работы со временем и таймфреймами
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from utils.constants import TIMEFRAME_TO_MS, TIMEFRAME_NAMES


def get_current_timestamp() -> int:
    """
    Получить текущую временную метку в миллисекундах.

    Returns:
        int: Временная метка в миллисекундах
    """
    import time
    return int(time.time() * 1000)


def get_current_timestamp_seconds() -> int:
    """
    Получить текущий Unix timestamp в секундах.

    Returns:
        int: Текущий timestamp в секундах
    """
    return int(time.time())


def timestamp_to_datetime(timestamp: int, in_milliseconds: bool = True) -> datetime:
    """
    Преобразовать Unix timestamp в datetime объект.

    Args:
        timestamp: Unix timestamp
        in_milliseconds: True если timestamp в миллисекундах

    Returns:
        datetime: Объект datetime в UTC
    """
    if in_milliseconds:
        timestamp = timestamp / 1000

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime, in_milliseconds: bool = True) -> int:
    """
    Преобразовать datetime в Unix timestamp.

    Args:
        dt: Объект datetime
        in_milliseconds: True если нужен timestamp в миллисекундах

    Returns:
        int: Unix timestamp
    """
    timestamp = int(dt.timestamp())

    if in_milliseconds:
        timestamp *= 1000

    return timestamp


def timeframe_to_milliseconds(timeframe: str) -> Optional[int]:
    """
    Получить количество миллисекунд для таймфрейма.

    Args:
        timeframe: Таймфрейм (например, '1h', '4h', '1d')

    Returns:
        Optional[int]: Количество миллисекунд или None если таймфрейм не поддерживается
    """
    return TIMEFRAME_TO_MS.get(timeframe)


def timeframe_to_seconds(timeframe: str) -> Optional[int]:
    """
    Получить количество секунд для таймфрейма.

    Args:
        timeframe: Таймфрейм

    Returns:
        Optional[int]: Количество секунд или None
    """
    ms = timeframe_to_milliseconds(timeframe)
    return int(ms / 1000) if ms else None


def get_timeframe_display_name(timeframe: str) -> str:
    """
    Получить человекочитаемое название таймфрейма.

    Args:
        timeframe: Таймфрейм

    Returns:
        str: Человекочитаемое название
    """
    return TIMEFRAME_NAMES.get(timeframe, timeframe)


def align_timestamp_to_timeframe(timestamp: int, timeframe: str) -> int:
    """
    Выровнять timestamp по границе таймфрейма.

    Args:
        timestamp: Timestamp в миллисекундах
        timeframe: Таймфрейм

    Returns:
        int: Выровненный timestamp
    """
    timeframe_ms = timeframe_to_milliseconds(timeframe)
    if timeframe_ms is None:
        return timestamp

    return (timestamp // timeframe_ms) * timeframe_ms


def get_candle_open_time(timestamp: int, timeframe: str) -> int:
    """
    Получить время открытия свечи для заданного timestamp.

    Args:
        timestamp: Timestamp в миллисекундах
        timeframe: Таймфрейм

    Returns:
        int: Время открытия свечи
    """
    return align_timestamp_to_timeframe(timestamp, timeframe)


def get_candle_close_time(open_time: int, timeframe: str) -> int:
    """
    Получить время закрытия свечи.

    Args:
        open_time: Время открытия свечи в миллисекундах
        timeframe: Таймфрейм

    Returns:
        int: Время закрытия свечи
    """
    timeframe_ms = timeframe_to_milliseconds(timeframe)
    if timeframe_ms is None:
        return open_time

    return open_time + timeframe_ms - 1


def get_previous_candle_time(current_time: int, timeframe: str, periods_back: int = 1) -> int:
    """
    Получить время предыдущей свечи.

    Args:
        current_time: Текущее время в миллисекундах
        timeframe: Таймфрейм
        periods_back: На сколько периодов назад

    Returns:
        int: Время предыдущей свечи
    """
    timeframe_ms = timeframe_to_milliseconds(timeframe)
    if timeframe_ms is None:
        return current_time

    aligned_time = align_timestamp_to_timeframe(current_time, timeframe)
    return aligned_time - (timeframe_ms * periods_back)


def get_next_candle_time(current_time: int, timeframe: str, periods_forward: int = 1) -> int:
    """
    Получить время следующей свечи.

    Args:
        current_time: Текущее время в миллисекундах
        timeframe: Таймфрейм
        periods_forward: На сколько периодов вперед

    Returns:
        int: Время следующей свечи
    """
    timeframe_ms = timeframe_to_milliseconds(timeframe)
    if timeframe_ms is None:
        return current_time

    aligned_time = align_timestamp_to_timeframe(current_time, timeframe)
    return aligned_time + (timeframe_ms * periods_forward)


def calculate_time_until_next_candle(timeframe: str) -> int:
    """
    Рассчитать количество секунд до следующей свечи.

    Args:
        timeframe: Таймфрейм

    Returns:
        int: Количество секунд до следующей свечи
    """
    current_time = get_current_timestamp()
    next_candle_time = get_next_candle_time(current_time, timeframe)

    return int((next_candle_time - current_time) / 1000)


def is_candle_closed(timestamp: int, timeframe: str) -> bool:
    """
    Проверить, закрыта ли свеча для данного времени.

    Args:
        timestamp: Timestamp в миллисекундах
        timeframe: Таймфрейм

    Returns:
        bool: True если свеча закрыта
    """
    current_time = get_current_timestamp()
    candle_close_time = get_candle_close_time(
        get_candle_open_time(timestamp, timeframe),
        timeframe
    )

    return current_time > candle_close_time


def get_historical_time_range(timeframe: str, limit: int, end_time: int) -> tuple[int, int]:
    """
    Рассчитать временной диапазон для загрузки исторических данных.

    Args:
        timeframe: Таймфрейм (например, '1h')
        limit: Количество свечей
        end_time: Конечное время в миллисекундах

    Returns:
        tuple[int, int]: (start_time, end_time) в миллисекундах
    """
    from utils.constants import TIMEFRAME_TO_MS

    # Получаем длительность одной свечи в миллисекундах
    timeframe_ms = TIMEFRAME_TO_MS.get(timeframe, 60000)  # По умолчанию 1 минута

    # Рассчитываем начальное время
    start_time = end_time - (timeframe_ms * limit)

    return start_time, end_time


def format_timestamp_for_display(timestamp: int, in_milliseconds: bool = True) -> str:
    """
    Отформатировать timestamp для отображения пользователю.

    Args:
        timestamp: Unix timestamp
        in_milliseconds: True если timestamp в миллисекундах

    Returns:
        str: Отформатированная дата и время
    """
    dt = timestamp_to_datetime(timestamp, in_milliseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_duration(seconds: int) -> str:
    """
    Отформатировать продолжительность в человекочитаемый вид.

    Args:
        seconds: Количество секунд

    Returns:
        str: Отформатированная продолжительность
    """
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}м"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}ч {minutes}м"
        return f"{hours}ч"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours > 0:
            return f"{days}д {hours}ч"
        return f"{days}д"


def get_market_time_info() -> Dict[str, str]:
    """
    Получить информацию о рыночном времени.

    Returns:
        Dict[str, str]: Информация о времени различных рынков
    """
    now_utc = datetime.now(timezone.utc)

    # Основные временные зоны для криптовалютных рынков
    timezones = {
        "UTC": timezone.utc,
        "EST": timezone(timedelta(hours=-5)),  # New York
        "CET": timezone(timedelta(hours=1)),   # Central Europe
        "JST": timezone(timedelta(hours=9)),   # Tokyo
        "SGT": timezone(timedelta(hours=8)),   # Singapore
    }

    time_info = {}
    for name, tz in timezones.items():
        local_time = now_utc.astimezone(tz)
        time_info[name] = local_time.strftime("%H:%M")

    return time_info


def validate_timeframe(timeframe: str) -> bool:
    """
    Валидировать таймфрейм.

    Args:
        timeframe: Таймфрейм для проверки

    Returns:
        bool: True если таймфрейм валиден
    """
    return timeframe in TIMEFRAME_TO_MS


def get_supported_timeframes() -> List[str]:
    """
    Получить список поддерживаемых таймфреймов.

    Returns:
        List[str]: Список таймфреймов
    """
    return list(TIMEFRAME_TO_MS.keys())


def sort_timeframes_by_duration(timeframes: List[str]) -> List[str]:
    """
    Отсортировать таймфреймы по продолжительности.

    Args:
        timeframes: Список таймфреймов

    Returns:
        List[str]: Отсортированный список
    """
    def get_duration(tf: str) -> int:
        return TIMEFRAME_TO_MS.get(tf, 0)

    return sorted(timeframes, key=get_duration)


def is_time_for_signal_check(last_check: int, interval_seconds: int = 60) -> bool:
    """
    Проверить, пора ли проверять сигналы.

    Args:
        last_check: Время последней проверки (timestamp в секундах)
        interval_seconds: Интервал проверки в секундах

    Returns:
        bool: True если пора проверять
    """
    current_time = get_current_timestamp_seconds()
    return (current_time - last_check) >= interval_seconds


def get_time_ago_text(timestamp: int, in_milliseconds: bool = True) -> str:
    """
    Получить текст "X времени назад".

    Args:
        timestamp: Timestamp
        in_milliseconds: True если timestamp в миллисекундах

    Returns:
        str: Текст времени назад
    """
    current_time = get_current_timestamp()
    if not in_milliseconds:
        timestamp *= 1000
        current_time = current_time

    diff_seconds = (current_time - timestamp) // 1000

    if diff_seconds < 60:
        return "только что"
    elif diff_seconds < 3600:
        minutes = diff_seconds // 60
        return f"{minutes} мин назад"
    elif diff_seconds < 86400:
        hours = diff_seconds // 3600
        return f"{hours} ч назад"
    else:
        days = diff_seconds // 86400
        return f"{days} дн назад"