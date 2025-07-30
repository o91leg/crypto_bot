"""
Путь: src/bot/middlewares/database_mw.py
Описание: Middleware для автоматического предоставления сессии БД в обработчики
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from data.database import get_session

# Настройка логирования
logger = structlog.get_logger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для предоставления сессии базы данных в обработчики."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Основной метод middleware.

        Args:
            handler: Следующий обработчик в цепочке
            event: Событие Telegram (Message, CallbackQuery, etc.)
            data: Данные, передаваемые между middleware и обработчиками

        Returns:
            Any: Результат выполнения обработчика
        """
        # Получаем информацию о пользователе для логирования
        user_id = None
        event_type = type(event).__name__

        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id

        logger.debug(
            "Database middleware called",
            event_type=event_type,
            user_id=user_id
        )

        # Создаем сессию базы данных
        try:
            async with get_session() as session:
                # Добавляем сессию в данные для обработчика
                data["session"] = session

                # Вызываем следующий обработчик
                result = await handler(event, data)

                # Если обработчик выполнился успешно, коммитим транзакцию
                # (это уже происходит автоматически в контекстном менеджере get_session)

                logger.debug(
                    "Database middleware completed successfully",
                    event_type=event_type,
                    user_id=user_id
                )

                return result

        except Exception as e:
            # Логируем ошибку
            logger.error(
                "Error in database middleware",
                event_type=event_type,
                user_id=user_id,
                error=str(e),
                exc_info=True
            )

            # Пробрасываем исключение дальше
            raise


class UserCheckMiddleware(BaseMiddleware):
    """Middleware для проверки и получения пользователя из БД."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет пользователя и добавляет его в данные.

        Args:
            handler: Следующий обработчик в цепочке
            event: Событие Telegram
            data: Данные middleware

        Returns:
            Any: Результат выполнения обработчика
        """
        # Проверяем, есть ли информация о пользователе
        telegram_user = None
        if hasattr(event, 'from_user') and event.from_user:
            telegram_user = event.from_user
        else:
            # Если нет информации о пользователе, продолжаем без проверки
            return await handler(event, data)

        user_id = telegram_user.id
        session: AsyncSession = data.get("session")

        if not session:
            logger.warning("No database session available in UserCheckMiddleware")
            return await handler(event, data)

        try:
            from data.models.user_model import User

            # Получаем пользователя из БД
            user = await User.get_by_telegram_id(session, user_id)

            if user:
                # Проверяем, не заблокирован ли пользователь
                if user.is_blocked:
                    logger.warning("Blocked user attempted to use bot", user_id=user_id)

                    # Отправляем сообщение о блокировке
                    if hasattr(event, 'answer'):
                        await event.answer(
                            "❌ Ваш аккаунт заблокирован.\nОбратитесь к администратору для разблокировки."
                        )

                    return  # Прерываем выполнение

                # Проверяем, активен ли пользователь
                if not user.is_active:
                    logger.info("Inactive user attempted to use bot", user_id=user_id)

                    # Активируем пользователя обратно
                    user.activate()
                    await session.commit()

                    logger.info("User reactivated", user_id=user_id)

                # Добавляем пользователя в данные
                data["user"] = user

                logger.debug("User loaded from database", user_id=user_id, username=user.username)
            else:
                # Пользователь не найден - это нормально для команды /start
                logger.debug("User not found in database", user_id=user_id)

            # Продолжаем выполнение
            return await handler(event, data)

        except Exception as e:
            logger.error(
                "Error in user check middleware",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )

            # Продолжаем выполнение несмотря на ошибку
            return await handler(event, data)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для глобальной обработки ошибок."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        """
        Обрабатывает ошибки в обработчиках.

        Args:
            handler: Следующий обработчик в цепочке
            event: Событие Telegram
            data: Данные middleware

        Returns:
            Any: Результат выполнения обработчика
        """
        try:
            return await handler(event, data)

        except Exception as e:
            # Получаем информацию для логирования
            user_id = None
            event_type = type(event).__name__

            if hasattr(event, 'from_user') and event.from_user:
                user_id = event.from_user.id

            # Логируем ошибку
            logger.error(
                "Unhandled error in bot handler",
                event_type=event_type,
                user_id=user_id,
                error=str(e),
                exc_info=True
            )

            # Пытаемся отправить пользователю сообщение об ошибке
            try:
                error_message = (
                    "❌ <b>Произошла ошибка</b>\n\n"
                    "Попробуйте еще раз или вернитесь в главное меню.\n"
                    "Если проблема повторяется, обратитесь к администратору."
                )

                if hasattr(event, 'answer'):
                    # Для сообщений
                    await event.answer(error_message)
                elif hasattr(event, 'message') and hasattr(event.message, 'edit_text'):
                    # Для callback запросов
                    from ..keyboards.main_menu_kb import get_error_keyboard

                    await event.message.edit_text(
                        error_message,
                        reply_markup=get_error_keyboard()
                    )
                    await event.answer("Произошла ошибка", show_alert=True)

            except Exception as send_error:
                logger.error(
                    "Failed to send error message to user",
                    user_id=user_id,
                    error=str(send_error)
                )

            # Не пробрасываем исключение дальше, чтобы бот продолжал работать