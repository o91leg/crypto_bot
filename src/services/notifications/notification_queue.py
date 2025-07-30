"""
Путь: src/services/notifications/notification_queue.py
Описание: Сервис для управления очередью уведомлений
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from data.redis_client import get_redis_client
from utils.logger import get_logger
from utils.constants import NOTIFICATION_PRIORITIES, MAX_NOTIFICATIONS_PER_MINUTE
from utils.exceptions import NotificationError


class NotificationStatus(Enum):
    """Статусы уведомлений."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NotificationTask:
    """Задача уведомления."""
    id: str
    user_id: int
    type: str  # signal, system, broadcast
    priority: str  # HIGH, MEDIUM, LOW
    data: Dict[str, Any]
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    status: NotificationStatus = NotificationStatus.PENDING
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["scheduled_at"] = self.scheduled_at.isoformat() if self.scheduled_at else None
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationTask":
        """Создать из словаря."""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data["scheduled_at"]:
            data["scheduled_at"] = datetime.fromisoformat(data["scheduled_at"])
        data["status"] = NotificationStatus(data["status"])
        return cls(**data)


class NotificationQueue:
    """
    Сервис для управления очередью уведомлений.

    Включает:
    - Приоритизацию уведомлений
    - Планирование отправки
    - Retry механизм
    - Статистику и мониторинг
    """

    def __init__(self):
        """Инициализация очереди уведомлений."""
        self.redis_client = None
        self.logger = get_logger(__name__)
        self.is_processing = False
        self.processing_task = None

        # Ключи Redis
        self.queue_key = "notification_queue"
        self.processing_key = "notification_processing"
        self.stats_key = "notification_stats"

    async def initialize(self) -> None:
        """Инициализировать подключение к Redis."""
        if not self.redis_client:
            self.redis_client = get_redis_client()  # Убираем await!
            self.logger.info("Notification queue initialized")

    async def add_notification(
            self,
            user_id: int,
            notification_type: str,
            data: Dict[str, Any],
            priority: str = "MEDIUM",
            delay_seconds: int = 0
    ) -> str:
        """
        Добавить уведомление в очередь.

        Args:
            user_id: ID пользователя
            notification_type: Тип уведомления
            data: Данные уведомления
            priority: Приоритет
            delay_seconds: Задержка перед отправкой

        Returns:
            str: ID задачи

        Raises:
            NotificationError: Ошибка при добавлении
        """
        await self.initialize()

        try:
            # Создаем задачу
            task_id = f"{user_id}_{notification_type}_{int(datetime.now().timestamp())}"

            scheduled_at = None
            if delay_seconds > 0:
                scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)

            task = NotificationTask(
                id=task_id,
                user_id=user_id,
                type=notification_type,
                priority=priority,
                data=data,
                created_at=datetime.now(),
                scheduled_at=scheduled_at
            )

            # Получаем приоритет для сортировки
            priority_score = NOTIFICATION_PRIORITIES.get(priority, 2)

            # Добавляем в очередь с приоритетом
            await self.redis_client.zadd(
                self.queue_key,
                {json.dumps(task.to_dict()): priority_score}
            )

            # Обновляем статистику
            await self._update_stats("added", 1)

            self.logger.info(
                "Notification added to queue",
                task_id=task_id,
                user_id=user_id,
                type=notification_type,
                priority=priority,
                delay_seconds=delay_seconds
            )

            return task_id

        except Exception as e:
            self.logger.error(
                "Error adding notification to queue",
                user_id=user_id,
                type=notification_type,
                error=str(e)
            )
            raise NotificationError(f"Failed to add notification: {str(e)}")

    async def add_signal_notification(
            self,
            user_id: int,
            symbol: str,
            timeframe: str,
            signal_data: Dict[str, Any],
            priority: str = "MEDIUM"
    ) -> str:
        """
        Добавить уведомление о сигнале.

        Args:
            user_id: ID пользователя
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            signal_data: Данные сигнала
            priority: Приоритет

        Returns:
            str: ID задачи
        """
        notification_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "signal_data": signal_data
        }

        return await self.add_notification(
            user_id=user_id,
            notification_type="signal",
            data=notification_data,
            priority=priority
        )

    async def get_pending_notifications(
            self,
            limit: int = 100
    ) -> List[NotificationTask]:
        """
        Получить ожидающие уведомления.

        Args:
            limit: Максимальное количество

        Returns:
            List[NotificationTask]: Список задач
        """
        await self.initialize()

        try:
            # Получаем задачи по приоритету (меньший score = выше приоритет)
            raw_tasks = await self.redis_client.zrange(
                self.queue_key,
                0,
                limit - 1,
                withscores=True
            )

            tasks = []
            current_time = datetime.now()

            for task_data, score in raw_tasks:
                try:
                    task_dict = json.loads(task_data)
                    task = NotificationTask.from_dict(task_dict)

                    # Проверяем время планировки
                    if task.scheduled_at and task.scheduled_at > current_time:
                        continue

                    # Проверяем статус
                    if task.status == NotificationStatus.PENDING:
                        tasks.append(task)

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    self.logger.error(
                        "Error parsing notification task",
                        error=str(e),
                        task_data=task_data
                    )
                    # Удаляем поврежденную задачу
                    await self.redis_client.zrem(self.queue_key, task_data)

            return tasks

        except Exception as e:
            self.logger.error(
                "Error getting pending notifications",
                error=str(e)
            )
            return []

    async def mark_task_processing(self, task: NotificationTask) -> bool:
        """
        Отметить задачу как обрабатываемую.

        Args:
            task: Задача для обработки

        Returns:
            bool: True если успешно отмечено
        """
        await self.initialize()

        try:
            # Обновляем статус
            task.status = NotificationStatus.PROCESSING
            task.attempts += 1

            # Удаляем из очереди
            old_task_json = json.dumps(task.to_dict())
            await self.redis_client.zrem(self.queue_key, old_task_json)

            # Добавляем в обработку
            await self.redis_client.hset(
                self.processing_key,
                task.id,
                json.dumps(task.to_dict())
            )

            return True

        except Exception as e:
            self.logger.error(
                "Error marking task as processing",
                task_id=task.id,
                error=str(e)
            )
            return False

    async def mark_task_completed(
            self,
            task: NotificationTask,
            success: bool,
            error_message: Optional[str] = None
    ) -> None:
        """
        Отметить задачу как завершенную.

        Args:
            task: Завершенная задача
            success: Успешно ли выполнена
            error_message: Сообщение об ошибке
        """
        await self.initialize()

        try:
            if success:
                task.status = NotificationStatus.SENT
                await self._update_stats("sent", 1)
            else:
                task.status = NotificationStatus.FAILED
                task.error_message = error_message
                await self._update_stats("failed", 1)

                # Повторная попытка если не превышен лимит
                if task.attempts < task.max_attempts:
                    await self._reschedule_task(task)
                    return

            # Удаляем из обработки
            await self.redis_client.hdel(self.processing_key, task.id)

            self.logger.debug(
                "Task completed",
                task_id=task.id,
                success=success,
                attempts=task.attempts
            )

        except Exception as e:
            self.logger.error(
                "Error marking task as completed",
                task_id=task.id,
                error=str(e)
            )

    async def start_processing(self) -> None:
        """Запустить обработку очереди."""
        if self.is_processing:
            self.logger.warning("Queue processing already started")
            return

        self.is_processing = True
        self.processing_task = asyncio.create_task(self._process_queue())

        self.logger.info("Notification queue processing started")

    async def stop_processing(self) -> None:
        """Остановить обработку очереди."""
        if not self.is_processing:
            return

        self.is_processing = False

        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Notification queue processing stopped")

    async def _process_queue(self) -> None:
        """Основной цикл обработки очереди."""
        from services.notifications.telegram_sender import TelegramSender

        while self.is_processing:
            try:
                # Получаем ожидающие задачи
                pending_tasks = await self.get_pending_notifications(
                    limit=MAX_NOTIFICATIONS_PER_MINUTE
                )

                if not pending_tasks:
                    await asyncio.sleep(1)
                    continue

                # Обрабатываем задачи
                for task in pending_tasks:
                    if not self.is_processing:
                        break

                    try:
                        # Отмечаем как обрабатываемую
                        await self.mark_task_processing(task)

                        # Обрабатываем в зависимости от типа
                        success = await self._process_single_task(task)

                        # Отмечаем как завершенную
                        await self.mark_task_completed(task, success)

                        # Небольшая пауза между отправками
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        self.logger.error(
                            "Error processing task",
                            task_id=task.id,
                            error=str(e)
                        )
                        await self.mark_task_completed(
                            task,
                            success=False,
                            error_message=str(e)
                        )

            except Exception as e:
                self.logger.error(
                    "Error in queue processing loop",
                    error=str(e)
                )
                await asyncio.sleep(5)

    async def _process_single_task(self, task: NotificationTask) -> bool:
        """
        Обработать одну задачу.

        Args:
            task: Задача для обработки

        Returns:
            bool: True если успешно обработано
        """
        try:
            # Здесь должна быть логика отправки
            # Пока что заглушка
            self.logger.info(
                "Processing notification task",
                task_id=task.id,
                user_id=task.user_id,
                type=task.type
            )

            # Имитация обработки
            await asyncio.sleep(0.1)

            return True

        except Exception as e:
            self.logger.error(
                "Error processing single task",
                task_id=task.id,
                error=str(e)
            )
            return False

    async def _reschedule_task(self, task: NotificationTask) -> None:
        """Перепланировать неудачную задачу."""
        try:
            # Увеличиваем задержку с каждой попыткой
            delay_seconds = 2 ** task.attempts  # 2, 4, 8 секунд
            task.scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)
            task.status = NotificationStatus.PENDING

            # Добавляем обратно в очередь
            priority_score = NOTIFICATION_PRIORITIES.get(task.priority, 2)
            await self.redis_client.zadd(
                self.queue_key,
                {json.dumps(task.to_dict()): priority_score}
            )

            # Удаляем из обработки
            await self.redis_client.hdel(self.processing_key, task.id)

            self.logger.info(
                "Task rescheduled",
                task_id=task.id,
                attempt=task.attempts,
                delay_seconds=delay_seconds
            )

        except Exception as e:
            self.logger.error(
                "Error rescheduling task",
                task_id=task.id,
                error=str(e)
            )

    async def _update_stats(self, metric: str, value: int) -> None:
        """Обновить статистику."""
        try:
            await self.redis_client.hincrby(self.stats_key, metric, value)
            await self.redis_client.hincrby(
                self.stats_key,
                f"{metric}_today",
                value
            )
        except Exception as e:
            self.logger.error(
                "Error updating stats",
                metric=metric,
                value=value,
                error=str(e)
            )

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Получить статистику очереди.

        Returns:
            Dict: Статистика очереди
        """
        await self.initialize()

        try:
            # Получаем счетчики
            stats = await self.redis_client.hgetall(self.stats_key)

            # Получаем размер очереди
            queue_size = await self.redis_client.zcard(self.queue_key)
            processing_size = await self.redis_client.hlen(self.processing_key)

            return {
                "queue_size": queue_size,
                "processing_size": processing_size,
                "total_added": int(stats.get("added", 0)),
                "total_sent": int(stats.get("sent", 0)),
                "total_failed": int(stats.get("failed", 0)),
                "sent_today": int(stats.get("sent_today", 0)),
                "failed_today": int(stats.get("failed_today", 0)),
                "is_processing": self.is_processing
            }

        except Exception as e:
            self.logger.error(
                "Error getting queue stats",
                error=str(e)
            )
            return {}


# Глобальный экземпляр очереди
notification_queue = NotificationQueue()