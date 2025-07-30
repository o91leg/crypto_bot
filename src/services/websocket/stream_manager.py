"""
Путь: src/services/websocket/stream_manager.py
Описание: Менеджер для управления потоками данных WebSocket Binance
Автор: Crypto Bot Team
Дата создания: 2025-07-28
Обновлено: 2025-07-29 - Добавлена интеграция с системой сигналов
"""

import asyncio
from typing import Dict, Set, List, Optional, Callable, Any
from collections import defaultdict
import structlog

from .binance_websocket import BinanceWebSocketClient
from config.binance_config import get_binance_config  # ИСПРАВЛЕН ИМПОРТ - убрал get_kline_stream_name
from utils.exceptions import WebSocketConnectionError, BinanceDataError
from utils.logger import LoggerMixin
from utils.validators import validate_trading_pair_symbol, validate_timeframe

# Настройка логирования
logger = structlog.get_logger(__name__)

def get_kline_stream_name(symbol: str, timeframe: str) -> str:
    """
    Получить имя потока для kline данных.

    Args:
        symbol: Символ торговой пары
        timeframe: Таймфрейм

    Returns:
        str: Имя потока для WebSocket
    """
    return f"{symbol.lower()}@kline_{timeframe}"

def get_ticker_stream_name(symbol: str) -> str:
    """
    Получить имя потока для ticker данных.

    Args:
        symbol: Символ торговой пары

    Returns:
        str: Имя потока для WebSocket
    """
    return f"{symbol.lower()}@ticker"

def get_depth_stream_name(symbol: str, level: str = "5") -> str:
    """
    Получить имя потока для depth данных.

    Args:
        symbol: Символ торговой пары
        level: Уровень глубины (5, 10, 20)

    Returns:
        str: Имя потока для WebSocket
    """
    return f"{symbol.lower()}@depth{level}"

def parse_stream_name(stream_name: str) -> dict:
    """
    Разобрать имя потока на компоненты.

    Args:
        stream_name: Имя потока

    Returns:
        dict: Информация о потоке
    """
    try:
        if '@' not in stream_name:
            return {"valid": False}

        symbol_part, stream_type = stream_name.split('@', 1)
        symbol = symbol_part.upper()

        if stream_type.startswith('kline_'):
            timeframe = stream_type[6:]  # Убираем "kline_"
            return {
                "valid": True,
                "type": "kline",
                "symbol": symbol,
                "timeframe": timeframe
            }
        elif stream_type == 'ticker':
            return {
                "valid": True,
                "type": "ticker",
                "symbol": symbol
            }
        elif stream_type.startswith('depth'):
            level = stream_type[5:] if len(stream_type) > 5 else "5"
            return {
                "valid": True,
                "type": "depth",
                "symbol": symbol,
                "level": level
            }
        else:
            return {"valid": False}

    except Exception:
        return {"valid": False}

class StreamSubscription:
    """Информация о подписке на поток."""

    def __init__(self, symbol: str, timeframe: str, users: Set[int] = None):
        """
        Инициализация подписки.

        Args:
            symbol: Символ торговой пары (например, BTCUSDT)
            timeframe: Таймфрейм (например, 1m)
            users: Множество пользователей, подписанных на поток
        """
        self.symbol = symbol.upper()
        self.timeframe = timeframe.lower()
        self.users = users or set()
        self.stream_name = get_kline_stream_name(self.symbol, self.timeframe)
        self.created_at = asyncio.get_event_loop().time()
        self.last_data_time: Optional[float] = None
        self.message_count = 0

    def add_user(self, user_id: int) -> None:
        """Добавить пользователя к подписке."""
        self.users.add(user_id)

    def remove_user(self, user_id: int) -> bool:
        """
        Удалить пользователя из подписки.

        Returns:
            bool: True если подписка стала пустой
        """
        self.users.discard(user_id)
        return len(self.users) == 0

    def update_stats(self) -> None:
        """Обновить статистику получения данных."""
        self.last_data_time = asyncio.get_event_loop().time()
        self.message_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для отладки."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "stream_name": self.stream_name,
            "users_count": len(self.users),
            "users": list(self.users),
            "created_at": self.created_at,
            "last_data_time": self.last_data_time,
            "message_count": self.message_count,
        }


