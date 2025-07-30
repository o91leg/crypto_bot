"""
Путь: src/data/models/candle_model.py
Описание: Модель свечи (OHLCV данные) для хранения ценовых данных
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import (
    Integer, String, BigInteger, Numeric, ForeignKey,
    select, desc, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from .base_model import Base


class Candle(Base):
    """Модель свечи с OHLCV данными."""

    __tablename__ = "candles"

    # Основные поля
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор свечи"
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
        comment="Таймфрейм свечи (1m, 5m, 1h, etc.)"
    )

    # Временные метки
    open_time: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Время открытия свечи (Unix timestamp в миллисекундах)"
    )

    close_time: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Время закрытия свечи (Unix timestamp в миллисекундах)"
    )

    # OHLC цены
    open_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Цена открытия"
    )

    high_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Максимальная цена"
    )

    low_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Минимальная цена"
    )

    close_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
        comment="Цена закрытия"
    )

    # Объем торгов
    volume: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        comment="Объем торгов в базовой валюте"
    )

    quote_volume: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 8),
        nullable=True,
        comment="Объем торгов в котируемой валюте"
    )

    # Количество сделок
    trades_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Количество сделок в свече"
    )

    # Флаг завершенности свечи
    is_closed: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Завершена ли свеча (False для текущей свечи)"
    )

    # Связи с другими таблицами
    pair = relationship("Pair", back_populates="candles")

    # Ограничения и индексы
    __table_args__ = (
        UniqueConstraint('pair_id', 'timeframe', 'open_time', name='uq_candles_pair_timeframe_time'),
        Index('idx_candles_pair_timeframe', 'pair_id', 'timeframe'),
        Index('idx_candles_time_range', 'pair_id', 'timeframe', 'open_time'),
        Index('idx_candles_recent', 'pair_id', 'timeframe', 'open_time', postgresql_using='btree'),
    )

    def __repr__(self) -> str:
        """Строковое представление свечи."""
        return f"<Candle(pair_id={self.pair_id}, timeframe={self.timeframe}, time={self.open_time})>"

    @property
    def open_datetime(self) -> datetime:
        """
        Время открытия свечи как datetime объект.

        Returns:
            datetime: Время открытия свечи
        """
        return datetime.fromtimestamp(self.open_time / 1000)

    @property
    def close_datetime(self) -> datetime:
        """
        Время закрытия свечи как datetime объект.

        Returns:
            datetime: Время закрытия свечи
        """
        return datetime.fromtimestamp(self.close_time / 1000)

    @property
    def price_change(self) -> Decimal:
        """
        Изменение цены (close - open).

        Returns:
            Decimal: Абсолютное изменение цены
        """
        return self.close_price - self.open_price

    @property
    def price_change_percent(self) -> Decimal:
        """
        Процентное изменение цены.

        Returns:
            Decimal: Процентное изменение цены
        """
        if self.open_price == 0:
            return Decimal('0')
        return (self.price_change / self.open_price) * Decimal('100')

    @property
    def typical_price(self) -> Decimal:
        """
        Типичная цена (HLC/3).

        Returns:
            Decimal: Типичная цена
        """
        return (self.high_price + self.low_price + self.close_price) / Decimal('3')

    @property
    def median_price(self) -> Decimal:
        """
        Медианная цена (HL/2).

        Returns:
            Decimal: Медианная цена
        """
        return (self.high_price + self.low_price) / Decimal('2')

    @property
    def weighted_price(self) -> Decimal:
        """
        Взвешенная цена (OHLC/4).

        Returns:
            Decimal: Взвешенная цена
        """
        return (self.open_price + self.high_price + self.low_price + self.close_price) / Decimal('4')

    @property
    def body_size(self) -> Decimal:
        """
        Размер тела свечи.

        Returns:
            Decimal: Размер тела свечи
        """
        return abs(self.close_price - self.open_price)

    @property
    def upper_shadow(self) -> Decimal:
        """
        Размер верхней тени.

        Returns:
            Decimal: Размер верхней тени
        """
        return self.high_price - max(self.open_price, self.close_price)

    @property
    def lower_shadow(self) -> Decimal:
        """
        Размер нижней тени.

        Returns:
            Decimal: Размер нижней тени
        """
        return min(self.open_price, self.close_price) - self.low_price

    @property
    def is_bullish(self) -> bool:
        """
        Является ли свеча бычьей (растущей).

        Returns:
            bool: True если свеча бычья
        """
        return self.close_price > self.open_price

    @property
    def is_bearish(self) -> bool:
        """
        Является ли свеча медвежьей (падающей).

        Returns:
            bool: True если свеча медвежья
        """
        return self.close_price < self.open_price

    @property
    def is_doji(self) -> bool:
        """
        Является ли свеча доджи (цены открытия и закрытия равны).

        Returns:
            bool: True если свеча доджи
        """
        return self.close_price == self.open_price

    def get_ohlc_array(self) -> List[float]:
        """
        Получить OHLC данные как массив.

        Returns:
            List[float]: Массив [open, high, low, close]
        """
        return [
            float(self.open_price),
            float(self.high_price),
            float(self.low_price),
            float(self.close_price)
        ]

    def get_ohlcv_array(self) -> List[float]:
        """
        Получить OHLCV данные как массив.

        Returns:
            List[float]: Массив [open, high, low, close, volume]
        """
        return [
            float(self.open_price),
            float(self.high_price),
            float(self.low_price),
            float(self.close_price),
            float(self.volume)
        ]

    @classmethod
    async def get_latest_candles(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            limit: int = 100
    ) -> List["Candle"]:
        """
        Получить последние свечи для пары и таймфрейма.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм
            limit: Количество свечей

        Returns:
            List[Candle]: Список свечей, отсортированный по времени
        """
        stmt = (
            select(cls)
            .where(
                cls.pair_id == pair_id,
                cls.timeframe == timeframe,
                cls.is_closed == True
            )
            .order_by(desc(cls.open_time))
            .limit(limit)
        )
        result = await session.execute(stmt)
        candles = list(result.scalars().all())
        return list(reversed(candles))  # Возвращаем в хронологическом порядке

    @classmethod
    async def get_candles_range(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            start_time: int,
            end_time: int
    ) -> List["Candle"]:
        """
        Получить свечи в диапазоне времени.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм
            start_time: Начальное время (Unix timestamp в мс)
            end_time: Конечное время (Unix timestamp в мс)

        Returns:
            List[Candle]: Список свечей в диапазоне
        """
        stmt = (
            select(cls)
            .where(
                cls.pair_id == pair_id,
                cls.timeframe == timeframe,
                cls.open_time >= start_time,
                cls.open_time <= end_time
            )
            .order_by(cls.open_time)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_latest_candle(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str
    ) -> Optional["Candle"]:
        """
        Получить последнюю свечу для пары и таймфрейма.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм

        Returns:
            Optional[Candle]: Последняя свеча или None
        """
        stmt = (
            select(cls)
            .where(
                cls.pair_id == pair_id,
                cls.timeframe == timeframe,
                cls.is_closed == True
            )
            .order_by(desc(cls.open_time))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_candle(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            open_time: int,
            close_time: int,
            open_price: Decimal,
            high_price: Decimal,
            low_price: Decimal,
            close_price: Decimal,
            volume: Decimal,
            quote_volume: Decimal,
            trades_count: int,
            taker_buy_base_volume: Decimal,
            taker_buy_quote_volume: Decimal,
            is_closed: bool = True
    ) -> "Candle":
        """
        Создать новую свечу в базе данных.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм свечи
            open_time: Время открытия (Unix timestamp в мс)
            close_time: Время закрытия (Unix timestamp в мс)
            open_price: Цена открытия
            high_price: Максимальная цена
            low_price: Минимальная цена
            close_price: Цена закрытия
            volume: Объем в базовой валюте
            quote_volume: Объем в котируемой валюте
            trades_count: Количество сделок
            taker_buy_base_volume: Объем покупок тейкера в базовой валюте
            taker_buy_quote_volume: Объем покупок тейкера в котируемой валюте
            is_closed: Закрыта ли свеча

        Returns:
            Candle: Созданная свеча

        Raises:
            ValueError: При неверных параметрах
        """
        # Валидация данных
        if open_time <= 0 or close_time <= 0:
            raise ValueError("Invalid time values")

        if open_time >= close_time:
            raise ValueError("Open time must be less than close time")

        if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
            raise ValueError("Prices must be positive")

        if high_price < max(open_price, close_price):
            raise ValueError("High price must be greater than or equal to open/close prices")

        if low_price > min(open_price, close_price):
            raise ValueError("Low price must be less than or equal to open/close prices")

        candle = cls(
            pair_id=pair_id,
            timeframe=timeframe,
            open_time=open_time,
            close_time=close_time,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            quote_volume=quote_volume,
            trades_count=trades_count,
            taker_buy_base_volume=taker_buy_base_volume,
            taker_buy_quote_volume=taker_buy_quote_volume,
            is_closed=is_closed
        )

        session.add(candle)
        await session.flush()
        return candle

    @classmethod
    async def bulk_create_candles(
            cls,
            session: AsyncSession,
            candles_data: List[Dict[str, Any]]
    ) -> List["Candle"]:
        """
        Создать несколько свечей за одну операцию.

        Args:
            session: Сессия базы данных
            candles_data: Список данных свечей

        Returns:
            List[Candle]: Список созданных свечей
        """
        candles = []
        for data in candles_data:
            candle = cls(**data)
            session.add(candle)
            candles.append(candle)

        await session.flush()
        return candles

    @classmethod
    async def get_latest_candle(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str
    ) -> Optional["Candle"]:
        """
        Получить последнюю свечу.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм

        Returns:
            Optional[Candle]: Последняя свеча или None
        """
        stmt = (
            select(cls)
            .where(
                cls.pair_id == pair_id,
                cls.timeframe == timeframe
            )
            .order_by(desc(cls.open_time))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_candle_from_params(
            cls,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            kline_data: Dict[str, Any]
    ) -> "Candle":
        """
        Создать свечу из данных kline.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм
            kline_data: Данные kline от Binance

        Returns:
            Candle: Созданная свеча
        """
        candle = cls(
            pair_id=pair_id,
            timeframe=timeframe,
            open_time=int(kline_data['t']),
            close_time=int(kline_data['T']),
            open_price=Decimal(str(kline_data['o'])),
            high_price=Decimal(str(kline_data['h'])),
            low_price=Decimal(str(kline_data['l'])),
            close_price=Decimal(str(kline_data['c'])),
            volume=Decimal(str(kline_data['v'])),
            quote_volume=Decimal(str(kline_data['q'])),
            trades_count=int(kline_data['n']),
            is_closed=bool(kline_data['x'])
        )

        session.add(candle)
        await session.flush()
        return candle

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать свечу в словарь.

        Returns:
            Dict[str, Any]: Словарь с данными свечи
        """
        return {
            "id": self.id,
            "pair_id": self.pair_id,
            "timeframe": self.timeframe,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open_datetime": self.open_datetime.isoformat(),
            "close_datetime": self.close_datetime.isoformat(),
            "open_price": float(self.open_price),
            "high_price": float(self.high_price),
            "low_price": float(self.low_price),
            "close_price": float(self.close_price),
            "volume": float(self.volume),
            "quote_volume": float(self.quote_volume) if self.quote_volume else None,
            "trades_count": self.trades_count,
            "is_closed": self.is_closed,
            "price_change": float(self.price_change),
            "price_change_percent": float(self.price_change_percent),
            "is_bullish": self.is_bullish,
            "is_bearish": self.is_bearish,
        }

    @classmethod
    async def count_candles(cls, session: AsyncSession, pair_id: int, timeframe: str) -> int:
        """
        Подсчитать количество свечей для пары и таймфрейма.

        Args:
            session: Сессия базы данных
            pair_id: ID пары
            timeframe: Таймфрейм

        Returns:
            int: Количество свечей
        """
        from sqlalchemy import func, select

        stmt = select(func.count(cls.id)).where(
            cls.pair_id == pair_id,
            cls.timeframe == timeframe
        )
        result = await session.execute(stmt)
        return result.scalar() or 0