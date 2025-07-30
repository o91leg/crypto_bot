"""
Путь: src/services/signals/signal_aggregator.py
Описание: Сервис для объединения и координации всех типов сигналов
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from services.signals.rsi_signals import rsi_signal_generator
from services.cache.indicator_cache import indicator_cache
from services.cache.candle_cache import candle_cache
from services.indicators.rsi_calculator import RSICalculator
from services.indicators.ema_calculator import EMACalculator
from utils.logger import get_logger
from utils.constants import BINANCE_TIMEFRAMES, RSI_PERIODS, EMA_PERIODS
from utils.exceptions import SignalError


class SignalAggregator:
    """
    Агрегатор всех типов сигналов.

    Координирует:
    - RSI сигналы
    - EMA сигналы
    - Объемные сигналы
    - Комбинированные сигналы
    """

    def __init__(self):
        """Инициализация агрегатора сигналов."""
        self.logger = get_logger(__name__)
        self.rsi_calculator = RSICalculator()
        self.ema_calculator = EMACalculator()

        # Статистика обработки
        self.stats = {
            "processed_updates": 0,
            "generated_signals": 0,
            "sent_notifications": 0,
            "errors": 0
        }

    async def process_candle_update(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            candle_data: Dict[str, Any],
            is_closed: bool = True
    ) -> Dict[str, int]:
        """
        Обработать обновление свечи и сгенерировать сигналы.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle_data: Данные свечи
            is_closed: Закрыта ли свеча

        Returns:
            Dict[str, int]: Статистика генерации сигналов
        """
        try:
            self.stats["processed_updates"] += 1

            result = {
                "rsi_notifications": 0,
                "ema_notifications": 0,
                "volume_notifications": 0,
                "total_notifications": 0
            }

            # Получаем текущую цену
            current_price = float(candle_data.get("close_price", 0))

            if current_price <= 0:
                self.logger.warning(
                    "Invalid candle price",
                    symbol=symbol,
                    timeframe=timeframe,
                    price=current_price
                )
                return result

            # Обновляем кеш свечей
            if is_closed:
                await candle_cache.add_new_candle(symbol, timeframe, candle_data)
            else:
                await candle_cache.update_last_candle(symbol, timeframe, candle_data)

            # Рассчитываем индикаторы
            indicators = await self._calculate_indicators(
                symbol, timeframe, candle_data, is_closed
            )

            if not indicators:
                return result

            # Рассчитываем изменение объема
            volume_change = await self._calculate_volume_change(
                symbol, timeframe, candle_data
            )

            # Генерируем RSI сигналы
            if indicators.get("rsi"):
                rsi_count = await self._process_rsi_signals(
                    session=session,
                    symbol=symbol,
                    timeframe=timeframe,
                    rsi_value=indicators["rsi"],
                    price=current_price,
                    volume_change_percent=volume_change
                )
                result["rsi_notifications"] = rsi_count

            # Генерируем EMA сигналы (пока заглушка)
            if indicators.get("ema"):
                ema_count = await self._process_ema_signals(
                    session=session,
                    symbol=symbol,
                    timeframe=timeframe,
                    ema_values=indicators["ema"],
                    price=current_price
                )
                result["ema_notifications"] = ema_count

            # Общее количество уведомлений
            result["total_notifications"] = (
                    result["rsi_notifications"] +
                    result["ema_notifications"] +
                    result["volume_notifications"]
            )

            self.stats["generated_signals"] += result["total_notifications"]
            self.stats["sent_notifications"] += result["total_notifications"]

            if result["total_notifications"] > 0:
                self.logger.info(
                    "Signals processed successfully",
                    symbol=symbol,
                    timeframe=timeframe,
                    **result
                )

            return result

        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(
                "Error processing candle update",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return {
                "rsi_notifications": 0,
                "ema_notifications": 0,
                "volume_notifications": 0,
                "total_notifications": 0,
                "error": str(e)
            }

    async def process_multiple_pairs(
            self,
            session: AsyncSession,
            updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Обработать обновления для нескольких пар.

        Args:
            session: Сессия базы данных
            updates: Список обновлений

        Returns:
            Dict: Общая статистика
        """
        total_stats = {
            "processed_pairs": 0,
            "total_notifications": 0,
            "errors": 0
        }

        try:
            # Обрабатываем обновления параллельно
            tasks = []

            for update in updates:
                task = self.process_candle_update(
                    session=session,
                    symbol=update["symbol"],
                    timeframe=update["timeframe"],
                    candle_data=update["candle_data"],
                    is_closed=update.get("is_closed", True)
                )
                tasks.append(task)

            # Ждем результаты
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Собираем статистику
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    total_stats["errors"] += 1
                    self.logger.error(
                        "Error in parallel processing",
                        update_index=i,
                        error=str(result)
                    )
                else:
                    total_stats["processed_pairs"] += 1
                    total_stats["total_notifications"] += result.get("total_notifications", 0)

            self.logger.info(
                "Batch processing completed",
                **total_stats
            )

            return total_stats

        except Exception as e:
            self.logger.error(
                "Error in batch processing",
                updates_count=len(updates),
                error=str(e)
            )
            return total_stats

    async def _calculate_indicators(
            self,
            symbol: str,
            timeframe: str,
            candle_data: Dict[str, Any],
            is_closed: bool
    ) -> Dict[str, Any]:
        """
        Рассчитать все индикаторы для свечи.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle_data: Данные свечи
            is_closed: Закрыта ли свеча

        Returns:
            Dict: Рассчитанные индикаторы
        """
        try:
            indicators = {}

            # Получаем исторические данные для расчетов
            candles = await candle_cache.get_candles(symbol, timeframe, limit=200)

            if len(candles) < 50:  # Недостаточно данных
                self.logger.debug(
                    "Insufficient candles for indicators",
                    symbol=symbol,
                    timeframe=timeframe,
                    candles_count=len(candles)
                )
                return indicators

            # Преобразуем в список цен закрытия
            close_prices = [float(candle["close_price"]) for candle in candles]

            # Рассчитываем RSI
            try:
                rsi_value = await self.rsi_calculator.calculate_rsi(
                    prices=close_prices,
                    period=14
                )

                if rsi_value is not None:
                    indicators["rsi"] = rsi_value

                    # Кешируем RSI
                    await indicator_cache.set_rsi(
                        symbol, timeframe, 14, rsi_value
                    )

            except Exception as e:
                self.logger.error(
                    "Error calculating RSI",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )

            # Рассчитываем EMA
            try:
                ema_values = {}

                for period in [20, 50, 100, 200]:
                    if len(close_prices) >= period:
                        ema_value = await self.ema_calculator.calculate_ema(
                            prices=close_prices,
                            period=period
                        )

                        if ema_value is not None:
                            ema_values[period] = ema_value

                            # Кешируем EMA
                            await indicator_cache.set_ema(
                                symbol, timeframe, period, ema_value
                            )

                if ema_values:
                    indicators["ema"] = ema_values

            except Exception as e:
                self.logger.error(
                    "Error calculating EMA",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )

            return indicators

        except Exception as e:
            self.logger.error(
                "Error calculating indicators",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return {}

    async def _calculate_volume_change(
            self,
            symbol: str,
            timeframe: str,
            candle_data: Dict[str, Any]
    ) -> Optional[float]:
        """
        Рассчитать изменение объема.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle_data: Данные текущей свечи

        Returns:
            float: Изменение объема в процентах
        """
        try:
            current_volume = float(candle_data.get("volume", 0))

            if current_volume <= 0:
                return None

            # Получаем предыдущие свечи
            candles = await candle_cache.get_candles(symbol, timeframe, limit=2)

            if len(candles) < 2:
                return None

            # Берем предпоследнюю свечу (последняя - текущая)
            prev_volume = float(candles[-2].get("volume", 0))

            if prev_volume <= 0:
                return None

            # Рассчитываем изменение в процентах
            volume_change = ((current_volume - prev_volume) / prev_volume) * 100

            # Кешируем изменение объема
            await indicator_cache.set_volume_change(
                symbol, timeframe, volume_change
            )

            return volume_change

        except Exception as e:
            self.logger.error(
                "Error calculating volume change",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return None

    async def _process_rsi_signals(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            rsi_value: float,
            price: float,
            volume_change_percent: Optional[float]
    ) -> int:
        """
        Обработать RSI сигналы.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            rsi_value: Значение RSI
            price: Текущая цена
            volume_change_percent: Изменение объема

        Returns:
            int: Количество сгенерированных уведомлений
        """
        try:
            return await rsi_signal_generator.process_rsi_update(
                session=session,
                symbol=symbol,
                timeframe=timeframe,
                rsi_value=rsi_value,
                price=price,
                volume_change_percent=volume_change_percent
            )

        except Exception as e:
            self.logger.error(
                "Error processing RSI signals",
                symbol=symbol,
                timeframe=timeframe,
                rsi_value=rsi_value,
                error=str(e)
            )
            return 0

    async def _process_ema_signals(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            ema_values: Dict[int, float],
            price: float
    ) -> int:
        """
        Обработать EMA сигналы (заглушка).

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            ema_values: Значения EMA
            price: Текущая цена

        Returns:
            int: Количество сгенерированных уведомлений
        """
        # TODO: Реализовать EMA сигналы
        return 0

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Получить статистику обработки.

        Returns:
            Dict: Статистика
        """
        return {
            **self.stats,
            "success_rate": (
                                    (self.stats["processed_updates"] - self.stats["errors"]) /
                                    max(1, self.stats["processed_updates"])
                            ) * 100 if self.stats["processed_updates"] > 0 else 0
        }

    def reset_stats(self) -> None:
        """Сбросить статистику."""
        self.stats = {
            "processed_updates": 0,
            "generated_signals": 0,
            "sent_notifications": 0,
            "errors": 0
        }

        self.logger.info("Processing stats reset")


# Глобальный экземпляр агрегатора
signal_aggregator = SignalAggregator()