class StreamManager(LoggerMixin):
    """
    Менеджер потоков данных для управления подписками WebSocket.

    Отвечает за:
    - Управление подписками пользователей на потоки
    - Оптимизацию подписок (объединение одинаковых потоков)
    - Маршрутизацию данных к обработчикам
    - Отслеживание статистики потоков
    - Интеграцию с системой сигналов
    """

    def __init__(self, data_processor: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Инициализация менеджера потоков.

        Args:
            data_processor: Дополнительный обработчик данных потоков
        """
        self.config = get_binance_config()
        self.data_processor = data_processor

        # WebSocket клиент
        self.websocket_client: Optional[BinanceWebSocketClient] = None

        # Управление подписками
        self.subscriptions: Dict[str, StreamSubscription] = {}  # stream_name -> subscription
        self.user_streams: Dict[int, Set[str]] = defaultdict(set)  # user_id -> set of stream_names

        # Статистика
        self.total_messages_processed = 0
        self.total_subscriptions_created = 0
        self.total_subscriptions_removed = 0

        # Задачи мониторинга
        self.cleanup_task: Optional[asyncio.Task] = None
        self.stats_task: Optional[asyncio.Task] = None

        self.logger.info("StreamManager initialized")

    async def start(self) -> None:
        """Запустить менеджер потоков."""
        if self.websocket_client and self.websocket_client.is_connected():
            self.logger.warning("StreamManager already started")
            return

        self.logger.info("Starting StreamManager")

        try:
            # Создаем WebSocket клиент с интегрированным обработчиком сообщений
            self.websocket_client = BinanceWebSocketClient(
                message_handler=self._handle_websocket_message,
                error_handler=self._handle_websocket_error
            )

            # Подключаемся
            await self.websocket_client.connect()

            # Запускаем фоновые задачи
            await self._start_background_tasks()

            # Запускаем прослушивание сообщений
            asyncio.create_task(self.websocket_client.start_listening())

            self.logger.info("StreamManager started successfully")

        except Exception as e:
            self.logger.error("Failed to start StreamManager", error=str(e))
            raise

    async def stop(self) -> None:
        """Остановить менеджер потоков."""
        self.logger.info("Stopping StreamManager")

        # Останавливаем фоновые задачи
        await self._stop_background_tasks()

        # Отключаем WebSocket
        if self.websocket_client:
            await self.websocket_client.disconnect()
            self.websocket_client = None

        # Очищаем подписки
        self.subscriptions.clear()
        self.user_streams.clear()

        self.logger.info("StreamManager stopped")

    async def subscribe_user_to_pair(
            self,
            user_id: int,
            symbol: str,
            timeframes: List[str]
    ) -> Dict[str, bool]:
        """
        Подписать пользователя на пару с указанными таймфреймами.

        Args:
            user_id: ID пользователя
            symbol: Символ торговой пары
            timeframes: Список таймфреймов

        Returns:
            Dict[str, bool]: Результат подписки для каждого таймфрейма
        """
        if not self.websocket_client:
            raise WebSocketConnectionError("", "StreamManager not started")

        # Валидируем символ
        is_valid_symbol, error_msg = validate_trading_pair_symbol(symbol)
        if not is_valid_symbol:
            self.logger.error("Invalid symbol", symbol=symbol, error=error_msg)
            return {tf: False for tf in timeframes}

        results = {}
        streams_to_subscribe = []

        self.logger.info(
            "Subscribing user to pair",
            user_id=user_id,
            symbol=symbol,
            timeframes=timeframes
        )

        for timeframe in timeframes:
            # Валидируем таймфрейм
            is_valid_tf, tf_error = validate_timeframe(timeframe)
            if not is_valid_tf:
                self.logger.error(
                    "Invalid timeframe",
                    timeframe=timeframe,
                    error=tf_error
                )
                results[timeframe] = False
                continue

            stream_name = get_kline_stream_name(symbol, timeframe)

            try:
                # Проверяем, есть ли уже подписка на этот поток
                if stream_name in self.subscriptions:
                    # Добавляем пользователя к существующей подписке
                    subscription = self.subscriptions[stream_name]
                    subscription.add_user(user_id)

                    self.logger.debug(
                        "Added user to existing subscription",
                        stream=stream_name,
                        user_id=user_id,
                        total_users=len(subscription.users)
                    )
                else:
                    # Создаем новую подписку
                    subscription = StreamSubscription(symbol, timeframe, {user_id})
                    self.subscriptions[stream_name] = subscription
                    streams_to_subscribe.append(stream_name)
                    self.total_subscriptions_created += 1

                    self.logger.debug(
                        "Created new subscription",
                        stream=stream_name,
                        user_id=user_id
                    )

                # Добавляем поток к пользователю
                self.user_streams[user_id].add(stream_name)
                results[timeframe] = True

            except Exception as e:
                self.logger.error(
                    "Failed to create subscription",
                    stream=stream_name,
                    user_id=user_id,
                    error=str(e)
                )
                results[timeframe] = False

        # Подписываемся на новые потоки в WebSocket
        if streams_to_subscribe:
            try:
                await self.websocket_client.subscribe_to_multiple_streams(streams_to_subscribe)
                self.logger.info(
                    "WebSocket subscriptions created",
                    streams=streams_to_subscribe
                )
            except Exception as e:
                self.logger.error(
                    "Failed to create WebSocket subscriptions",
                    streams=streams_to_subscribe,
                    error=str(e)
                )

                # Откатываем изменения для неудачных подписок
                for stream_name in streams_to_subscribe:
                    if stream_name in self.subscriptions:
                        subscription = self.subscriptions[stream_name]
                        subscription.remove_user(user_id)
                        if len(subscription.users) == 0:
                            del self.subscriptions[stream_name]

                        self.user_streams[user_id].discard(stream_name)

                        # Обновляем результат
                        for tf, stream in [(tf, get_kline_stream_name(symbol, tf)) for tf in timeframes]:
                            if stream == stream_name:
                                results[tf] = False

        self.logger.info(
            "User subscription completed",
            user_id=user_id,
            symbol=symbol,
            success_count=sum(results.values()),
            total_count=len(results)
        )

        return results

    async def unsubscribe_user_from_pair(
            self,
            user_id: int,
            symbol: str,
            timeframes: List[str]
    ) -> Dict[str, bool]:
        """
        Отписать пользователя от пары с указанными таймфреймами.

        Args:
            user_id: ID пользователя
            symbol: Символ торговой пары
            timeframes: Список таймфреймов

        Returns:
            Dict[str, bool]: Результат отписки для каждого таймфрейма
        """
        if not self.websocket_client:
            raise WebSocketConnectionError("", "StreamManager not started")

        results = {}
        streams_to_unsubscribe = []

        self.logger.info(
            "Unsubscribing user from pair",
            user_id=user_id,
            symbol=symbol,
            timeframes=timeframes
        )

        for timeframe in timeframes:
            stream_name = get_kline_stream_name(symbol, timeframe)

            try:
                if stream_name in self.subscriptions:
                    subscription = self.subscriptions[stream_name]

                    # Удаляем пользователя из подписки
                    is_empty = subscription.remove_user(user_id)
                    self.user_streams[user_id].discard(stream_name)

                    if is_empty:
                        # Если подписка стала пустой, удаляем её
                        del self.subscriptions[stream_name]
                        streams_to_unsubscribe.append(stream_name)
                        self.total_subscriptions_removed += 1

                        self.logger.debug(
                            "Removed empty subscription",
                            stream=stream_name,
                            user_id=user_id
                        )
                    else:
                        self.logger.debug(
                            "Removed user from subscription",
                            stream=stream_name,
                            user_id=user_id,
                            remaining_users=len(subscription.users)
                        )

                results[timeframe] = True

            except Exception as e:
                self.logger.error(
                    "Failed to remove subscription",
                    stream=stream_name,
                    user_id=user_id,
                    error=str(e)
                )
                results[timeframe] = False

        # Отписываемся от пустых потоков в WebSocket
        if streams_to_unsubscribe:
            try:
                for stream_name in streams_to_unsubscribe:
                    await self.websocket_client.unsubscribe_from_stream(stream_name)

                self.logger.info(
                    "WebSocket unsubscriptions completed",
                    streams=streams_to_unsubscribe
                )
            except Exception as e:
                self.logger.error(
                    "Failed to unsubscribe from WebSocket streams",
                    streams=streams_to_unsubscribe,
                    error=str(e)
                )

        # Очищаем пустые записи пользователей
        if user_id in self.user_streams and not self.user_streams[user_id]:
            del self.user_streams[user_id]

        self.logger.info(
            "User unsubscription completed",
            user_id=user_id,
            symbol=symbol,
            success_count=sum(results.values()),
            total_count=len(results)
        )

        return results

    async def unsubscribe_user_from_all(self, user_id: int) -> bool:
        """
        Отписать пользователя от всех потоков.

        Args:
            user_id: ID пользователя

        Returns:
            bool: True если отписка успешна
        """
        if user_id not in self.user_streams:
            self.logger.info("User has no subscriptions", user_id=user_id)
            return True

        user_stream_names = list(self.user_streams[user_id])
        streams_to_unsubscribe = []

        self.logger.info(
            "Unsubscribing user from all streams",
            user_id=user_id,
            stream_count=len(user_stream_names)
        )

        try:
            for stream_name in user_stream_names:
                if stream_name in self.subscriptions:
                    subscription = self.subscriptions[stream_name]

                    # Удаляем пользователя
                    is_empty = subscription.remove_user(user_id)

                    if is_empty:
                        # Удаляем пустую подписку
                        del self.subscriptions[stream_name]
                        streams_to_unsubscribe.append(stream_name)
                        self.total_subscriptions_removed += 1

            # Очищаем потоки пользователя
            del self.user_streams[user_id]

            # Отписываемся от пустых потоков в WebSocket
            if streams_to_unsubscribe:
                for stream_name in streams_to_unsubscribe:
                    await self.websocket_client.unsubscribe_from_stream(stream_name)

            self.logger.info(
                "User fully unsubscribed",
                user_id=user_id,
                removed_streams=len(streams_to_unsubscribe)
            )

            return True

        except Exception as e:
            self.logger.error(
                "Failed to unsubscribe user from all streams",
                user_id=user_id,
                error=str(e)
            )
            return False

    async def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получить список подписок пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            List[Dict[str, Any]]: Список подписок пользователя
        """
        if user_id not in self.user_streams:
            return []

        subscriptions = []

        for stream_name in self.user_streams[user_id]:
            if stream_name in self.subscriptions:
                subscription = self.subscriptions[stream_name]
                subscriptions.append({
                    "symbol": subscription.symbol,
                    "timeframe": subscription.timeframe,
                    "stream_name": stream_name,
                    "users_count": len(subscription.users),
                    "message_count": subscription.message_count,
                    "last_data_time": subscription.last_data_time,
                })

        return subscriptions

    async def get_manager_stats(self) -> Dict[str, Any]:
        """
        Получить статистику менеджера потоков.

        Returns:
            Dict[str, Any]: Статистика менеджера
        """
        websocket_stats = {}
        if self.websocket_client:
            websocket_stats = await self.websocket_client.get_connection_stats()

        # Группируем подписки по символам
        symbols_stats = defaultdict(lambda: {"timeframes": set(), "users": set()})

        for subscription in self.subscriptions.values():
            symbols_stats[subscription.symbol]["timeframes"].add(subscription.timeframe)
            symbols_stats[subscription.symbol]["users"].update(subscription.users)

        # Преобразуем в сериализуемый формат
        symbols_info = {}
        for symbol, stats in symbols_stats.items():
            symbols_info[symbol] = {
                "timeframes": list(stats["timeframes"]),
                "users_count": len(stats["users"]),
                "users": list(stats["users"])
            }

        return {
            "subscriptions_count": len(self.subscriptions),
            "users_count": len(self.user_streams),
            "total_messages_processed": self.total_messages_processed,
            "total_subscriptions_created": self.total_subscriptions_created,
            "total_subscriptions_removed": self.total_subscriptions_removed,
            "symbols": symbols_info,
            "websocket": websocket_stats,
        }

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Получить детальную статистику менеджера потоков включая систему сигналов.

        Returns:
            Dict[str, Any]: Детальная статистика
        """
        # Получаем базовые статистики
        base_stats = await self.get_manager_stats()

        # Добавляем статистики системы сигналов
        try:
            from services.signals.signal_aggregator import signal_aggregator
            from services.notifications.notification_queue import notification_queue

            signal_stats = signal_aggregator.get_processing_stats()
            queue_stats = await notification_queue.get_queue_stats()

            processing_stats = {
                "signal_processing": signal_stats,
                "notification_queue": queue_stats,
                "processing_efficiency": {
                    "messages_per_subscription": (
                        self.total_messages_processed / max(1, len(self.subscriptions))
                    ),
                    "average_users_per_symbol": (
                        len(self.user_streams) / max(1, len(base_stats.get("symbols", {})))
                    ) if base_stats.get("symbols") else 0
                }
            }

        except Exception as e:
            self.logger.error("Error getting signal processing stats", error=str(e))
            processing_stats = {"error": "Unable to get signal processing stats"}

        # Объединяем статистики
        detailed_stats = {
            **base_stats,
            **processing_stats
        }

        return detailed_stats

    async def _handle_websocket_message(self, message: Dict[str, Any]) -> None:
        """
        Обработать сообщение от WebSocket.

        Args:
            message: Сообщение от WebSocket
        """
        try:
            stream_name = message.get("stream")

            if not stream_name:
                self.logger.warning("Message without stream name", message=message)
                return

            # Обновляем статистику подписки
            if stream_name in self.subscriptions:
                self.subscriptions[stream_name].update_stats()

            self.total_messages_processed += 1

            # Определяем тип потока и обрабатываем соответственно
            stream_info = parse_stream_name(stream_name)

            if stream_info.get("valid") and stream_info.get("type") == "kline":
                # Обрабатываем kline сообщения через систему сигналов
                await self._handle_kline_message(message)

            # Также передаем сообщение внешнему обработчику данных если есть
            if self.data_processor:
                if asyncio.iscoroutinefunction(self.data_processor):
                    await self.data_processor(message)
                else:
                    self.data_processor(message)

            self.logger.debug(
                "WebSocket message processed",
                stream=stream_name,
                data_type=message.get("data", {}).get("e", "unknown")
            )

        except Exception as e:
            self.logger.error(
                "Error processing WebSocket message",
                error=str(e),
                message=message,
                exc_info=True
            )

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

            # Проверяем, есть ли подписчики на этот поток
            if stream_name not in self.subscriptions:
                self.logger.debug(
                    "No active subscription for stream",
                    stream=stream_name
                )
                return

            subscription = self.subscriptions[stream_name]

            if not subscription.users:
                self.logger.debug(
                    "No users subscribed to stream",
                    stream=stream_name
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

            # Отправляем в систему сигналов
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
                        "Signals generated from stream",
                        symbol=symbol,
                        timeframe=timeframe,
                        rsi_notifications=result["rsi_notifications"],
                        ema_notifications=result["ema_notifications"],
                        total_notifications=result["total_notifications"]
                    )
                elif result.get("error"):
                    self.logger.error(
                        "Error in signal processing",
                        symbol=symbol,
                        timeframe=timeframe,
                        error=result["error"]
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

    async def _handle_websocket_error(self, error: Exception) -> None:
        """
        Обработать ошибку WebSocket.

        Args:
            error: Исключение от WebSocket
        """
        self.logger.error("WebSocket error occurred", error=str(error), error_type=type(error).__name__)

        # Здесь можно добавить дополнительную логику обработки ошибок
        # Например, уведомление администраторов или попытки восстановления

    async def _start_background_tasks(self) -> None:
        """Запустить фоновые задачи."""
        # Задача очистки неактивных подписок
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Задача сбора статистики
        self.stats_task = asyncio.create_task(self._stats_loop())

        self.logger.debug("StreamManager background tasks started")

    async def _stop_background_tasks(self) -> None:
        """Остановить фоновые задачи."""
        tasks = [self.cleanup_task, self.stats_task]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.cleanup_task = None
        self.stats_task = None

        self.logger.debug("StreamManager background tasks stopped")

    async def _cleanup_loop(self) -> None:
        """Цикл очистки неактивных подписок."""
        while True:
            try:
                # Проверяем каждые 5 минут
                await asyncio.sleep(300)

                current_time = asyncio.get_event_loop().time()
                inactive_streams = []

                # Ищем подписки без активности более 30 минут
                for stream_name, subscription in self.subscriptions.items():
                    if (subscription.last_data_time and
                            current_time - subscription.last_data_time > 1800):
                        inactive_streams.append(stream_name)

                if inactive_streams:
                    self.logger.warning(
                        "Found inactive streams",
                        count=len(inactive_streams),
                        streams=inactive_streams
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in cleanup loop", error=str(e))

    async def _stats_loop(self) -> None:
        """Цикл логирования статистики."""
        while True:
            try:
                # Логируем статистику каждые 10 минут
                await asyncio.sleep(600)

                stats = await self.get_manager_stats()
                self.logger.info(
                    "StreamManager statistics",
                    subscriptions=stats["subscriptions_count"],
                    users=stats["users_count"],
                    messages_processed=stats["total_messages_processed"],
                    symbols_count=len(stats["symbols"])
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in stats loop", error=str(e))