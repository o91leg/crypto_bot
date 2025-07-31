"""
Путь: src/services/websocket/binance_data_processor.py
Описание: Обработчик данных от Binance WebSocket для интеграции с системой сигналов
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import update

from data.database import get_session as get_async_session
from services.signals.signal_aggregator import signal_aggregator
from services.cache.candle_cache import candle_cache
from utils.logger import get_logger


class BinanceDataProcessor:
    """Обработчик данных от Binance WebSocket."""

    def __init__(self) -> None:
        """Инициализация обработчика."""
        self.logger = get_logger(__name__)
        self.processed_messages = 0
        self.processing_errors = 0

    async def process_websocket_message(self, message: Dict[str, Any]) -> None:
        """Обработать сообщение от WebSocket."""
        try:
            stream_name = message.get("stream", "")
            data = message.get("data", {})

            if not stream_name or not data:
                self.logger.warning("Invalid message format", message=message)
                return

            if "@kline_" in stream_name:
                await self.process_kline_data(data)
            elif "@ticker" in stream_name:
                await self._process_ticker_message(stream_name, data)
            else:
                self.logger.debug("Unsupported stream type", stream=stream_name)

            self.processed_messages += 1

        except Exception as e:  # pragma: no cover - защищает от неожиданных ошибок
            self.processing_errors += 1
            self.logger.error(
                "Error processing WebSocket message",
                error=str(e),
                message=message,
            )

    async def process_kline_data(self, data: Dict[str, Any]) -> None:
        """Обработать данные kline с сохранением в БД и пересчетом индикаторов."""
        try:
            kline = data.get("k", {})
            symbol = kline.get("s", "").upper()
            timeframe = kline.get("i", "")
            is_closed = kline.get("x", False)

            if not is_closed:
                return

            self.logger.debug(f"Processing closed kline: {symbol} {timeframe}")

            async with get_async_session() as session:
                from data.models.pair_model import Pair
                from data.models.candle_model import Candle

                pair = await Pair.get_by_symbol(session, symbol)

                if not pair:
                    self.logger.warning(f"Pair {symbol} not found in database")
                    return

                candle = Candle(
                    pair_id=pair.id,
                    timeframe=timeframe,
                    open_time=int(kline.get("t", 0)),
                    close_time=int(kline.get("T", 0)),
                    open_price=Decimal(kline.get("o", "0")),
                    high_price=Decimal(kline.get("h", "0")),
                    low_price=Decimal(kline.get("l", "0")),
                    close_price=Decimal(kline.get("c", "0")),
                    volume=Decimal(kline.get("v", "0")),
                    quote_volume=Decimal(kline.get("q", "0")),
                    trades_count=int(kline.get("n", 0)),
                    is_closed=True,
                )

                await self.save_candle_safely(session, candle)
                await self.recalculate_indicators(session, pair.id, timeframe)
                await self.check_trading_signals(session, pair, timeframe, candle)

                await session.commit()

                self.logger.info(
                    "Kline processed and indicators updated",
                    symbol=symbol,
                    timeframe=timeframe,
                    price=float(candle.close_price),
                )

        except Exception as e:  # pragma: no cover - защита от неожиданных ошибок
            self.logger.error("Error processing kline data", error=str(e), data=data)

    async def save_candle_safely(self, session, candle) -> None:
        """Безопасно сохранить свечу, избегая дублирования."""
        try:
            from sqlalchemy import select
            from data.models.candle_model import Candle as CandleModel

            existing = await session.execute(
                select(CandleModel).where(
                    CandleModel.pair_id == candle.pair_id,
                    CandleModel.timeframe == candle.timeframe,
                    CandleModel.open_time == candle.open_time,
                )
            )

            if existing.scalar_one_or_none():
                await session.execute(
                    update(CandleModel)
                    .where(
                        CandleModel.pair_id == candle.pair_id,
                        CandleModel.timeframe == candle.timeframe,
                        CandleModel.open_time == candle.open_time,
                    )
                    .values(
                        close_price=candle.close_price,
                        high_price=candle.high_price,
                        low_price=candle.low_price,
                        volume=candle.volume,
                        quote_volume=candle.quote_volume,
                        trades_count=candle.trades_count,
                        is_closed=True,
                    )
                )
            else:
                session.add(candle)

            await session.flush()

        except Exception as e:  # pragma: no cover - ошибки БД логируются
            self.logger.error("Error saving candle", error=str(e))
            await session.rollback()

    async def recalculate_indicators(self, session, pair_id: int, timeframe: str) -> None:
        """Пересчитать индикаторы для пары и таймфрейма."""
        try:
            from data.models.pair_model import Pair
            from data.models.candle_model import Candle
            from sqlalchemy import select

            pair = await session.get(Pair, pair_id)
            if not pair:
                return

            result = await session.execute(
                select(Candle)
                .where(
                    Candle.pair_id == pair_id,
                    Candle.timeframe == timeframe,
                )
                .order_by(Candle.open_time.desc())
                .limit(1)
            )
            last_candle = result.scalar_one_or_none()
            if not last_candle:
                return

            candle_data = {
                "open_time": last_candle.open_time,
                "close_time": last_candle.close_time,
                "open_price": str(last_candle.open_price),
                "high_price": str(last_candle.high_price),
                "low_price": str(last_candle.low_price),
                "close_price": str(last_candle.close_price),
                "volume": str(last_candle.volume),
            }

            await candle_cache.add_new_candle(pair.symbol, timeframe, candle_data)
            await signal_aggregator._calculate_indicators(
                pair.symbol, timeframe, candle_data, True
            )

        except Exception as e:  # pragma: no cover - непредвиденная ошибка индикаторов
            self.logger.error("Error recalculating indicators", error=str(e))

    async def check_trading_signals(self, session, pair, timeframe: str, candle) -> None:
        """Проверить сигналы для уведомлений."""
        try:
            candle_data = {
                "open_time": candle.open_time,
                "close_time": candle.close_time,
                "open_price": str(candle.open_price),
                "high_price": str(candle.high_price),
                "low_price": str(candle.low_price),
                "close_price": str(candle.close_price),
                "volume": str(candle.volume),
            }

            await signal_aggregator.process_candle_update(
                session=session,
                symbol=pair.symbol,
                timeframe=timeframe,
                candle_data=candle_data,
                is_closed=True,
            )

        except Exception as e:  # pragma: no cover - обработка ошибок сигналов
            self.logger.error("Error checking trading signals", error=str(e))

    async def _process_ticker_message(self, stream_name: str, data: Dict[str, Any]) -> None:
        """Обработать ticker сообщение (заглушка)."""
        # TODO: Реализовать обработку ticker данных если нужно
        _ = (stream_name, data)

    def get_processing_stats(self) -> Dict[str, Any]:
        """Получить статистику обработки."""
        success_rate = (
            (self.processed_messages - self.processing_errors)
            / max(1, self.processed_messages)
        ) * 100 if self.processed_messages > 0 else 0

        return {
            "processed_messages": self.processed_messages,
            "processing_errors": self.processing_errors,
            "success_rate": success_rate,
        }


# Глобальный экземпляр обработчика
binance_data_processor = BinanceDataProcessor()

