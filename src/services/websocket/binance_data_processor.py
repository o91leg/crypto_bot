"""
Путь: src/services/websocket/binance_data_processor.py
Описание: Обработчик данных от Binance WebSocket для интеграции с системой сигналов
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from data.database import get_session
from services.signals.signal_aggregator import signal_aggregator
from services.cache.candle_cache import candle_cache
from utils.logger import get_logger
from utils.exceptions import BinanceDataError, SignalError


class BinanceDataProcessor:
    """
    Обработчик данных от Binance WebSocket.

    Принимает сообщения от WebSocket и передает их в систему сигналов.
    """

    def __init__(self):
        """Инициализация обработчика."""
        self.logger = get_logger(__name__)
        self.processed_messages = 0
        self.processing_errors = 0

    async def process_websocket_message(self, message: Dict[str, Any]) -> None:
        """
        Обработать сообщение от WebSocket.

        Args:
            message: Сообщение от Binance WebSocket
        """
        try:
            stream_name = message.get("stream", "")
            data = message.get("data", {})

            if not stream_name or not data:
                self.logger.warning("Invalid message format", message=message)
                return

            # Определяем тип потока
            if "@kline_" in stream_name:
                await self._process_kline_message(stream_name, data)
            elif "@ticker" in stream_name:
                await self._process_ticker_message(stream_name, data)
            else:
                self.logger.debug("Unsupported stream type", stream=stream_name)

            self.processed_messages += 1

        except Exception as e:
            self.processing_errors += 1
            self.logger.error(
                "Error processing WebSocket message",
                error=str(e),
                message=message
            )

    async def _process_kline_message(self, stream_name: str, data: Dict[str, Any]) -> None:
        """
        Обработать kline сообщение.

        Args:
            stream_name: Название потока
            data: Данные kline
        """
        try:
            kline_data = data.get("k", {})

            if not kline_data:
                self.logger.warning("Empty kline data", stream=stream_name)
                return

            # Извлекаем информацию
            symbol = kline_data.get("s")  # BTCUSDT
            timeframe = kline_data.get("i")  # 1h
            is_closed = kline_data.get("x", False)  # Закрыта ли свеча

            if not symbol or not timeframe:
                self.logger.warning(
                    "Missing symbol or timeframe",
                    symbol=symbol,
                    timeframe=timeframe,
                    stream=stream_name
                )
                return

            # Подготавливаем данные свечи
            candle_data = {
                "open_time": int(kline_data.get("t", 0)),
                "close_time": int(kline_data.get("T", 0)),
                "open_price": kline_data.get("o", "0"),
                "high_price": kline_data.get("h", "0"),
                "low_price": kline_data.get("l", "0"),
                "close_price": kline_data.get("c", "0"),
                "volume": kline_data.get("v", "0")
            }

            # Всегда обновляем кеш
            if is_closed:
                await candle_cache.add_new_candle(symbol, timeframe, candle_data)
            else:
                await candle_cache.update_last_candle(symbol, timeframe, candle_data)

            # Отправляем в систему сигналов только закрытые свечи
            if is_closed:
                await self._process_closed_candle(symbol, timeframe, candle_data)

        except Exception as e:
            self.logger.error(
                "Error processing kline message",
                stream=stream_name,
                error=str(e)
            )

    async def _process_closed_candle(
            self,
            symbol: str,
            timeframe: str,
            candle_data: Dict[str, Any]
    ) -> None:
        """
        Обработать закрытую свечу через систему сигналов.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle_data: Данные свечи
        """
        try:
            # Получаем сессию БД
            async with get_session() as session:
                result = await signal_aggregator.process_candle_update(
                    session=session,
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_data=candle_data,
                    is_closed=True
                )

                if result["total_notifications"] > 0:
                    self.logger.info(
                        "Signals generated from WebSocket",
                        symbol=symbol,
                        timeframe=timeframe,
                        rsi_notifications=result["rsi_notifications"],
                        ema_notifications=result["ema_notifications"],
                        total_notifications=result["total_notifications"]
                    )

        except Exception as e:
            self.logger.error(
                "Error processing closed candle through signal system",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )

    async def _process_ticker_message(self, stream_name: str, data: Dict[str, Any]) -> None:
        """
        Обработать ticker сообщение (пока заглушка).

        Args:
            stream_name: Название потока
            data: Данные ticker
        """
        # TODO: Реализовать обработку ticker данных если нужно
        pass

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Получить статистику обработки.

        Returns:
            Dict: Статистика обработки
        """
        return {
            "processed_messages": self.processed_messages,
            "processing_errors": self.processing_errors,
            "success_rate": (
                                    (self.processed_messages - self.processing_errors) /
                                    max(1, self.processed_messages)
                            ) * 100 if self.processed_messages > 0 else 0
        }


# Глобальный экземпляр обработчика
binance_data_processor = BinanceDataProcessor()