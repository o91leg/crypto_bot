"""
Путь: src/data/repositories/user_repository.py
Описание: Репозиторий для работы с пользователями Telegram
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base_repository import BaseRepository
from data.models.user_model import User
from data.models.user_pair_model import UserPair
from data.models.signal_history_model import SignalHistory
from utils.exceptions import RecordNotFoundError, DatabaseError
from utils.logger import log_database_operation
import structlog

# Настройка логирования
logger = structlog.get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями."""

    def __init__(self):
        """Инициализация репозитория пользователей."""
        super().__init__(User)

    async def create_user_from_telegram(
            self,
            session: AsyncSession,
            telegram_user: Any
    ) -> User:
        """
        Создать пользователя из данных Telegram.

        Args:
            session: Сессия базы данных
            telegram_user: Объект пользователя от Telegram

        Returns:
            User: Созданный пользователь
        """
        try:
            user_data = {
                "id": telegram_user.id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
                "notifications_enabled": True,
                "is_active": True,
                "is_blocked": False
            }

            user = await self.create(session, **user_data)

            log_database_operation("INSERT", "users", user_id=user.id)
            logger.info("User created from Telegram data", user_id=user.id, username=user.username)

            return user

        except Exception as e:
            logger.error("Error creating user from Telegram", telegram_id=telegram_user.id, error=str(e))
            raise

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по Telegram ID.

        Args:
            session: Сессия базы данных
            telegram_id: ID пользователя в Telegram

        Returns:
            Optional[User]: Пользователь или None
        """
        try:
            user = await self.get_by_id(session, telegram_id)

            log_database_operation("SELECT", "users", user_id=telegram_id, found=user is not None)

            return user

        except Exception as e:
            logger.error("Error getting user by Telegram ID", telegram_id=telegram_id, error=str(e))
            return None

    async def get_or_create_user(
            self,
            session: AsyncSession,
            telegram_user: Any
    ) -> tuple[User, bool]:
        """
        Получить существующего пользователя или создать нового.

        Args:
            session: Сессия базы данных
            telegram_user: Объект пользователя от Telegram

        Returns:
            tuple[User, bool]: (пользователь, был_ли_создан)
        """
        user_id = telegram_user.id

        # Пытаемся найти существующего пользователя
        existing_user = await self.get_by_telegram_id(session, user_id)

        if existing_user:
            # Обновляем информацию существующего пользователя
            updated = await self._update_user_info(session, existing_user, telegram_user)
            return existing_user, False
        else:
            # Создаем нового пользователя
            new_user = await self.create_user_from_telegram(session, telegram_user)
            return new_user, True

    async def get_active_users(self, session: AsyncSession, limit: Optional[int] = None) -> List[User]:
        """
        Получить всех активных пользователей.

        Args:
            session: Сессия базы данных
            limit: Максимальное количество пользователей

        Returns:
            List[User]: Список активных пользователей
        """
        try:
            stmt = select(User).where(
                and_(
                    User.is_active == True,
                    User.is_blocked == False
                )
            ).order_by(User.created_at.desc())

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            users = list(result.scalars().all())

            log_database_operation("SELECT", "users", filter="active", count=len(users))
            logger.info("Retrieved active users", count=len(users))

            return users

        except Exception as e:
            logger.error("Error getting active users", error=str(e))
            return []

    async def get_users_with_notifications(self, session: AsyncSession) -> List[User]:
        """
        Получить пользователей с включенными уведомлениями.

        Args:
            session: Сессия базы данных

        Returns:
            List[User]: Список пользователей с уведомлениями
        """
        try:
            stmt = select(User).where(
                and_(
                    User.is_active == True,
                    User.is_blocked == False,
                    User.notifications_enabled == True
                )
            )

            result = await session.execute(stmt)
            users = list(result.scalars().all())

            log_database_operation("SELECT", "users", filter="notifications_enabled", count=len(users))
            logger.info("Retrieved users with notifications", count=len(users))

            return users

        except Exception as e:
            logger.error("Error getting users with notifications", error=str(e))
            return []

    async def get_users_with_pairs(self, session: AsyncSession) -> List[User]:
        """
        Получить пользователей, у которых есть отслеживаемые пары.

        Args:
            session: Сессия базы данных

        Returns:
            List[User]: Список пользователей с парами
        """
        try:
            stmt = (
                select(User)
                .join(UserPair, User.id == UserPair.user_id)
                .where(
                    and_(
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                .distinct()
                .options(selectinload(User.user_pairs))
            )

            result = await session.execute(stmt)
            users = list(result.scalars().all())

            log_database_operation("SELECT", "users", filter="with_pairs", count=len(users))
            logger.info("Retrieved users with pairs", count=len(users))

            return users

        except Exception as e:
            logger.error("Error getting users with pairs", error=str(e))
            return []

    async def block_user(self, session: AsyncSession, user_id: int, reason: str = None) -> bool:
        """
        Заблокировать пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            reason: Причина блокировки

        Returns:
            bool: True если пользователь заблокирован
        """
        try:
            user = await self.get_by_id(session, user_id)

            if not user:
                raise RecordNotFoundError("User", user_id)

            user.block_user()

            # Сохраняем причину в настройках
            if reason:
                user.set_setting("block_reason", reason)
                user.set_setting("blocked_at", func.now())

            await session.commit()

            log_database_operation("UPDATE", "users", user_id=user_id, action="blocked")
            logger.info("User blocked", user_id=user_id, reason=reason)

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error blocking user", user_id=user_id, error=str(e))
            return False

    async def unblock_user(self, session: AsyncSession, user_id: int) -> bool:
        """
        Разблокировать пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя

        Returns:
            bool: True если пользователь разблокирован
        """
        try:
            user = await self.get_by_id(session, user_id)

            if not user:
                raise RecordNotFoundError("User", user_id)

            user.unblock_user()

            # Очищаем информацию о блокировке
            user.set_setting("block_reason", None)
            user.set_setting("blocked_at", None)
            user.set_setting("unblocked_at", func.now())

            await session.commit()

            log_database_operation("UPDATE", "users", user_id=user_id, action="unblocked")
            logger.info("User unblocked", user_id=user_id)

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error unblocking user", user_id=user_id, error=str(e))
            return False

    async def toggle_notifications(self, session: AsyncSession, user_id: int) -> Optional[bool]:
        """
        Переключить состояние уведомлений пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя

        Returns:
            Optional[bool]: Новое состояние уведомлений или None при ошибке
        """
        try:
            user = await self.get_by_id(session, user_id)

            if not user:
                raise RecordNotFoundError("User", user_id)

            new_state = user.toggle_notifications()

            await session.commit()

            log_database_operation("UPDATE", "users", user_id=user_id, notifications=new_state)
            logger.info("User notifications toggled", user_id=user_id, new_state=new_state)

            return new_state

        except Exception as e:
            await session.rollback()
            logger.error("Error toggling notifications", user_id=user_id, error=str(e))
            return None

    async def increment_signals_count(self, session: AsyncSession, user_id: int) -> bool:
        """
        Увеличить счетчик полученных сигналов.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя

        Returns:
            bool: True если счетчик увеличен
        """
        try:
            user = await self.get_by_id(session, user_id)

            if not user:
                raise RecordNotFoundError("User", user_id)

            user.increment_signals_count()

            await session.commit()

            log_database_operation("UPDATE", "users", user_id=user_id, action="increment_signals")

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error incrementing signals count", user_id=user_id, error=str(e))
            return False

    async def get_user_statistics(self, session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить статистику пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя

        Returns:
            Optional[Dict[str, Any]]: Статистика пользователя
        """
        try:
            # Получаем пользователя с связанными данными
            stmt = (
                select(User)
                .where(User.id == user_id)
                .options(
                    selectinload(User.user_pairs),
                    selectinload(User.signal_history)
                )
            )

            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Подсчитываем статистику
            pairs_count = len(user.user_pairs)
            signals_count = user.total_signals_received

            # Статистика по типам сигналов
            signal_types_stats = await self._get_signal_types_stats(session, user_id)

            # Активные таймфреймы
            active_timeframes = set()
            for user_pair in user.user_pairs:
                active_timeframes.update(user_pair.get_enabled_timeframes())

            statistics = {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked,
                "notifications_enabled": user.notifications_enabled,
                "pairs_count": pairs_count,
                "total_signals_received": signals_count,
                "active_timeframes_count": len(active_timeframes),
                "active_timeframes": list(active_timeframes),
                "signal_types_stats": signal_types_stats,
                "last_activity": user.updated_at.isoformat() if user.updated_at else None
            }

            log_database_operation("SELECT", "users", user_id=user_id, action="statistics")

            return statistics

        except Exception as e:
            logger.error("Error getting user statistics", user_id=user_id, error=str(e))
            return None

    async def search_users(
            self,
            session: AsyncSession,
            search_term: str,
            limit: int = 50
    ) -> List[User]:
        """
        Поиск пользователей по имени или username.

        Args:
            session: Сессия базы данных
            search_term: Поисковый запрос
            limit: Максимальное количество результатов

        Returns:
            List[User]: Список найденных пользователей
        """
        try:
            search_term = f"%{search_term.lower()}%"

            stmt = select(User).where(
                or_(
                    func.lower(User.username).like(search_term),
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term)
                )
            ).limit(limit)

            result = await session.execute(stmt)
            users = list(result.scalars().all())

            log_database_operation("SELECT", "users", action="search", results=len(users))
            logger.info("User search completed", search_term=search_term, results=len(users))

            return users

        except Exception as e:
            logger.error("Error searching users", search_term=search_term, error=str(e))
            return []

    async def get_users_summary(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Получить сводную статистику по пользователям.

        Args:
            session: Сессия базы данных

        Returns:
            Dict[str, Any]: Сводная статистика
        """
        try:
            # Общее количество пользователей
            total_count = await self.count(session)

            # Активные пользователи
            active_count = await self.count(session, {"is_active": True, "is_blocked": False})

            # Пользователи с уведомлениями
            notifications_count = await self.count(session, {
                "is_active": True,
                "is_blocked": False,
                "notifications_enabled": True
            })

            # Заблокированные пользователи
            blocked_count = await self.count(session, {"is_blocked": True})

            # Пользователи с парами
            stmt = (
                select(func.count(func.distinct(UserPair.user_id)))
                .select_from(UserPair)
                .join(User, User.id == UserPair.user_id)
                .where(User.is_active == True)
            )
            result = await session.execute(stmt)
            users_with_pairs = result.scalar() or 0

            summary = {
                "total_users": total_count,
                "active_users": active_count,
                "users_with_notifications": notifications_count,
                "users_with_pairs": users_with_pairs,
                "blocked_users": blocked_count,
                "inactive_users": total_count - active_count - blocked_count
            }

            log_database_operation("SELECT", "users", action="summary")
            logger.info("Generated users summary", **summary)

            return summary

        except Exception as e:
            logger.error("Error getting users summary", error=str(e))
            return {}

    async def _update_user_info(
            self,
            session: AsyncSession,
            user: User,
            telegram_user: Any
    ) -> bool:
        """
        Обновить информацию пользователя из данных Telegram.

        Args:
            session: Сессия базы данных
            user: Пользователь для обновления
            telegram_user: Данные от Telegram

        Returns:
            bool: True если информация была обновлена
        """
        updated = False

        # Проверяем и обновляем поля
        if user.username != telegram_user.username:
            user.username = telegram_user.username
            updated = True

        if user.first_name != telegram_user.first_name:
            user.first_name = telegram_user.first_name
            updated = True

        if user.last_name != telegram_user.last_name:
            user.last_name = telegram_user.last_name
            updated = True

        # Активируем пользователя если он был неактивен
        if not user.is_active and not user.is_blocked:
            user.activate()
            updated = True

        if updated:
            await session.commit()
            log_database_operation("UPDATE", "users", user_id=user.id, action="info_updated")
            logger.info("User info updated", user_id=user.id)

        return updated

    async def _get_signal_types_stats(self, session: AsyncSession, user_id: int) -> Dict[str, int]:
        """
        Получить статистику по типам сигналов пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя

        Returns:
            Dict[str, int]: Статистика по типам сигналов
        """
        try:
            stmt = (
                select(SignalHistory.signal_type, func.count(SignalHistory.id))
                .where(SignalHistory.user_id == user_id)
                .group_by(SignalHistory.signal_type)
            )

            result = await session.execute(stmt)
            signal_stats = dict(result.fetchall())

            return signal_stats

        except Exception as e:
            logger.error("Error getting signal types stats", user_id=user_id, error=str(e))
            return {}