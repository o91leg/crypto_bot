"""
Путь: src/data/models/signal_history_model.py
Описание: Модель истории сигналов для отслеживания отправленных уведомлений
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import (
    Integer, String, BigInteger, Numeric, ForeignKey, JSON,
    select, desc, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from .base_model import Base


class SignalHistory(Base):
    """Модель истории отправленных сигналов."""

    __tablename__ = "signal_history"

    # Основные поля
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор записи"
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID пользователя, которому отправлен сигнал"
    )

    pair_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pairs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID торговой пары"
    )

    timeframe: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        index=True,
        comment="Таймфрейм сигнала"
    )

    signal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Тип сигнала (rsi_oversold, rsi_overbought, ema_cross, etc.)"
    )

    signal_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="Значение индикатора при генерации сигнала"
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Цена на момент сигнала"
    )

    additional_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Дополнительные данные сигнала в JSON формате"
    )

    sent_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Время отправки сигнала"
    )

    # Связи с другими таблицами
    user = relationship("User", back_populates="signal_history")
    pair = relationship("Pair", back_populates="signal_history")

    # Индексы для оптимизации запросов
    __table_args__ = (
        Index('idx_signal_history_user_pair', 'user_id', 'pair_id'),
        Index('idx_signal_history_type_time', 'signal_type', 'sent_at'),
        Index('idx_signal_history_recent', 'user_id', 'pair_id', 'timeframe', 'sent_at'),
    )

    def __repr__(self) -> str:
        """Строковое представление записи истории сигналов."""
        return f"<SignalHistory(user_id={self.user_id}, signal_type={self.signal_type}, sent_at={self.sent_at})>"

    @property
    def signal_display_name(self) -> str:
        """
        Получить отображаемое название сигнала.

        Returns:
            str: Человекочитаемое название сигнала
        """
        signal_names = {
            "rsi_oversold_strong": "RSI: Сильная перепроданность",
            "rsi_oversold_medium": "RSI: Средняя перепроданность",
            "rsi_oversold_normal": "RSI: Перепроданность",
            "rsi_overbought_normal": "RSI: Перекупленность",
            "rsi_overbought_medium": "RSI: Средняя перекупленность",
            "rsi_overbought_strong": "RSI: Сильная перекупленность",
            "ema_cross_up": "EMA: Пересечение вверх",
            "ema_cross_down": "EMA: Пересечение вниз",
            "volume_spike": "Объем: Всплеск активности",
        }
        return signal_names.get(self.signal_type, self.signal_type.replace("_", " ").title())

    @classmethod
    async def create_signal_record(
            cls,
            session: AsyncSession,
            user_id: int,
            pair_id: int,
            timeframe: str,
            signal_type: str,
            signal_value: Optional[float],
            price: float,
            additional_data: Optional[Dict[str, Any]] = None
    ) -> "SignalHistory":
        """
        Создать запись о сигнале.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            pair_id: ID пары
            timeframe: Таймфрейм
            signal_type: Тип сигнала
            signal_value: Значение индикатора
            price: Цена
            additional_data: Дополнительные данные

        Returns:
            SignalHistory: Созданная запись
        """
        signal_record = cls(
            user_id=user_id,
            pair_id=pair_id,
            timeframe=timeframe,
            signal_type=signal_type,
            signal_value=Decimal(str(signal_value)) if signal_value is not None else None,
            price=Decimal(str(price)),
            additional_data=additional_data,
            sent_at=datetime.utcnow()
        )

        session.add(signal_record)
        await session.flush()
        return signal_record

    @classmethod
    async def get_user_recent_signals(
            cls,
            session: AsyncSession,
            user_id: int,
            limit: int = 50
    ) -> List["SignalHistory"]:
        """
        Получить последние сигналы пользователя.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            limit: Максимальное количество записей

        Returns:
            List[SignalHistory]: Список последних сигналов
        """
        stmt = (
            select(cls)
            .where(cls.user_id == user_id)
            .order_by(desc(cls.sent_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_last_signal(
            cls,
            session: AsyncSession,
            user_id: int,
            pair_id: int,
            timeframe: str,
            signal_type: str
    ) -> Optional["SignalHistory"]:
        """
        Получить последний сигнал определенного типа.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            pair_id: ID пары
            timeframe: Таймфрейм
            signal_type: Тип сигнала

        Returns:
            Optional[SignalHistory]: Последний сигнал или None
        """
        stmt = (
            select(cls)
            .where(
                cls.user_id == user_id,
                cls.pair_id == pair_id,
                cls.timeframe == timeframe,
                cls.signal_type == signal_type
            )
            .order_by(desc(cls.sent_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_signals_count(
            cls,
            session: AsyncSession,
            user_id: Optional[int] = None,
            pair_id: Optional[int] = None,
            signal_type: Optional[str] = None
    ) -> int:
        """
        Получить количество сигналов по фильтрам.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя (опционально)
            pair_id: ID пары (опционально)
            signal_type: Тип сигнала (опционально)

        Returns:
            int: Количество сигналов
        """
        stmt = select(cls)

        if user_id is not None:
            stmt = stmt.where(cls.user_id == user_id)
        if pair_id is not None:
            stmt = stmt.where(cls.pair_id == pair_id)
        if signal_type is not None:
            stmt = stmt.where(cls.signal_type == signal_type)

        result = await session.execute(stmt)
        return len(list(result.scalars().all()))

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать запись в словарь.

        Returns:
            Dict[str, Any]: Словарь с данными записи
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "pair_id": self.pair_id,
            "timeframe": self.timeframe,
            "signal_type": self.signal_type,
            "signal_display_name": self.signal_display_name,
            "signal_value": float(self.signal_value) if self.signal_value else None,
            "price": float(self.price),
            "additional_data": self.additional_data,
            "sent_at": self.sent_at.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }