"""
Путь: src/services/notifications/telegram_sender.py
Описание: Сервис для отправки уведомлений пользователям в Telegram
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError

from bot.keyboards.main_menu_kb import get_main_menu_keyboard
from utils.logger import get_logger
from utils.constants import MAX_NOTIFICATIONS_PER_MINUTE, MAX_NOTIFICATIONS_PER_HOUR
from utils.exceptions import NotificationError


class TelegramSender:
    """
    Сервис для отправки уведомлений в Telegram.

    Включает:
    - Rate limiting (ограничение частоты)
    - Retry механизм при ошибках
    - Статистика отправки
    - Форматирование сообщений
    """

    def __init__(self, bot: Bot):
        """
        Инициализация отправщика.

        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
        self.logger = get_logger(__name__)

        # Статистика отправки
        self.stats = {
            "sent_total": 0,
            "sent_today": 0,
            "failed_total": 0,
            "blocked_users": set(),
            "last_reset": datetime.now().date()
        }

        # Rate limiting
        self.user_message_counts = {}  # user_id -> [timestamps]

    async def send_signal_notification(
            self,
            user_id: int,
            symbol: str,
            timeframe: str,
            signal_data: Dict[str, Any],
            priority: str = "MEDIUM"
    ) -> bool:
        """
        Отправить уведомление о сигнале.

        Args:
            user_id: ID пользователя
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            signal_data: Данные сигнала
            priority: Приоритет уведомления

        Returns:
            bool: True если успешно отправлено
        """
        try:
            # Проверяем rate limiting
            if not await self._check_rate_limit(user_id, priority):
                self.logger.warning(
                    "Rate limit exceeded for user",
                    user_id=user_id,
                    symbol=symbol,
                    timeframe=timeframe
                )
                return False

            # Форматируем сообщение
            from services.notifications.message_formatter import format_signal_message
            message_text = format_signal_message(
                symbol=symbol,
                timeframe=timeframe,
                **signal_data
            )

            # Создаем клавиатуру с кнопкой "Меню"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Меню", callback_data="main_menu")]
            ])

            # Отправляем сообщение
            success = await self._send_message_with_retry(
                user_id=user_id,
                text=message_text,
                reply_markup=keyboard,
                max_retries=3
            )

            if success:
                await self._update_sending_stats(user_id, success=True)
                self.logger.info(
                    "Signal notification sent successfully",
                    user_id=user_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_data.get("signal_type")
                )
            else:
                await self._update_sending_stats(user_id, success=False)

            return success

        except Exception as e:
            self.logger.error(
                "Error sending signal notification",
                user_id=user_id,
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            await self._update_sending_stats(user_id, success=False)
            return False

    async def send_system_message(
            self,
            user_id: int,
            message: str,
            keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправить системное сообщение пользователю.

        Args:
            user_id: ID пользователя
            message: Текст сообщения
            keyboard: Клавиатура (опционально)

        Returns:
            bool: True если успешно отправлено
        """
        try:
            success = await self._send_message_with_retry(
                user_id=user_id,
                text=message,
                reply_markup=keyboard,
                max_retries=2
            )

            if success:
                self.logger.debug(
                    "System message sent successfully",
                    user_id=user_id,
                    message_length=len(message)
                )

            return success

        except Exception as e:
            self.logger.error(
                "Error sending system message",
                user_id=user_id,
                error=str(e)
            )
            return False

    async def send_bulk_notifications(
            self,
            notifications: List[Dict[str, Any]],
            delay_between_sends: float = 0.05
    ) -> Dict[str, int]:
        """
        Отправить множественные уведомления.

        Args:
            notifications: Список уведомлений
            delay_between_sends: Задержка между отправками (сек)

        Returns:
            Dict: Статистика отправки
        """
        results = {
            "total": len(notifications),
            "sent": 0,
            "failed": 0,
            "rate_limited": 0
        }

        self.logger.info(
            "Starting bulk notification sending",
            total_notifications=len(notifications)
        )

        for notification in notifications:
            try:
                user_id = notification["user_id"]

                # Проверяем не заблокирован ли пользователь
                if user_id in self.stats["blocked_users"]:
                    results["failed"] += 1
                    continue

                # Отправляем уведомление
                if notification["type"] == "signal":
                    success = await self.send_signal_notification(
                        user_id=user_id,
                        symbol=notification["symbol"],
                        timeframe=notification["timeframe"],
                        signal_data=notification["signal_data"],
                        priority=notification.get("priority", "MEDIUM")
                    )
                else:
                    success = await self.send_system_message(
                        user_id=user_id,
                        message=notification["message"],
                        keyboard=notification.get("keyboard")
                    )

                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1

                # Задержка между отправками
                if delay_between_sends > 0:
                    await asyncio.sleep(delay_between_sends)

            except Exception as e:
                self.logger.error(
                    "Error in bulk notification",
                    notification=notification,
                    error=str(e)
                )
                results["failed"] += 1

        self.logger.info(
            "Bulk notification sending completed",
            **results
        )

        return results

    async def _send_message_with_retry(
            self,
            user_id: int,
            text: str,
            reply_markup: Optional[InlineKeyboardMarkup] = None,
            max_retries: int = 3
    ) -> bool:
        """
        Отправить сообщение с повторными попытками.

        Args:
            user_id: ID пользователя
            text: Текст сообщения
            reply_markup: Клавиатура
            max_retries: Максимальное количество попыток

        Returns:
            bool: True если успешно отправлено
        """
        for attempt in range(max_retries):
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return True

            except TelegramForbiddenError:
                # Пользователь заблокировал бота
                self.stats["blocked_users"].add(user_id)
                self.logger.warning(
                    "User blocked the bot",
                    user_id=user_id
                )
                return False

            except TelegramRetryAfter as e:
                # Rate limit от Telegram API
                retry_after = e.retry_after
                self.logger.warning(
                    "Telegram rate limit hit, waiting",
                    user_id=user_id,
                    retry_after=retry_after,
                    attempt=attempt + 1
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    return False

            except TelegramBadRequest as e:
                # Некорректный запрос
                self.logger.error(
                    "Bad request to Telegram API",
                    user_id=user_id,
                    error=str(e),
                    attempt=attempt + 1
                )

                # Не повторяем при ошибках запроса
                return False

            except Exception as e:
                # Другие ошибки
                self.logger.error(
                    "Unexpected error sending message",
                    user_id=user_id,
                    error=str(e),
                    attempt=attempt + 1
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    return False

        return False

    async def _check_rate_limit(
            self,
            user_id: int,
            priority: str = "MEDIUM"
    ) -> bool:
        """
        Проверить ограничения частоты отправки.

        Args:
            user_id: ID пользователя
            priority: Приоритет сообщения

        Returns:
            bool: True если можно отправлять
        """
        now = datetime.now()

        # Получаем историю отправок пользователя
        if user_id not in self.user_message_counts:
            self.user_message_counts[user_id] = []

        user_timestamps = self.user_message_counts[user_id]

        # Удаляем старые записи (старше часа)
        hour_ago = now - timedelta(hours=1)
        user_timestamps[:] = [ts for ts in user_timestamps if ts > hour_ago]

        # Проверяем лимиты
        minute_ago = now - timedelta(minutes=1)
        recent_messages = sum(1 for ts in user_timestamps if ts > minute_ago)

        # Лимиты в зависимости от приоритета
        if priority == "HIGH":
            minute_limit = MAX_NOTIFICATIONS_PER_MINUTE * 2
            hour_limit = MAX_NOTIFICATIONS_PER_HOUR * 2
        elif priority == "LOW":
            minute_limit = MAX_NOTIFICATIONS_PER_MINUTE // 2
            hour_limit = MAX_NOTIFICATIONS_PER_HOUR // 2
        else:  # MEDIUM
            minute_limit = MAX_NOTIFICATIONS_PER_MINUTE
            hour_limit = MAX_NOTIFICATIONS_PER_HOUR

        # Проверяем лимиты
        if recent_messages >= minute_limit:
            self.logger.debug(
                "Minute rate limit exceeded",
                user_id=user_id,
                recent_messages=recent_messages,
                limit=minute_limit
            )
            return False

        if len(user_timestamps) >= hour_limit:
            self.logger.debug(
                "Hour rate limit exceeded",
                user_id=user_id,
                total_messages=len(user_timestamps),
                limit=hour_limit
            )
            return False

        # Добавляем текущую отправку
        user_timestamps.append(now)
        return True

    async def _update_sending_stats(
            self,
            user_id: int,
            success: bool
    ) -> None:
        """
        Обновить статистику отправки.

        Args:
            user_id: ID пользователя
            success: Успешна ли отправка
        """
        # Сброс дневной статистики при смене дня
        today = datetime.now().date()
        if today != self.stats["last_reset"]:
            self.stats["sent_today"] = 0
            self.stats["last_reset"] = today

        if success:
            self.stats["sent_total"] += 1
            self.stats["sent_today"] += 1
        else:
            self.stats["failed_total"] += 1

    def get_sending_stats(self) -> Dict[str, Any]:
        """
        Получить статистику отправки.

        Returns:
            Dict: Статистика отправки
        """
        return {
            "sent_total": self.stats["sent_total"],
            "sent_today": self.stats["sent_today"],
            "failed_total": self.stats["failed_total"],
            "blocked_users_count": len(self.stats["blocked_users"]),
            "success_rate": (
                                    self.stats["sent_total"] /
                                    max(1, self.stats["sent_total"] + self.stats["failed_total"])
                            ) * 100,
            "active_users_with_limits": len(self.user_message_counts)
        }

    def reset_user_rate_limits(self, user_id: int) -> None:
        """
        Сбросить лимиты для пользователя.

        Args:
            user_id: ID пользователя
        """
        if user_id in self.user_message_counts:
            del self.user_message_counts[user_id]

        self.stats["blocked_users"].discard(user_id)

        self.logger.info(
            "Rate limits reset for user",
            user_id=user_id
        )

    def is_user_blocked(self, user_id: int) -> bool:
        """
        Проверить заблокировал ли пользователь бота.

        Args:
            user_id: ID пользователя

        Returns:
            bool: True если заблокирован
        """
        return user_id in self.stats["blocked_users"]