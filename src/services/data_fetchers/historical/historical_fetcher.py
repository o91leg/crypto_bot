"""
Путь: src/services/data_fetchers/historical/historical_fetcher.py
Описание: Основной класс для загрузки исторических данных OHLCV с Binance
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from config.binance_config import get_binance_config
from utils.exceptions import BinanceRateLimitError
from utils.validators import validate_timeframe
from utils.logger import LoggerMixin
from .historical_api_client import HistoricalAPIClient
from .historical_data_processor import HistoricalDataProcessor

# Настройка логирования
logger = structlog.get_logger(__name__)


class HistoricalDataFetcher(LoggerMixin):
    """
    Сервис для загрузки исторических данных свечей с Binance.

    Отвечает за:
    - Координацию загрузки исторических kline данных
    - Управление пакетной обработкой
    - Статистику загрузки
    - Обработку ошибок высокого уровня
    """

    def __init__(self):
        """Инициализация загрузчика исторических данных."""
        self.config = get_binance_config()

        # Компоненты
        self.api_client = HistoricalAPIClient()
        self.data_processor = HistoricalDataProcessor()

        # Статистика загрузки
        self.total_requests = 0
        self.total_candles_loaded = 0
        self.failed_requests = 0

        self.logger.info("HistoricalDataFetcher initialized")

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        await self.api_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)

    async def fetch_pair_historical_data(
            self,
            session: AsyncSession,
            pair_id: int,
            symbol: str,
            timeframes: List[str],
            limit: int = None
    ) -> int:
        """
        Загрузить исторические данные для торговой пары на всех таймфреймах.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары в БД
            symbol: Символ торговой пары (например, BTCUSDT)
            timeframes: Список таймфреймов для загрузки
            limit: Максимальное количество свечей на таймфрейм

        Returns:
            int: Общее количество загруженных свечей
        """
        if limit is None:
            limit = self.config.historical_data_limit

        self.logger.info(
            "Starting historical data fetch for pair",
            symbol=symbol,
            timeframes=timeframes,
            limit=limit
        )

        total_candles = 0

        for timeframe in timeframes:
            try:
                # Валидируем таймфрейм
                is_valid, error_msg = validate_timeframe(timeframe)
                if not is_valid:
                    self.logger.error(
                        "Invalid timeframe",
                        timeframe=timeframe,
                        error=error_msg
                    )
                    continue

                # Загружаем данные для таймфрейма
                candles_count = await self.fetch_timeframe_data(
                    session=session,
                    pair_id=pair_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit
                )

                total_candles += candles_count

                self.logger.info(
                    "Timeframe data loaded",
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=candles_count
                )

                # Небольшая пауза между запросами для избежания rate limit
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(
                    "Error loading timeframe data",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )
                self.failed_requests += 1

        self.logger.info(
            "Historical data fetch completed",
            symbol=symbol,
            total_candles=total_candles,
            timeframes_count=len(timeframes)
        )

        return total_candles

    async def fetch_timeframe_data(
            self,
            session: AsyncSession,
            pair_id: int,
            symbol: str,
            timeframe: str,
            limit: int = 500,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None
    ) -> int:
        """
        Загрузить исторические данные для конкретного таймфрейма.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            symbol: Символ пары
            timeframe: Таймфрейм (например, 1h)
            limit: Максимальное количество свечей
            start_time: Начальное время (Unix timestamp в мс)
            end_time: Конечное время (Unix timestamp в мс)

        Returns:
            int: Количество загруженных свечей
        """
        from utils.time_helpers import get_current_timestamp, get_historical_time_range

        # Если временной диапазон не указан, используем последние данные
        if start_time is None or end_time is None:
            end_time = get_current_timestamp()
            start_time, end_time = get_historical_time_range(timeframe, limit, end_time)

        total_loaded = 0
        current_start = start_time

        while current_start < end_time and total_loaded < limit:
            try:
                # Определяем размер пакета (не более 1000 - лимит Binance)
                batch_limit = min(
                    self.config.max_candles_per_request,
                    limit - total_loaded
                )

                # Загружаем пакет данных через API клиент
                klines = await self.api_client.fetch_klines_batch(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=current_start,
                    end_time=end_time,
                    limit=batch_limit
                )

                if not klines:
                    self.logger.info(
                        "No more data available",
                        symbol=symbol,
                        timeframe=timeframe,
                        start_time=current_start
                    )
                    break

                # Обрабатываем и сохраняем свечи в базу данных
                saved_count = await self.data_processor.save_candles_to_db(
                    session=session,
                    pair_id=pair_id,
                    timeframe=timeframe,
                    klines=klines
                )

                total_loaded += saved_count
                self.total_candles_loaded += saved_count
                self.total_requests += 1

                # Обновляем время для следующего пакета
                if klines:
                    last_kline = klines[-1]
                    current_start = int(last_kline[6]) + 1  # close_time + 1ms

                self.logger.debug(
                    "Batch processed",
                    symbol=symbol,
                    timeframe=timeframe,
                    batch_size=len(klines),
                    saved=saved_count,
                    total_loaded=total_loaded
                )

                # Пауза между запросами
                await asyncio.sleep(0.1)

            except BinanceRateLimitError as e:
                self.logger.warning(
                    "Rate limit hit, waiting",
                    retry_after=e.details.get("retry_after", 60)
                )
                await asyncio.sleep(e.details.get("retry_after", 60))
                continue

            except Exception as e:
                self.logger.error(
                    "Error in batch processing",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e)
                )
                self.failed_requests += 1
                break

        return total_loaded

    async def fetch_recent_candles(
            self,
            session: AsyncSession,
            pair_id: int,
            symbol: str,
            timeframe: str,
            limit: int = 100
    ) -> int:
        """
        Загрузить последние свечи для обновления данных.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            symbol: Символ пары
            timeframe: Таймфрейм
            limit: Количество последних свечей

        Returns:
            int: Количество загруженных свечей
        """
        from data.models.candle_model import Candle

        self.logger.info(
            "Fetching recent candles",
            symbol=symbol,
            timeframe=timeframe,
            limit=limit
        )

        try:
            # Получаем последнюю свечу из БД
            last_candle = await Candle.get_latest_candle(session, pair_id, timeframe)

            start_time = None
            if last_candle:
                # Начинаем с момента после последней свечи
                start_time = last_candle.close_time + 1

            # Загружаем новые данные
            return await self.fetch_timeframe_data(
                session=session,
                pair_id=pair_id,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                start_time=start_time
            )

        except Exception as e:
            self.logger.error(
                "Error fetching recent candles",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return 0

    def get_statistics(self) -> dict:
        """
        Получить статистику загрузки.

        Returns:
            dict: Статистика загрузки
        """
        return {
            "total_requests": self.total_requests,
            "total_candles_loaded": self.total_candles_loaded,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            )
        }

    def reset_statistics(self) -> None:
        """Сбросить статистику загрузки."""
        self.total_requests = 0
        self.total_candles_loaded = 0
        self.failed_requests = 0