"""
Путь: src/services/cache/indicator_cache.py
Описание: Сервис для кеширования данных индикаторов в Redis
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import redis.asyncio as redis
from data.redis_client import get_redis_client
from utils.logger import get_logger
from utils.constants import CACHE_TTL, BINANCE_TIMEFRAMES
from utils.exceptions import CacheError, ValidationError


class IndicatorCache:
    """
    Сервис для кеширования данных индикаторов в Redis.

    Структура кеша:
    rsi:{symbol}:{timeframe}:{period} -> float (значение RSI)
    ema:{symbol}:{timeframe}:{period} -> float (значение EMA)
    indicators_meta:{symbol}:{timeframe} -> dict (метаданные)
    """

    def __init__(self):
        """Инициализация кеша индикаторов."""
        self.redis_client = None
        self.logger = get_logger(__name__)

    async def initialize(self) -> None:
        """Инициализировать подключение к Redis."""
        if not self.redis_client:
            self.redis_client = get_redis_client()
            self.logger.info("Indicator cache initialized")

    async def get_rsi(
            self,
            symbol: str,
            timeframe: str,
            period: int = 14
    ) -> Optional[float]:
        """
        Получить значение RSI из кеша.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            period: Период RSI

        Returns:
            Optional[float]: Значение RSI или None
        """
        await self.initialize()

        cache_key = self._get_rsi_key(symbol, timeframe, period)

        try:
            cached_value = await self.redis_client.get(cache_key)

            if cached_value is None:
                self.logger.debug(
                    "Cache miss for RSI",
                    symbol=symbol,
                    timeframe=timeframe,
                    period=period
                )
                return None

            rsi_value = float(cached_value)

            self.logger.debug(
                "Cache hit for RSI",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                value=rsi_value
            )

            return rsi_value

        except Exception as e:
            self.logger.error(
                "Error getting RSI from cache",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                error=str(e)
            )
            return None

    async def set_rsi(
            self,
            symbol: str,
            timeframe: str,
            period: int,
            value: float
    ) -> bool:
        """
        Сохранить значение RSI в кеш.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            period: Период RSI
            value: Значение RSI

        Returns:
            bool: True если успешно сохранено
        """
        await self.initialize()

        cache_key = self._get_rsi_key(symbol, timeframe, period)

        try:
            # Сохраняем с TTL
            ttl = CACHE_TTL.get("indicators", 3600)
            await self.redis_client.setex(cache_key, ttl, str(value))

            self.logger.debug(
                "RSI cached successfully",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                value=value
            )

            return True

        except Exception as e:
            self.logger.error(
                "Error caching RSI",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                error=str(e)
            )
            return False

    async def get_ema(
            self,
            symbol: str,
            timeframe: str,
            period: int
    ) -> Optional[float]:
        """
        Получить значение EMA из кеша.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            period: Период EMA

        Returns:
            Optional[float]: Значение EMA или None
        """
        await self.initialize()

        cache_key = self._get_ema_key(symbol, timeframe, period)

        try:
            cached_value = await self.redis_client.get(cache_key)

            if cached_value is None:
                return None

            return float(cached_value)

        except Exception as e:
            self.logger.error(
                "Error getting EMA from cache",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                error=str(e)
            )
            return None

    async def set_ema(
            self,
            symbol: str,
            timeframe: str,
            period: int,
            value: float
    ) -> bool:
        """
        Сохранить значение EMA в кеш.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            period: Период EMA
            value: Значение EMA

        Returns:
            bool: True если успешно сохранено
        """
        await self.initialize()

        cache_key = self._get_ema_key(symbol, timeframe, period)

        try:
            ttl = CACHE_TTL.get("indicators", 3600)
            await self.redis_client.setex(cache_key, ttl, str(value))

            self.logger.debug(
                "EMA cached successfully",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                value=value
            )

            return True

        except Exception as e:
            self.logger.error(
                "Error caching EMA",
                symbol=symbol,
                timeframe=timeframe,
                period=period,
                error=str(e)
            )
            return False

    async def invalidate_indicators(
            self,
            symbol: str,
            timeframe: Optional[str] = None
    ) -> bool:
        """
        Очистить кеш индикаторов для символа.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм (None = все таймфреймы)

        Returns:
            bool: True если успешно очищено
        """
        await self.initialize()

        try:
            # Формируем паттерны для поиска ключей
            if timeframe:
                patterns = [
                    f"rsi:{symbol.upper()}:{timeframe}:*",
                    f"ema:{symbol.upper()}:{timeframe}:*"
                ]
            else:
                patterns = [
                    f"rsi:{symbol.upper()}:*",
                    f"ema:{symbol.upper()}:*"
                ]

            keys_to_delete = []
            for pattern in patterns:
                keys = await self.redis_client.keys(pattern)
                keys_to_delete.extend(keys)

            if keys_to_delete:
                deleted_count = await self.redis_client.delete(*keys_to_delete)

                self.logger.info(
                    "Indicators cache invalidated",
                    symbol=symbol,
                    timeframe=timeframe or "all",
                    deleted_keys=deleted_count
                )

            return True

        except Exception as e:
            self.logger.error(
                "Error invalidating indicators cache",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return False

    async def get_all_rsi_values(
            self,
            symbol: str,
            timeframes: List[str],
            period: int = 14
    ) -> Dict[str, Optional[float]]:
        """
        Получить значения RSI для всех таймфреймов.

        Args:
            symbol: Символ торговой пары
            timeframes: Список таймфреймов
            period: Период RSI

        Returns:
            Dict[str, Optional[float]]: Словарь значений RSI
        """
        await self.initialize()

        results = {}

        for timeframe in timeframes:
            try:
                rsi_value = await self.get_rsi(symbol, timeframe, period)
                results[timeframe] = rsi_value
            except Exception as e:
                self.logger.error(
                    "Error getting RSI for timeframe",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )
                results[timeframe] = None

        return results

    async def cache_multiple_rsi(
            self,
            symbol: str,
            rsi_data: Dict[str, float],
            period: int = 14
    ) -> bool:
        """
        Кешировать несколько значений RSI одновременно.

        Args:
            symbol: Символ торговой пары
            rsi_data: Словарь {timeframe: rsi_value}
            period: Период RSI

        Returns:
            bool: True если все значения сохранены успешно
        """
        await self.initialize()

        success_count = 0
        total_count = len(rsi_data)

        for timeframe, rsi_value in rsi_data.items():
            try:
                success = await self.set_rsi(symbol, timeframe, period, rsi_value)
                if success:
                    success_count += 1
            except Exception as e:
                self.logger.error(
                    "Error caching RSI for timeframe",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )

        self.logger.info(
            "Multiple RSI values cached",
            symbol=symbol,
            success_count=success_count,
            total_count=total_count
        )

        return success_count == total_count

    def _get_rsi_key(self, symbol: str, timeframe: str, period: int) -> str:
        """Получить ключ для RSI."""
        return f"rsi:{symbol.upper()}:{timeframe}:{period}"

    def _get_ema_key(self, symbol: str, timeframe: str, period: int) -> str:
        """Получить ключ для EMA."""
        return f"ema:{symbol.upper()}:{timeframe}:{period}"

    def _get_meta_key(self, symbol: str, timeframe: str) -> str:
        """Получить ключ для метаданных."""
        return f"indicators_meta:{symbol.upper()}:{timeframe}"


# Глобальный экземпляр кеша
indicator_cache = IndicatorCache()