"""
Путь: src/services/cache/candle_cache.py
Описание: Сервис для кеширования свечных данных в Redis
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from data.redis_client import get_redis_client
from data.models.candle_model import Candle
from utils.logger import get_logger
from utils.constants import CACHE_TTL, BINANCE_TIMEFRAMES
from utils.exceptions import CacheError, ValidationError


class CandleCache:
    """
    Сервис для кеширования свечных данных в Redis.

    Структура кеша:
    candles:{symbol}:{timeframe} -> List[dict] (последние 500 свечей)
    candles_meta:{symbol}:{timeframe} -> dict (метаданные)
    """

    def __init__(self):
        """Инициализация кеша свечей."""
        self.redis_client = None
        self.logger = get_logger(__name__)
        self.max_candles_per_timeframe = 500

    async def initialize(self) -> None:
        """Инициализировать подключение к Redis."""
        if not self.redis_client:
            self.redis_client = get_redis_client()  # Убираем await!
            self.logger.info("Candle cache initialized")

    async def get_candles(
            self,
            symbol: str,
            timeframe: str,
            limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить свечи из кеша.

        Args:
            symbol: Символ торговой пары (например, 'BTCUSDT')
            timeframe: Таймфрейм (например, '1h')
            limit: Максимальное количество свечей (None = все)

        Returns:
            List[Dict]: Список свечей в формате словарей

        Raises:
            CacheError: Ошибка при работе с кешем
            ValidationError: Некорректные параметры
        """
        await self.initialize()

        # Валидация параметров
        if not symbol or not timeframe:
            raise ValidationError("Symbol and timeframe are required")

        if timeframe not in BINANCE_TIMEFRAMES:
            raise ValidationError(f"Invalid timeframe: {timeframe}")

        cache_key = self._get_candles_key(symbol, timeframe)

        try:
            # Получаем данные из Redis
            cached_data = await self.redis_client.get(cache_key)

            if not cached_data:
                self.logger.debug(
                    "Cache miss for candles",
                    symbol=symbol,
                    timeframe=timeframe
                )
                return []

            # Парсим JSON данные
            candles_data = json.loads(cached_data)

            # Применяем лимит если указан
            if limit and limit > 0:
                candles_data = candles_data[-limit:]

            self.logger.debug(
                "Cache hit for candles",
                symbol=symbol,
                timeframe=timeframe,
                count=len(candles_data)
            )

            return candles_data

        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to decode cached candles",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            # Удаляем поврежденные данные
            await self.redis_client.delete(cache_key)
            return []

        except Exception as e:
            self.logger.error(
                "Error getting candles from cache",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise CacheError(f"Failed to get candles from cache: {str(e)}")

    async def set_candles(
            self,
            symbol: str,
            timeframe: str,
            candles: List[Dict[str, Any]]
    ) -> bool:
        """
        Сохранить свечи в кеш.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candles: Список свечей

        Returns:
            bool: True если успешно сохранено

        Raises:
            CacheError: Ошибка при сохранении
            ValidationError: Некорректные данные
        """
        await self.initialize()

        if not symbol or not timeframe:
            raise ValidationError("Symbol and timeframe are required")

        if not isinstance(candles, list):
            raise ValidationError("Candles must be a list")

        cache_key = self._get_candles_key(symbol, timeframe)
        meta_key = self._get_meta_key(symbol, timeframe)

        try:
            # Ограничиваем количество свечей
            if len(candles) > self.max_candles_per_timeframe:
                candles = candles[-self.max_candles_per_timeframe:]

            # Подготавливаем данные для сериализации
            serializable_candles = []
            for candle in candles:
                serializable_candle = self._prepare_candle_for_cache(candle)
                serializable_candles.append(serializable_candle)

            # Сериализуем в JSON
            candles_json = json.dumps(serializable_candles, ensure_ascii=False)

            # Сохраняем в Redis с TTL
            ttl = CACHE_TTL.get("candles", 86400)

            pipeline = self.redis_client.pipeline()
            pipeline.setex(cache_key, ttl, candles_json)

            # Сохраняем метаданные
            meta_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(serializable_candles),
                "updated_at": datetime.now().isoformat(),
                "first_candle_time": serializable_candles[0]["open_time"] if serializable_candles else None,
                "last_candle_time": serializable_candles[-1]["close_time"] if serializable_candles else None
            }

            pipeline.setex(meta_key, ttl, json.dumps(meta_data))

            await pipeline.execute()

            self.logger.debug(
                "Candles cached successfully",
                symbol=symbol,
                timeframe=timeframe,
                count=len(serializable_candles)
            )

            return True

        except Exception as e:
            self.logger.error(
                "Error caching candles",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise CacheError(f"Failed to cache candles: {str(e)}")

    async def add_new_candle(
            self,
            symbol: str,
            timeframe: str,
            candle: Dict[str, Any]
    ) -> bool:
        """
        Добавить новую свечу в конец кеша.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle: Данные новой свечи

        Returns:
            bool: True если успешно добавлено
        """
        await self.initialize()

        try:
            # Получаем текущие данные
            cached_candles = await self.get_candles(symbol, timeframe)

            # Подготавливаем новую свечу
            serializable_candle = self._prepare_candle_for_cache(candle)

            # Добавляем новую свечу в конец
            cached_candles.append(serializable_candle)

            # Ограничиваем размер кеша
            if len(cached_candles) > self.max_candles_per_timeframe:
                cached_candles = cached_candles[-self.max_candles_per_timeframe:]

            # Сохраняем обновленные данные
            return await self.set_candles(symbol, timeframe, cached_candles)

        except Exception as e:
            self.logger.error(
                "Error adding new candle to cache",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return False

    async def update_last_candle(
            self,
            symbol: str,
            timeframe: str,
            candle: Dict[str, Any]
    ) -> bool:
        """
        Обновить последнюю свечу в кеше (для текущей незакрытой свечи).

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle: Обновленные данные свечи

        Returns:
            bool: True если успешно обновлено
        """
        await self.initialize()

        try:
            # Получаем текущие данные
            cached_candles = await self.get_candles(symbol, timeframe)

            if not cached_candles:
                # Если кеш пуст, добавляем как новую свечу
                return await self.add_new_candle(symbol, timeframe, candle)

            # Подготавливаем данные свечи
            serializable_candle = self._prepare_candle_for_cache(candle)

            # Заменяем последнюю свечу
            cached_candles[-1] = serializable_candle

            # Сохраняем обновленные данные
            return await self.set_candles(symbol, timeframe, cached_candles)

        except Exception as e:
            self.logger.error(
                "Error updating last candle in cache",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return False

    async def get_cache_info(
            self,
            symbol: str,
            timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о кешированных данных.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм

        Returns:
            Dict: Метаданные кеша или None если нет данных
        """
        await self.initialize()

        meta_key = self._get_meta_key(symbol, timeframe)

        try:
            cached_meta = await self.redis_client.get(meta_key)

            if not cached_meta:
                return None

            return json.loads(cached_meta)

        except Exception as e:
            self.logger.error(
                "Error getting cache info",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return None

    async def invalidate_cache(
            self,
            symbol: str,
            timeframe: Optional[str] = None
    ) -> bool:
        """
        Очистить кеш для символа и таймфрейма.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм (None = все таймфреймы)

        Returns:
            bool: True если успешно очищено
        """
        await self.initialize()

        try:
            if timeframe:
                # Очищаем конкретный таймфрейм
                keys_to_delete = [
                    self._get_candles_key(symbol, timeframe),
                    self._get_meta_key(symbol, timeframe)
                ]
            else:
                # Очищаем все таймфреймы для символа
                keys_to_delete = []
                for tf in BINANCE_TIMEFRAMES:
                    keys_to_delete.extend([
                        self._get_candles_key(symbol, tf),
                        self._get_meta_key(symbol, tf)
                    ])

            if keys_to_delete:
                deleted_count = await self.redis_client.delete(*keys_to_delete)

                self.logger.info(
                    "Cache invalidated",
                    symbol=symbol,
                    timeframe=timeframe or "all",
                    deleted_keys=deleted_count
                )

            return True

        except Exception as e:
            self.logger.error(
                "Error invalidating cache",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return False

    async def load_from_database(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            limit: Optional[int] = None
    ) -> bool:
        """
        Загрузить данные из БД в кеш.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            limit: Максимальное количество свечей

        Returns:
            bool: True если успешно загружено
        """
        try:
            # Получаем данные из БД
            candles = await Candle.get_candles_for_cache(
                session=session,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit or self.max_candles_per_timeframe
            )

            if not candles:
                self.logger.debug(
                    "No candles found in database",
                    symbol=symbol,
                    timeframe=timeframe
                )
                return False

            # Преобразуем в формат для кеша
            candles_data = []
            for candle in candles:
                candle_dict = {
                    "open_time": candle.open_time,
                    "close_time": candle.close_time,
                    "open_price": str(candle.open_price),
                    "high_price": str(candle.high_price),
                    "low_price": str(candle.low_price),
                    "close_price": str(candle.close_price),
                    "volume": str(candle.volume)
                }
                candles_data.append(candle_dict)

            # Сохраняем в кеш
            success = await self.set_candles(symbol, timeframe, candles_data)

            if success:
                self.logger.info(
                    "Candles loaded from database to cache",
                    symbol=symbol,
                    timeframe=timeframe,
                    count=len(candles_data)
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error loading candles from database",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return False

    def _get_candles_key(self, symbol: str, timeframe: str) -> str:
        """Получить ключ для кеша свечей."""
        return f"candles:{symbol.upper()}:{timeframe}"

    def _get_meta_key(self, symbol: str, timeframe: str) -> str:
        """Получить ключ для метаданных кеша."""
        return f"candles_meta:{symbol.upper()}:{timeframe}"

    def _prepare_candle_for_cache(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Подготовить свечу для сохранения в кеш.

        Преобразует Decimal в строки для JSON сериализации.
        """
        serializable_candle = {}

        for key, value in candle.items():
            if isinstance(value, Decimal):
                serializable_candle[key] = str(value)
            elif isinstance(value, datetime):
                serializable_candle[key] = int(value.timestamp() * 1000)
            else:
                serializable_candle[key] = value

        return serializable_candle


# Глобальный экземпляр кеша
candle_cache = CandleCache()