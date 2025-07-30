"""
Путь: src/services/websocket/binance_websocket.py
Описание: Основной WebSocket клиент для подключения к Binance Kline потокам
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
import structlog

from config.binance_config import get_binance_config
from utils.exceptions import (
    WebSocketConnectionError,
    WebSocketReconnectError,
    BinanceAPIError,
    BinanceDataError
)
from utils.validators import validate_binance_kline_data
from utils.logger import LoggerMixin

# Настройка логирования
logger = structlog.get_logger(__name__)


class ConnectionState(Enum):
    """Состояния WebSocket соединения."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class BinanceWebSocketClient(LoggerMixin):
    """
    WebSocket клиент для подключения к Binance Stream API.

    Поддерживает:
    - Автоматическое переподключение
    - Управление подписками на потоки
    - Обработку ping/pong
    - Обработку ошибок соединения
    """

    def __init__(self,
                 message_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
                 error_handler: Optional[Callable[[Exception], None]] = None):
        """
        Инициализация WebSocket клиента.

        Args:
            message_handler: Обработчик входящих сообщений
            error_handler: Обработчик ошибок
        """
        self.config = get_binance_config()

        # Обработчики событий
        self.message_handler = message_handler
        self.error_handler = error_handler

        # Состояние соединения
        self.state = ConnectionState.DISCONNECTED
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connection_id: Optional[str] = None

        # Управление подписками
        self.subscribed_streams: Set[str] = set()
        self.pending_subscriptions: Set[str] = set()

        # Переподключение
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = self.config.max_reconnect_attempts
        self.reconnect_delay = self.config.reconnect_delay
        self.backoff_multiplier = self.config.backoff_multiplier
        self.max_reconnect_delay = self.config.max_reconnect_delay

        # Мониторинг соединения
        self.last_ping_time = 0
        self.last_pong_time = 0
        self.ping_interval = self.config.ping_interval
        self.ping_timeout = self.config.ping_timeout

        # Статистика
        self.messages_received = 0
        self.messages_sent = 0
        self.connection_start_time: Optional[float] = None
        self.last_message_time: Optional[float] = None

        # Задачи asyncio
        self.connection_task: Optional[asyncio.Task] = None
        self.ping_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None

        self.logger.info("BinanceWebSocketClient initialized")

    async def connect(self) -> bool:
        """
        Установить соединение с Binance WebSocket API.

        Returns:
            bool: True если соединение установлено успешно
        """
        if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            self.logger.warning("Already connected or connecting")
            return True

        self.state = ConnectionState.CONNECTING
        self.logger.info("Connecting to Binance WebSocket", url=self.config.websocket_url)

        try:
            # Устанавливаем соединение
            self.websocket = await websockets.connect(
                self.config.websocket_url,
                ping_interval=None,  # Отключаем автоматический ping
                ping_timeout=None,
                close_timeout=self.config.close_timeout,
                compression=None  # Отключаем сжатие для производительности
            )

            # Генерируем уникальный ID соединения
            self.connection_id = f"binance_{int(time.time())}"
            self.connection_start_time = time.time()
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0

            self.logger.info(
                "WebSocket connected successfully",
                connection_id=self.connection_id,
                remote_address=self.websocket.remote_address
            )

            # Запускаем фоновые задачи
            await self._start_background_tasks()

            # Восстанавливаем подписки если есть
            if self.subscribed_streams:
                await self._resubscribe_streams()

            return True

        except Exception as e:
            self.state = ConnectionState.DISCONNECTED
            self.logger.error("Failed to connect to WebSocket", error=str(e))

            if self.error_handler:
                await self._safe_call_error_handler(e)

            raise WebSocketConnectionError(self.config.websocket_url, str(e))

    async def disconnect(self) -> None:
        """Корректно закрыть WebSocket соединение."""
        if self.state == ConnectionState.CLOSED:
            return

        self.logger.info("Disconnecting WebSocket", connection_id=self.connection_id)
        self.state = ConnectionState.CLOSED

        # Останавливаем фоновые задачи
        await self._stop_background_tasks()

        # Закрываем WebSocket соединение
        if self.websocket and getattr(self.websocket, "close_code", None) is None:
            try:
                await self.websocket.close()
            except Exception as e:
                self.logger.error("Error closing WebSocket", error=str(e))

        # Очищаем состояние
        self.websocket = None
        self.connection_id = None
        self.subscribed_streams.clear()
        self.pending_subscriptions.clear()

        self.logger.info("WebSocket disconnected")

    async def subscribe_to_stream(self, stream_name: str) -> bool:
        """
        Подписаться на поток данных.

        Args:
            stream_name: Название потока (например, "btcusdt@kline_1m")

        Returns:
            bool: True если подписка успешна
        """
        if not stream_name:
            self.logger.error("Stream name cannot be empty")
            return False

        self.logger.info("Subscribing to stream", stream=stream_name)

        # Добавляем в список подписок
        self.subscribed_streams.add(stream_name)

        if self.state != ConnectionState.CONNECTED:
            self.logger.warning("Not connected, stream will be subscribed on reconnect", stream=stream_name)
            return True

        try:
            # Формируем сообщение подписки
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": int(time.time() * 1000)
            }

            # Отправляем подписку
            await self._send_message(subscribe_message)
            self.pending_subscriptions.add(stream_name)

            self.logger.info("Stream subscription sent", stream=stream_name)
            return True

        except Exception as e:
            self.logger.error("Failed to subscribe to stream", stream=stream_name, error=str(e))
            self.subscribed_streams.discard(stream_name)
            return False

    async def unsubscribe_from_stream(self, stream_name: str) -> bool:
        """
        Отписаться от потока данных.

        Args:
            stream_name: Название потока

        Returns:
            bool: True если отписка успешна
        """
        if stream_name not in self.subscribed_streams:
            self.logger.warning("Not subscribed to stream", stream=stream_name)
            return True

        self.logger.info("Unsubscribing from stream", stream=stream_name)

        # Удаляем из списка подписок
        self.subscribed_streams.discard(stream_name)
        self.pending_subscriptions.discard(stream_name)

        if self.state != ConnectionState.CONNECTED:
            self.logger.info("Not connected, stream removed from subscriptions", stream=stream_name)
            return True

        try:
            # Формируем сообщение отписки
            unsubscribe_message = {
                "method": "UNSUBSCRIBE",
                "params": [stream_name],
                "id": int(time.time() * 1000)
            }

            # Отправляем отписку
            await self._send_message(unsubscribe_message)

            self.logger.info("Stream unsubscription sent", stream=stream_name)
            return True

        except Exception as e:
            self.logger.error("Failed to unsubscribe from stream", stream=stream_name, error=str(e))
            return False

    async def subscribe_to_multiple_streams(self, stream_names: List[str]) -> Dict[str, bool]:
        """
        Подписаться на несколько потоков одновременно.

        Args:
            stream_names: Список названий потоков

        Returns:
            Dict[str, bool]: Результат подписки для каждого потока
        """
        if not stream_names:
            return {}

        self.logger.info("Subscribing to multiple streams", count=len(stream_names))

        results = {}

        if self.state != ConnectionState.CONNECTED:
            # Если не подключены, просто добавляем в список подписок
            for stream_name in stream_names:
                self.subscribed_streams.add(stream_name)
                results[stream_name] = True
            return results

        try:
            # Формируем сообщение подписки на множественные потоки
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": stream_names,
                "id": int(time.time() * 1000)
            }

            # Отправляем подписку
            await self._send_message(subscribe_message)

            # Обновляем состояние
            for stream_name in stream_names:
                self.subscribed_streams.add(stream_name)
                self.pending_subscriptions.add(stream_name)
                results[stream_name] = True

            self.logger.info("Multiple streams subscription sent", count=len(stream_names))
            return results

        except Exception as e:
            self.logger.error("Failed to subscribe to multiple streams", error=str(e))
            return {stream_name: False for stream_name in stream_names}

    async def start_listening(self) -> None:
        """
        Запустить прослушивание сообщений WebSocket.
        Эта функция блокирующая и должна запускаться в отдельной задаче.
        """
        if not self.websocket:
            raise WebSocketConnectionError(self.config.websocket_url, "Not connected")

        self.logger.info("Starting WebSocket message listening")

        try:
            async for message in self.websocket:
                await self._handle_message(message)

        except ConnectionClosed as e:
            self.logger.warning("WebSocket connection closed", code=e.code, reason=e.reason)
            self.state = ConnectionState.DISCONNECTED

            # Пытаемся переподключиться
            if self.websocket and getattr(self.websocket, "close_code", None) is None:
                await self._handle_reconnection()

        except WebSocketException as e:
            self.logger.error("WebSocket exception occurred", error=str(e))
            self.state = ConnectionState.DISCONNECTED
            await self._handle_reconnection()

        except Exception as e:
            self.logger.error("Unexpected error in message listening", error=str(e), exc_info=True)
            self.state = ConnectionState.DISCONNECTED

            if self.error_handler:
                await self._safe_call_error_handler(e)

    async def get_connection_stats(self) -> Dict[str, Any]:
        """
        Получить статистику соединения.

        Returns:
            Dict[str, Any]: Статистика соединения
        """
        uptime = None
        if self.connection_start_time:
            uptime = time.time() - self.connection_start_time

        return {
            "state": self.state.value,
            "connection_id": self.connection_id,
            "subscribed_streams": list(self.subscribed_streams),
            "pending_subscriptions": list(self.pending_subscriptions),
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "reconnect_attempts": self.reconnect_attempts,
            "uptime_seconds": round(uptime) if uptime else None,
            "last_message_time": self.last_message_time,
            "last_ping_time": self.last_ping_time,
            "last_pong_time": self.last_pong_time,
            "is_connected": self.is_connected(),
        }

    def is_connected(self) -> bool:
        """
        Проверить, установлено ли соединение.

        Returns:
            bool: True если соединение активно
        """
        return (
            self.state == ConnectionState.CONNECTED
            and self.websocket is not None
            and getattr(self.websocket, "close_code", None) is None
        )

    async def _send_message(self, message: Dict[str, Any]) -> None:
        """
        Отправить сообщение через WebSocket.

        Args:
            message: Сообщение для отправки
        """
        if not self.websocket or getattr(self.websocket, "close_code", None) is not None:
            raise WebSocketConnectionError(self.config.websocket_url, "WebSocket not connected")

        try:
            message_json = json.dumps(message)
            await self.websocket.send(message_json)
            self.messages_sent += 1

            self.logger.debug("Message sent", message_type=message.get("method", "data"))

        except Exception as e:
            self.logger.error("Failed to send message", error=str(e))
            raise

    async def _handle_message(self, raw_message: str) -> None:
        """
        Обработать входящее сообщение.

        Args:
            raw_message: Сырое сообщение от WebSocket
        """
        try:
            # Парсим JSON
            message = json.loads(raw_message)
            self.messages_received += 1
            self.last_message_time = time.time()

            # Определяем тип сообщения
            if "stream" in message and "data" in message:
                # Сообщение с данными потока
                await self._handle_stream_message(message)

            elif "id" in message and "result" in message:
                # Ответ на команду управления
                await self._handle_control_response(message)

            elif "error" in message:
                # Ошибка от сервера
                await self._handle_error_message(message)

            else:
                # Неизвестный тип сообщения
                self.logger.warning("Unknown message format", message=message)

        except json.JSONDecodeError as e:
            self.logger.error("Failed to decode JSON message", error=str(e), raw_message=raw_message[:200])

        except Exception as e:
            self.logger.error("Error handling message", error=str(e), exc_info=True)

    async def _handle_stream_message(self, message: Dict[str, Any]) -> None:
        """
        Обработать сообщение с данными потока.

        Args:
            message: Сообщение с данными потока
        """
        stream_name = message.get("stream")
        data = message.get("data", {})

        if not stream_name:
            self.logger.warning("Stream message without stream name", message=message)
            return

        # Валидируем данные для kline потоков
        if "@kline_" in stream_name:
            kline_data = data.get("k", {})
            is_valid, error_msg = validate_binance_kline_data(kline_data)

            if not is_valid:
                self.logger.error(
                    "Invalid kline data received",
                    stream=stream_name,
                    error=error_msg,
                    data=kline_data
                )
                raise BinanceDataError(stream_name.split('@')[0], stream_name, error_msg)

        # Передаем сообщение обработчику
        if self.message_handler:
            try:
                await self._safe_call_message_handler(message)
            except Exception as e:
                self.logger.error("Error in message handler", stream=stream_name, error=str(e))

        self.logger.debug("Stream message processed", stream=stream_name)

    async def _handle_control_response(self, message: Dict[str, Any]) -> None:
        """
        Обработать ответ на команду управления.

        Args:
            message: Ответ на команду
        """
        request_id = message.get("id")
        result = message.get("result")

        if result is None:
            self.logger.info("Control command executed", request_id=request_id, result=result)
        else:
            self.logger.warning("Control command failed", request_id=request_id, result=result)

    async def _handle_error_message(self, message: Dict[str, Any]) -> None:
        """
        Обработать сообщение об ошибке.

        Args:
            message: Сообщение об ошибке
        """
        error = message.get("error", {})
        error_code = error.get("code")
        error_msg = error.get("msg", "Unknown error")

        self.logger.error("Server error received", code=error_code, message=error_msg)

        # Создаем исключение
        exception = BinanceAPIError(f"Server error {error_code}: {error_msg}")

        if self.error_handler:
            await self._safe_call_error_handler(exception)

    async def _handle_reconnection(self) -> None:
        """Обработать переподключение при разрыве соединения."""
        if self.state == ConnectionState.CLOSED:
            return  # Клиент был явно закрыт

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached, giving up")
            self.state = ConnectionState.CLOSED

            exception = WebSocketReconnectError(self.reconnect_attempts, self.max_reconnect_attempts)
            if self.error_handler:
                await self._safe_call_error_handler(exception)
            return

        self.state = ConnectionState.RECONNECTING
        self.reconnect_attempts += 1

        # Рассчитываем задержку с экспоненциальным backoff
        delay = min(
            self.reconnect_delay * (self.backoff_multiplier ** (self.reconnect_attempts - 1)),
            self.max_reconnect_delay
        )

        self.logger.info(
            "Attempting to reconnect",
            attempt=self.reconnect_attempts,
            max_attempts=self.max_reconnect_attempts,
            delay_seconds=delay
        )

        # Ждем перед переподключением
        await asyncio.sleep(delay)

        try:
            # Пытаемся переподключиться
            await self.connect()
            self.logger.info("Reconnection successful")

        except Exception as e:
            self.logger.error("Reconnection failed", error=str(e))
            # Повторяем попытку
            await self._handle_reconnection()

    async def _resubscribe_streams(self) -> None:
        """Восстановить подписки после переподключения."""
        if not self.subscribed_streams:
            return

        self.logger.info("Resubscribing to streams", count=len(self.subscribed_streams))

        try:
            # Подписываемся на все потоки одним сообщением
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": list(self.subscribed_streams),
                "id": int(time.time() * 1000)
            }

            await self._send_message(subscribe_message)
            self.pending_subscriptions.update(self.subscribed_streams)

            self.logger.info("Stream resubscription completed")

        except Exception as e:
            self.logger.error("Failed to resubscribe to streams", error=str(e))

    async def _start_background_tasks(self) -> None:
        """Запустить фоновые задачи."""
        # Задача для ping/pong
        self.ping_task = asyncio.create_task(self._ping_loop())

        # Задача для проверки здоровья соединения
        self.health_check_task = asyncio.create_task(self._health_check_loop())

        self.logger.debug("Background tasks started")

    async def _stop_background_tasks(self) -> None:
        """Остановить фоновые задачи."""
        tasks = [self.ping_task, self.health_check_task, self.connection_task]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.ping_task = None
        self.health_check_task = None
        self.connection_task = None

        self.logger.debug("Background tasks stopped")

    async def _ping_loop(self) -> None:
        """Цикл отправки ping сообщений."""
        while self.state == ConnectionState.CONNECTED:
            try:
                if self.websocket and getattr(self.websocket, "close_code", None) is None:
                    await self.websocket.ping()
                    self.last_ping_time = time.time()

                await asyncio.sleep(self.ping_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in ping loop", error=str(e))
                break

    async def _health_check_loop(self) -> None:
        """Цикл проверки здоровья соединения."""
        while self.state == ConnectionState.CONNECTED:
            try:
                current_time = time.time()

                # Проверяем, получили ли мы pong на последний ping
                if (self.last_ping_time > 0 and
                        self.last_pong_time < self.last_ping_time and
                        current_time - self.last_ping_time > self.ping_timeout):
                    self.logger.warning("Ping timeout detected, reconnecting")
                    await self._handle_reconnection()
                    break

                # Проверяем, получали ли мы сообщения в последнее время
                if (self.last_message_time and
                        current_time - self.last_message_time > 300):  # 5 минут
                    self.logger.warning("No messages received for 5 minutes")

                await asyncio.sleep(30)  # Проверяем каждые 30 секунд

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in health check loop", error=str(e))
                break

    async def _safe_call_message_handler(self, message: Dict[str, Any]) -> None:
        """Безопасно вызвать обработчик сообщений."""
        try:
            if asyncio.iscoroutinefunction(self.message_handler):
                await self.message_handler(message)
            else:
                self.message_handler(message)
        except Exception as e:
            self.logger.error("Error in message handler", error=str(e), exc_info=True)

    async def _safe_call_error_handler(self, error: Exception) -> None:
        """Безопасно вызвать обработчик ошибок."""
        try:
            if asyncio.iscoroutinefunction(self.error_handler):
                await self.error_handler(error)
            else:
                self.error_handler(error)
        except Exception as e:
            self.logger.error("Error in error handler", error=str(e), exc_info=True)

    # Алиасы для совместимости с тестами
    async def subscribe(self, streams: List[str]) -> bool:
        """
        Подписаться на список потоков (алиас для subscribe_to_multiple_streams).

        Args:
            streams: Список названий потоков

        Returns:
            bool: True если все подписки успешны
        """
        if not streams:
            return True

        results = await self.subscribe_to_multiple_streams(streams)
        return all(results.values())

    async def unsubscribe(self, streams: List[str]) -> bool:
        """
        Отписаться от списка потоков.

        Args:
            streams: Список названий потоков

        Returns:
            bool: True если все отписки успешны
        """
        if not streams:
            return True

        results = []
        for stream_name in streams:
            result = await self.unsubscribe_from_stream(stream_name)
            results.append(result)

        return all(results)

    async def _handle_kline_message(self, message: Dict[str, Any]) -> None:
        """
        Обработать kline сообщение и передать в систему сигналов.

        Args:
            message: Сообщение с kline данными
        """
        try:
            stream_name = message.get("stream", "")
            data = message.get("data", {})
            kline_data = data.get("k", {})

            if not kline_data:
                self.logger.warning("Empty kline data", stream=stream_name)
                return

            # Извлекаем информацию о символе и таймфрейме
            symbol = kline_data.get("s")  # BTCUSDT
            timeframe = kline_data.get("i")  # 1h
            is_closed = kline_data.get("x", False)  # Закрыта ли свеча

            if not symbol or not timeframe:
                self.logger.warning(
                    "Missing symbol or timeframe in kline data",
                    symbol=symbol,
                    timeframe=timeframe
                )
                return

            # Подготавливаем данные свечи для обработки
            candle_data = {
                "open_time": int(kline_data.get("t", 0)),
                "close_time": int(kline_data.get("T", 0)),
                "open_price": kline_data.get("o", "0"),
                "high_price": kline_data.get("h", "0"),
                "low_price": kline_data.get("l", "0"),
                "close_price": kline_data.get("c", "0"),
                "volume": kline_data.get("v", "0")
            }

            # Отправляем в агрегатор сигналов только для закрытых свечей
            if is_closed:
                await self._process_closed_candle(symbol, timeframe, candle_data)
            else:
                # Для незакрытых свечей только обновляем кеш
                await self._update_current_candle(symbol, timeframe, candle_data)

        except Exception as e:
            self.logger.error(
                "Error handling kline message",
                error=str(e),
                message=message
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
            # Импортируем агрегатор сигналов
            from services.signals.signal_aggregator import signal_aggregator
            from data.database import get_session

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
                "Error processing closed candle",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )

    async def _update_current_candle(
            self,
            symbol: str,
            timeframe: str,
            candle_data: Dict[str, Any]
    ) -> None:
        """
        Обновить данные текущей незакрытой свечи в кеше.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            candle_data: Данные свечи
        """
        try:
            from services.cache.candle_cache import candle_cache

            # Обновляем последнюю свечу в кеше
            await candle_cache.update_last_candle(symbol, timeframe, candle_data)

            self.logger.debug(
                "Current candle updated in cache",
                symbol=symbol,
                timeframe=timeframe,
                price=candle_data.get("close_price")
            )

        except Exception as e:
            self.logger.error(
                "Error updating current candle",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )