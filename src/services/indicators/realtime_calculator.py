"""
Путь: src/services/indicators/realtime_calculator.py
Описание: Сервис пересчета индикаторов при получении новых данных
Автор: Crypto Bot Team
Дата создания: 2025-07-30
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from services.indicators.rsi_calculator import RSICalculator
from services.cache.indicator_cache import IndicatorCache
from utils.logger import get_logger


class RealtimeCalculator:
    """Калькулятор индикаторов в реальном времени"""

    def __init__(self):
        self.rsi_calculator = RSICalculator()
        self.indicator_cache = IndicatorCache()
        self.logger = get_logger(__name__)

    async def recalculate_indicators(
        self,
        session: AsyncSession,
        pair_id: int,
        timeframe: str
    ):
        """
        Пересчитать все индикаторы для пары и таймфрейма.

        Args:
            session: Сессия БД
            pair_id: ID пары
            timeframe: Таймфрейм
        """
        try:
            # Получаем символ пары для кеширования
            from data.models.pair_model import Pair
            pair = await Pair.get_by_id(session, pair_id)
            if not pair:
                return

            # Пересчитываем RSI
            rsi_result = await self.rsi_calculator.calculate_rsi_from_candles(
                session=session,
                pair_id=pair_id,
                timeframe=timeframe,
                period=14
            )

            if rsi_result:
                # Кешируем новое значение RSI
                cache_key = f"rsi:{pair.symbol}:{timeframe}:14"
                await self.indicator_cache.set_indicator(
                    cache_key,
                    {
                        "value": rsi_result.value,
                        "timestamp": rsi_result.timestamp.isoformat(),
                        "interpretation": rsi_result.interpretation
                    },
                    ttl=300  # 5 минут
                )

                self.logger.info(
                    "RSI recalculated and cached",
                    symbol=pair.symbol,
                    timeframe=timeframe,
                    rsi=rsi_result.value
                )

            # Здесь можно добавить пересчет других индикаторов (EMA, etc)

        except Exception as e:
            self.logger.error(
                "Error recalculating indicators",
                pair_id=pair_id,
                timeframe=timeframe,
                error=str(e)
            )

    async def get_fresh_rsi(
        self,
        session: AsyncSession,
        pair_id: int,
        timeframe: str
    ) -> Optional[dict]:
        """
        Получить свежий RSI (из кеша или пересчитать).

        Args:
            session: Сессия БД
            pair_id: ID пары
            timeframe: Таймфрейм

        Returns:
            dict: Данные RSI или None
        """
        try:
            # Получаем символ пары
            from data.models.pair_model import Pair
            pair = await Pair.get_by_id(session, pair_id)
            if not pair:
                return None

            # Проверяем кеш
            cache_key = f"rsi:{pair.symbol}:{timeframe}:14"
            cached_rsi = await self.indicator_cache.get_indicator(cache_key)

            if cached_rsi:
                return cached_rsi

            # Если в кеше нет - пересчитываем
            await self.recalculate_indicators(session, pair_id, timeframe)

            # Возвращаем из кеша после пересчета
            return await self.indicator_cache.get_indicator(cache_key)

        except Exception as e:
            self.logger.error("Error getting fresh RSI", error=str(e))
            return None
