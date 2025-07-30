"""
Путь: src/data/models/pair_model.py
Описание: Модель торговой пары криптовалют для отслеживания на Binance
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import String, Boolean, select, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from .base_model import Base


class Pair(Base):
    """Модель торговой пары криптовалют."""

    __tablename__ = "pairs"

    # Основные поля
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор пары"
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Символ торговой пары на Binance (например, BTCUSDT)"
    )

    base_asset: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Базовая валюта (например, BTC)"
    )

    quote_asset: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Котируемая валюта (например, USDT)"
    )

    # Статус пары
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Активна ли пара для торговли на Binance"
    )

    is_tracked: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Отслеживается ли пара нашим ботом"
    )

    # Информация о паре
    price_precision: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Точность цены (количество знаков после запятой)"
    )

    quantity_precision: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Точность количества (количество знаков после запятой)"
    )

    # Статистика использования
    users_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Количество пользователей, отслеживающих эту пару"
    )

    signals_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Общее количество сигналов по этой паре"
    )

    # Связи с другими таблицами
    user_pairs = relationship("UserPair", back_populates="pair", cascade="all, delete-orphan")
    candles = relationship("Candle", back_populates="pair", cascade="all, delete-orphan")
    signal_history = relationship("SignalHistory", back_populates="pair", cascade="all, delete-orphan")

    # Индексы для оптимизации запросов
    __table_args__ = (
        Index('idx_pairs_base_quote', 'base_asset', 'quote_asset'),
        Index('idx_pairs_active_tracked', 'is_active', 'is_tracked'),
    )

    def __repr__(self) -> str:
        """Строковое представление торговой пары."""
        return f"<Pair(symbol={self.symbol}, active={self.is_active})>"

    @property
    def display_name(self) -> str:
        """
        Получить отображаемое название пары.

        Returns:
            str: Отформатированное название пары (например, BTC/USDT)
        """
        return f"{self.base_asset}/{self.quote_asset}"

    @property
    def binance_symbol(self) -> str:
        """
        Получить символ пары для Binance API.

        Returns:
            str: Символ пары в формате Binance
        """
        return self.symbol.upper()

    def increment_users_count(self) -> None:
        """Увеличить счетчик пользователей."""
        self.users_count += 1

    def decrement_users_count(self) -> None:
        """Уменьшить счетчик пользователей."""
        if self.users_count > 0:
            self.users_count -= 1

    def increment_signals_count(self) -> None:
        """Увеличить счетчик сигналов."""
        self.signals_count += 1

    def activate(self) -> None:
        """Активировать пару."""
        self.is_active = True
        self.is_tracked = True

    def deactivate(self) -> None:
        """Деактивировать пару."""
        self.is_active = False

    def stop_tracking(self) -> None:
        """Остановить отслеживание пары."""
        self.is_tracked = False

    def start_tracking(self) -> None:
        """Начать отслеживание пары."""
        self.is_tracked = True
        if not self.is_active:
            self.is_active = True

    @classmethod
    async def get_by_symbol(cls, session: AsyncSession, symbol: str) -> Optional["Pair"]:
        """
        Получить пару по символу.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары

        Returns:
            Optional[Pair]: Торговая пара или None
        """
        stmt = select(cls).where(cls.symbol == symbol.upper())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_assets(cls, session: AsyncSession, base_asset: str, quote_asset: str) -> Optional["Pair"]:
        """
        Получить пару по базовой и котируемой валютам.

        Args:
            session: Сессия базы данных
            base_asset: Базовая валюта
            quote_asset: Котируемая валюта

        Returns:
            Optional[Pair]: Торговая пара или None
        """
        stmt = select(cls).where(
            cls.base_asset == base_asset.upper(),
            cls.quote_asset == quote_asset.upper()
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_active_pairs(cls, session: AsyncSession) -> List["Pair"]:
        """
        Получить все активные пары.

        Args:
            session: Сессия базы данных

        Returns:
            List[Pair]: Список активных торговых пар
        """
        stmt = select(cls).where(
            cls.is_active == True,
            cls.is_tracked == True
        ).order_by(cls.users_count.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_tracked_pairs(cls, session: AsyncSession) -> List["Pair"]:
        """
        Получить все отслеживаемые пары.

        Args:
            session: Сессия базы данных

        Returns:
            List[Pair]: Список отслеживаемых пар
        """
        stmt = select(cls).where(cls.is_tracked == True).order_by(cls.users_count.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_popular_pairs(cls, session: AsyncSession, limit: int = 10) -> List["Pair"]:
        """
        Получить популярные пары по количеству пользователей.

        Args:
            session: Сессия базы данных
            limit: Максимальное количество пар

        Returns:
            List[Pair]: Список популярных пар
        """
        stmt = (
            select(cls)
            .where(cls.is_active == True, cls.is_tracked == True)
            .order_by(cls.users_count.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def search_by_base_asset(cls, session: AsyncSession, base_asset: str) -> List["Pair"]:
        """
        Найти пары по базовой валюте.

        Args:
            session: Сессия базы данных
            base_asset: Базовая валюта для поиска

        Returns:
            List[Pair]: Список найденных пар
        """
        stmt = (
            select(cls)
            .where(
                cls.base_asset.ilike(f"%{base_asset.upper()}%"),
                cls.is_active == True
            )
            .order_by(cls.users_count.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def create_from_symbol(
            cls,
            session: AsyncSession,
            symbol: str,
            price_precision: Optional[int] = None,
            quantity_precision: Optional[int] = None
    ) -> "Pair":
        """
        Создать торговую пару из символа.

        Args:
            session: Сессия базы данных
            symbol: Символ пары (например, BTCUSDT)
            price_precision: Точность цены
            quantity_precision: Точность количества

        Returns:
            Pair: Созданная торговая пара

        Raises:
            ValueError: Если символ имеет неверный формат
        """
        symbol = symbol.upper()

        # Продвинутый парсинг символа
        base_asset, quote_asset = cls._parse_symbol(symbol)

        if not base_asset or not quote_asset:
            raise ValueError(f"Cannot parse symbol: {symbol}")

        # Проверяем, не существует ли уже такая пара
        existing_pair = await cls.get_by_symbol(session, symbol)
        if existing_pair:
            return existing_pair

        pair = cls(
            symbol=symbol,
            base_asset=base_asset,
            quote_asset=quote_asset,
            price_precision=price_precision,
            quantity_precision=quantity_precision,
        )

        session.add(pair)
        await session.flush()
        return pair

    @staticmethod
    def _parse_symbol(symbol: str) -> tuple[str, str]:
        """
        Разобрать символ торговой пары на базовую и котируемую валюты.

        Args:
            symbol: Символ для разбора

        Returns:
            tuple[str, str]: (base_asset, quote_asset)
        """
        # Известные котируемые валюты в порядке приоритета (от самых длинных к коротким)
        quote_currencies = [
            'USDT', 'USDC', 'BUSD', 'TUSD', 'USDP',  # Стейблкоины
            'BTC', 'ETH', 'BNB', 'XRP', 'ADA',  # Основные криптовалюты
            'DOT', 'SOL', 'MATIC', 'AVAX', 'DOGE',  # Популярные альткоины
            'TRX', 'LTC', 'LINK', 'UNI', 'ATOM',  # Другие популярные
            'USD', 'EUR', 'GBP', 'JPY', 'RUB',  # Фиатные валюты
        ]

        # Пробуем найти подходящую котируемую валюту
        for quote in quote_currencies:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base_asset = symbol[:-len(quote)]
                quote_asset = quote

                # Дополнительная проверка: базовая валюта должна быть разумной длины
                if 2 <= len(base_asset) <= 10:
                    return base_asset, quote_asset

        # Если не удалось разобрать, возвращаем пустые строки
        return "", ""

    @classmethod
    async def get_by_symbol(
            cls,
            session: AsyncSession,
            symbol: str
    ) -> Optional["Pair"]:
        """
        Получить пару по символу.

        Args:
            session: Сессия базы данных
            symbol: Символ пары

        Returns:
            Optional[Pair]: Найденная пара или None
        """
        stmt = select(cls).where(cls.symbol == symbol.upper())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def to_dict(self, include_stats: bool = False) -> Dict[str, Any]:
        """
        Преобразовать пару в словарь.

        Args:
            include_stats: Включить ли статистику

        Returns:
            Dict[str, Any]: Словарь с данными пары
        """
        data = {
            "id": self.id,
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "is_tracked": self.is_tracked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_stats:
            data.update({
                "users_count": self.users_count,
                "signals_count": self.signals_count,
                "price_precision": self.price_precision,
                "quantity_precision": self.quantity_precision,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            })

        return data