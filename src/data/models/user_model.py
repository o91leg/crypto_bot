"""
Путь: src/data/models/user_model.py
Описание: Модель пользователя Telegram для хранения данных и настроек
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import BigInteger, String, Boolean, JSON, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from .base_model import Base


class User(Base):
    """Модель пользователя Telegram."""

    __tablename__ = "users"

    # Основные поля
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram user ID (используется как первичный ключ)"
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Telegram username пользователя"
    )

    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Имя пользователя в Telegram"
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Фамилия пользователя в Telegram"
    )

    language_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default="en",
        comment="Код языка пользователя"
    )

    # Настройки уведомлений
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Включены ли уведомления для пользователя"
    )

    # Настройки пользователя в JSON
    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Дополнительные настройки пользователя в формате JSON"
    )

    # Статистика пользователя
    total_signals_received: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Общее количество полученных сигналов"
    )

    # Статус пользователя
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Активен ли пользователь"
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Заблокирован ли пользователь"
    )

    # Связи с другими таблицами
    user_pairs = relationship("UserPair", back_populates="user", cascade="all, delete-orphan")
    signal_history = relationship("SignalHistory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """Строковое представление пользователя."""
        display_name = self.username or self.first_name or str(self.id)
        return f"<User(id={self.id}, name={display_name})>"

    @property
    def display_name(self) -> str:
        """
        Получить отображаемое имя пользователя.

        Returns:
            str: Отображаемое имя пользователя
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.id}"

    @property
    def full_name(self) -> str:
        """
        Получить полное имя пользователя.

        Returns:
            str: Полное имя пользователя
        """
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else self.display_name

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Получить значение настройки пользователя.

        Args:
            key: Ключ настройки
            default: Значение по умолчанию

        Returns:
            Any: Значение настройки
        """
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Установить значение настройки пользователя.

        Args:
            key: Ключ настройки
            value: Значение настройки
        """
        if not self.settings:
            self.settings = {}
        self.settings[key] = value

    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """
        Обновить несколько настроек пользователя.

        Args:
            new_settings: Словарь с новыми настройками
        """
        if not self.settings:
            self.settings = {}
        self.settings.update(new_settings)

    def increment_signals_count(self) -> None:
        """Увеличить счетчик полученных сигналов."""
        self.total_signals_received += 1

    def toggle_notifications(self) -> bool:
        """
        Переключить состояние уведомлений.

        Returns:
            bool: Новое состояние уведомлений
        """
        self.notifications_enabled = not self.notifications_enabled
        return self.notifications_enabled

    def block_user(self) -> None:
        """Заблокировать пользователя."""
        self.is_blocked = True
        self.is_active = False

    def unblock_user(self) -> None:
        """Разблокировать пользователя."""
        self.is_blocked = False
        self.is_active = True

    def deactivate(self) -> None:
        """Деактивировать пользователя."""
        self.is_active = False

    def activate(self) -> None:
        """Активировать пользователя."""
        self.is_active = True
        self.is_blocked = False

    @classmethod
    async def get_by_telegram_id(cls, session: AsyncSession, telegram_id: int) -> Optional["User"]:
        """
        Получить пользователя по Telegram ID.

        Args:
            session: Сессия базы данных
            telegram_id: Telegram ID пользователя

        Returns:
            Optional[User]: Пользователь или None
        """
        stmt = select(cls).where(cls.id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_active_users(cls, session: AsyncSession) -> List["User"]:
        """
        Получить всех активных пользователей.

        Args:
            session: Сессия базы данных

        Returns:
            List[User]: Список активных пользователей
        """
        stmt = select(cls).where(
            cls.is_active == True,
            cls.is_blocked == False
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_users_with_notifications(cls, session: AsyncSession) -> List["User"]:
        """
        Получить пользователей с включенными уведомлениями.

        Args:
            session: Сессия базы данных

        Returns:
            List[User]: Список пользователей с уведомлениями
        """
        stmt = select(cls).where(
            cls.is_active == True,
            cls.is_blocked == False,
            cls.notifications_enabled == True
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Преобразовать пользователя в словарь.

        Args:
            include_sensitive: Включить ли чувствительные данные

        Returns:
            Dict[str, Any]: Словарь с данными пользователя
        """
        data = {
            "id": self.id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "notifications_enabled": self.notifications_enabled,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_sensitive:
            data.update({
                "settings": self.settings,
                "total_signals_received": self.total_signals_received,
                "is_blocked": self.is_blocked,
                "language_code": self.language_code,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            })

        return data