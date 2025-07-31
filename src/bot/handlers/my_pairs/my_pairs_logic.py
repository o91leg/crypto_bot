"""
Путь: src/bot/handlers/my_pairs/my_pairs_logic.py
Описание: Бизнес-логика для работы с торговыми парами пользователя
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from services.indicators.realtime_calculator import RealtimeCalculator

# Настройка логирования
logger = structlog.get_logger(__name__)


async def calculate_rsi_for_pair(session: AsyncSession, user_pair) -> dict:
    """Рассчитать RSI для пары с использованием живых данных."""
    realtime_calc = RealtimeCalculator()
    rsi_data: dict = {}

    for timeframe in user_pair.get_enabled_timeframes():
        try:
            fresh_rsi = await realtime_calc.get_fresh_rsi(
                session, user_pair.pair_id, timeframe
            )

            if fresh_rsi:
                rsi_data[timeframe] = fresh_rsi
            else:
                rsi_data[timeframe] = {"error": "Недостаточно данных"}

        except Exception as e:
            rsi_data[timeframe] = {"error": f"Ошибка расчета: {str(e)[:50]}"}

    return rsi_data


def validate_timeframe_toggle(user_pair, timeframe: str) -> tuple[bool, str]:
    """
    Валидировать переключение таймфрейма.

    Args:
        user_pair: Пользовательская пара
        timeframe: Таймфрейм для переключения

    Returns:
        tuple: (is_valid, error_message)
    """
    from config.bot_config import get_bot_config

    config = get_bot_config()

    # Проверяем, что таймфрейм поддерживается
    if timeframe not in config.default_timeframes:
        return False, f"Таймфрейм {timeframe} не поддерживается"

    # Проверяем, что не отключаем последний активный таймфрейм
    enabled_timeframes = user_pair.get_enabled_timeframes()
    is_currently_enabled = user_pair.is_timeframe_enabled(timeframe)

    if is_currently_enabled and len(enabled_timeframes) == 1:
        return False, "Нельзя отключить единственный активный таймфрейм"

    return True, ""


def get_pair_statistics(user_pair) -> dict:
    """
    Получить статистику по паре.

    Args:
        user_pair: Пользовательская пара

    Returns:
        dict: Статистика пары
    """
    enabled_timeframes = user_pair.get_enabled_timeframes()
    total_timeframes = len(user_pair.timeframes)

    return {
        "enabled_timeframes_count": len(enabled_timeframes),
        "total_timeframes_count": total_timeframes,
        "enabled_percentage": (
            len(enabled_timeframes) / total_timeframes * 100
            if total_timeframes > 0
            else 0
        ),
        "signals_received": user_pair.signals_received,
        "pair_symbol": user_pair.pair.symbol,
        "pair_display_name": user_pair.pair.display_name,
    }


async def update_pair_timeframes_bulk(
    session: AsyncSession, user_pair, timeframes_config: dict
) -> bool:
    """
    Массовое обновление таймфреймов пары.

    Args:
        session: Сессия базы данных
        user_pair: Пользовательская пара
        timeframes_config: Конфигурация таймфреймов

    Returns:
        bool: Успешность операции
    """
    try:
        # Проверяем, что хотя бы один таймфрейм будет активен
        enabled_count = sum(
            1 for enabled in timeframes_config.values() if enabled
        )

        if enabled_count == 0:
            logger.warning(
                "Attempted to disable all timeframes",
                pair_id=user_pair.pair_id,
            )
            return False

        # Обновляем конфигурацию
        user_pair.set_timeframes(timeframes_config)
        await session.commit()

        logger.info(
            "Bulk timeframes update completed",
            pair_id=user_pair.pair_id,
            enabled_count=enabled_count,
        )

        return True

    except Exception as e:
        logger.error("Error updating timeframes bulk", error=str(e))
        await session.rollback()
        return False
