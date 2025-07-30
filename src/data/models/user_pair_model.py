"""
Путь: src/data/models/user_pair_model.py
Описание: Модель связи пользователь-пара с настройками таймфреймов
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Dict, List, Optional, Any
from sqlalchemy import BigInteger, Integer, JSON, ForeignKey, select, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .base_model import Base


class UserPair(Base):
    """Модель связи пользователя с торговой парой."""

    __tablename__ = "user_pairs"

    # Составной первичный ключ
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="ID пользователя Telegram"
    )

    pair_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pairs.id", ondelete="CASCADE"),
        primary_key=True,
        comment="ID торговой пары"
    )

    # Настройки таймфреймов в JSON формате
    timeframes: Mapped[Dict[str, bool]] = mapped_column(
        JSON,
        nullable=False,
        comment="Настройки включенных таймфреймов {timeframe: enabled}"
    )

    # Дополнительные настройки для пары
    custom_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Дополнительные пользовательские настройки для пары"
    )

    # Статистика
    signals_received: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Количество полученных сигналов по этой паре"
    )

    # Связи с другими таблицами
    user = relationship("User", back_populates="user_pairs")
    pair = relationship("Pair", back_populates="user_pairs")

    # Индексы для оптимизации
    __table_args__ = (
        Index('idx_user_pairs_user_id', 'user_id'),
        Index('idx_user_pairs_pair_id', 'pair_id'),
    )

    def __repr__(self) -> str:
        """Строковое представление связи пользователь-пара."""
        return f"<UserPair(user_id={self.user_id}, pair_id={self.pair_id})>"

    def __init__(self, user_id: int, pair_id: int, timeframes: Optional[Dict[str, bool]] = None, **kwargs):
        """
        Инициализация связи пользователь-пара.

        Args:
            user_id: ID пользователя
            pair_id: ID пары
            timeframes: Настройки таймфреймов
            **kwargs: Дополнительные параметры
        """
        super().__init__(**kwargs)
        self.user_id = user_id
        self.pair_id = pair_id

        # Устанавливаем дефолтные таймфреймы если не указаны
        if timeframes is None:
            from config.bot_config import get_bot_config
            config = get_bot_config()
            self.timeframes = {tf: True for tf in config.default_timeframes}
        else:
            self.timeframes = timeframes

    def is_timeframe_enabled(self, timeframe: str) -> bool:
        """
        Проверить, включен ли таймфрейм.

        Args:
            timeframe: Таймфрейм для проверки

        Returns:
            bool: True если таймфрейм включен
        """
        return self.timeframes.get(timeframe, False)

    def enable_timeframe(self, timeframe: str) -> None:
        """
        Включить таймфрейм.

        Args:
            timeframe: Таймфрейм для включения
        """
        if not self.timeframes:
            self.timeframes = {}

        new_timeframes = self.timeframes.copy()
        new_timeframes[timeframe] = True
        self.timeframes = new_timeframes

        from sqlalchemy.orm import attributes
        attributes.flag_modified(self, "timeframes")

    def disable_timeframe(self, timeframe: str) -> None:
        """
        Отключить таймфрейм.

        Args:
            timeframe: Таймфрейм для отключения
        """
        if not self.timeframes:
            self.timeframes = {}

        new_timeframes = self.timeframes.copy()
        new_timeframes[timeframe] = False
        self.timeframes = new_timeframes

        from sqlalchemy.orm import attributes
        attributes.flag_modified(self, "timeframes")

    def toggle_timeframe(self, timeframe: str) -> bool:
        """
        Переключить состояние таймфрейма.

        Args:
            timeframe: Таймфрейм для переключения

        Returns:
            bool: Новое состояние таймфрейма
        """
        if not self.timeframes:
            self.timeframes = {}

        current_state = self.timeframes.get(timeframe, False)
        new_state = not current_state

        # Создаем НОВЫЙ словарь чтобы SQLAlchemy заметил изменение
        new_timeframes = self.timeframes.copy()
        new_timeframes[timeframe] = new_state
        self.timeframes = new_timeframes

        # ВАЖНО: Помечаем атрибут как изменённый
        from sqlalchemy.orm import attributes
        attributes.flag_modified(self, "timeframes")

        return new_state

    def get_enabled_timeframes(self) -> List[str]:
        """
        Получить список включенных таймфреймов.

        Returns:
            List[str]: Список включенных таймфреймов
        """
        if not self.timeframes:
            return []
        return [tf for tf, enabled in self.timeframes.items() if enabled]

    def set_timeframes(self, timeframes_dict: Dict[str, bool]) -> None:
        """
        Установить настройки таймфреймов.

        Args:
            timeframes_dict: Словарь с настройками таймфреймов
        """
        self.timeframes = timeframes_dict.copy()

        from sqlalchemy.orm import attributes
        attributes.flag_modified(self, "timeframes")

    def reset_to_default_timeframes(self) -> None:
        """Сбросить таймфреймы к значениям по умолчанию."""
        from config.bot_config import get_bot_config
        config = get_bot_config()
        self.timeframes = {tf: True for tf in config.default_timeframes}

    def get_custom_setting(self, key: str, default: Any = None) -> Any:
        """
        Получить пользовательскую настройку.

        Args:
            key: Ключ настройки
            default: Значение по умолчанию

        Returns:
            Any: Значение настройки
        """
        if not self.custom_settings:
            return default
        return self.custom_settings.get(key, default)

    def set_custom_setting(self, key: str, value: Any) -> None:
        """
        Установить пользовательскую настройку.

        Args:
            key: Ключ настройки
            value: Значение настройки
        """
        if not self.custom_settings:
            self.custom_settings = {}
        self.custom_settings[key] = value

    def increment_signals_count(self) -> None:
        """Увеличить счетчик полученных сигналов."""
        self.signals_received += 1

    @classmethod
    async def get_by_user_and_pair(cls, session: AsyncSession, user_id: int, pair_id: int) -> Optional["UserPair"]:
        """Получить связь пользователь-пара."""
        from sqlalchemy.orm import joinedload

        stmt = (
            select(cls)
            .where(cls.user_id == user_id, cls.pair_id == pair_id)
            .options(joinedload(cls.pair))
        )
        result = await session.execute(stmt)
        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_user_pairs(cls, session: AsyncSession, user_id: int) -> List["UserPair"]:
        """Получить все пары пользователя."""
        from sqlalchemy.orm import joinedload

        stmt = (
            select(cls)
            .where(cls.user_id == user_id)
            .options(joinedload(cls.pair))
        )
        result = await session.execute(stmt)
        return list(result.unique().scalars().all())

    @classmethod
    async def get_pair_users(cls, session: AsyncSession, pair_id: int) -> List["UserPair"]:
        """
        Получить всех пользователей пары.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            List[UserPair]: Список пользователей пары
        """
        stmt = (
            select(cls)
            .where(cls.pair_id == pair_id)
            .options(
                selectinload(cls.user)
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_users_with_timeframe(
        cls,
        session: AsyncSession,
        pair_id: int,
        timeframe: str
    ) -> List["UserPair"]:
        """
        Получить пользователей с включенным таймфреймом для пары.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм

        Returns:
            List[UserPair]: Список пользователей с включенным таймфреймом
        """
        # Используем JSON оператор для PostgreSQL
        stmt = (
            select(cls)
            .where(
                cls.pair_id == pair_id,
                cls.timeframes[timeframe].astext.cast(Boolean) == True
            )
            .options(
                selectinload(cls.user)
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def create_user_pair(
        cls,
        session: AsyncSession,
        user_id: int,
        pair_id: int,
        timeframes: Optional[Dict[str, bool]] = None
    ) -> "UserPair":
        """
        Создать связь пользователь-пара.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            pair_id: ID пары
            timeframes: Настройки таймфреймов

        Returns:
            UserPair: Созданная связь
        """
        user_pair = cls(user_id=user_id, pair_id=pair_id, timeframes=timeframes)
        session.add(user_pair)
        await session.flush()
        return user_pair

    def to_dict(self, include_pair_info: bool = False) -> Dict[str, Any]:
        """
        Преобразовать связь в словарь.

        Args:
            include_pair_info: Включить ли информацию о паре

        Returns:
            Dict[str, Any]: Словарь с данными связи
        """
        data = {
            "user_id": self.user_id,
            "pair_id": self.pair_id,
            "timeframes": self.timeframes,
            "enabled_timeframes": self.get_enabled_timeframes(),
            "signals_received": self.signals_received,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_pair_info and hasattr(self, 'pair') and self.pair:
            data["pair_info"] = {
                "symbol": self.pair.symbol,
                "display_name": self.pair.display_name,
                "base_asset": self.pair.base_asset,
                "quote_asset": self.pair.quote_asset,
            }

        if self.custom_settings:
            data["custom_settings"] = self.custom_settings

        return data