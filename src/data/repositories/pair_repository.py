"""
Путь: src/data/repositories/pair_repository.py
Описание: Репозиторий для работы с торговыми парами криптовалют
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base_repository import BaseRepository
from data.models.pair_model import Pair
from data.models.user_pair_model import UserPair
from data.models.candle_model import Candle
from utils.exceptions import RecordNotFoundError, RecordAlreadyExistsError, DatabaseError
from utils.validators import validate_trading_pair_symbol, extract_base_quote_assets
from utils.logger import log_database_operation
import structlog

# Настройка логирования
logger = structlog.get_logger(__name__)


class PairRepository(BaseRepository[Pair]):
    """Репозиторий для работы с торговыми парами."""

    def __init__(self):
        """Инициализация репозитория торговых пар."""
        super().__init__(Pair)

    async def create_pair_from_symbol(
            self,
            session: AsyncSession,
            symbol: str,
            price_precision: Optional[int] = None,
            quantity_precision: Optional[int] = None,
            is_active: bool = True
    ) -> Pair:
        """
        Создать торговую пару из символа.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары (например, BTCUSDT)
            price_precision: Точность цены
            quantity_precision: Точность количества
            is_active: Активна ли пара

        Returns:
            Pair: Созданная торговая пара
        """
        # Валидируем символ
        is_valid, error_msg = validate_trading_pair_symbol(symbol)
        if not is_valid:
            raise ValueError(f"Invalid symbol format: {error_msg}")

        symbol = symbol.upper()

        # Проверяем, не существует ли уже такая пара
        existing_pair = await self.get_by_symbol(session, symbol)
        if existing_pair:
            raise RecordAlreadyExistsError("Pair", symbol)

        try:
            # Извлекаем базовую и котируемую валюты
            base_asset, quote_asset = extract_base_quote_assets(symbol)

            if not base_asset or not quote_asset:
                raise ValueError(f"Cannot parse base and quote assets from symbol: {symbol}")

            # Создаем пару
            pair_data = {
                "symbol": symbol,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "is_active": is_active,
                "is_tracked": True,
                "price_precision": price_precision,
                "quantity_precision": quantity_precision,
                "users_count": 0,
                "signals_count": 0
            }

            pair = await self.create(session, **pair_data)

            log_database_operation("INSERT", "pairs", symbol=symbol, pair_id=pair.id)
            logger.info("Pair created from symbol", symbol=symbol, pair_id=pair.id)

            return pair

        except Exception as e:
            logger.error("Error creating pair from symbol", symbol=symbol, error=str(e))
            raise

    async def get_by_symbol(self, session: AsyncSession, symbol: str) -> Optional[Pair]:
        """
        Получить пару по символу.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары

        Returns:
            Optional[Pair]: Торговая пара или None
        """
        try:
            pair = await self.get_by_field(session, "symbol", symbol.upper())

            log_database_operation("SELECT", "pairs", symbol=symbol, found=pair is not None)

            return pair

        except Exception as e:
            logger.error("Error getting pair by symbol", symbol=symbol, error=str(e))
            return None

    async def get_by_assets(
            self,
            session: AsyncSession,
            base_asset: str,
            quote_asset: str
    ) -> Optional[Pair]:
        """
        Получить пару по базовой и котируемой валютам.

        Args:
            session: Сессия базы данных
            base_asset: Базовая валюта
            quote_asset: Котируемая валюта

        Returns:
            Optional[Pair]: Торговая пара или None
        """
        try:
            pairs = await self.filter_by(
                session,
                {
                    "base_asset": base_asset.upper(),
                    "quote_asset": quote_asset.upper()
                },
                limit=1
            )

            pair = pairs[0] if pairs else None

            log_database_operation(
                "SELECT", "pairs",
                base_asset=base_asset,
                quote_asset=quote_asset,
                found=pair is not None
            )

            return pair

        except Exception as e:
            logger.error(
                "Error getting pair by assets",
                base_asset=base_asset,
                quote_asset=quote_asset,
                error=str(e)
            )
            return None

    async def get_active_pairs(self, session: AsyncSession, limit: Optional[int] = None) -> List[Pair]:
        """
        Получить все активные торговые пары.

        Args:
            session: Сессия базы данных
            limit: Максимальное количество пар

        Returns:
            List[Pair]: Список активных пар
        """
        try:
            pairs = await self.filter_by(
                session,
                {
                    "is_active": True,
                    "is_tracked": True
                },
                limit=limit,
                order_by="users_count"  # Сортируем по популярности
            )

            # Переворачиваем список чтобы самые популярные были первыми
            pairs.reverse()

            log_database_operation("SELECT", "pairs", filter="active", count=len(pairs))
            logger.info("Retrieved active pairs", count=len(pairs))

            return pairs

        except Exception as e:
            logger.error("Error getting active pairs", error=str(e))
            return []

    async def get_tracked_pairs(self, session: AsyncSession) -> List[Pair]:
        """
        Получить все отслеживаемые пары.

        Args:
            session: Сессия базы данных

        Returns:
            List[Pair]: Список отслеживаемых пар
        """
        try:
            pairs = await self.filter_by(
                session,
                {"is_tracked": True},
                order_by="users_count"
            )

            pairs.reverse()  # Популярные первыми

            log_database_operation("SELECT", "pairs", filter="tracked", count=len(pairs))
            logger.info("Retrieved tracked pairs", count=len(pairs))

            return pairs

        except Exception as e:
            logger.error("Error getting tracked pairs", error=str(e))
            return []

    async def get_popular_pairs(self, session: AsyncSession, limit: int = 20) -> List[Pair]:
        """
        Получить популярные торговые пары по количеству пользователей.

        Args:
            session: Сессия базы данных
            limit: Максимальное количество пар

        Returns:
            List[Pair]: Список популярных пар
        """
        try:
            stmt = (
                select(Pair)
                .where(
                    and_(
                        Pair.is_active == True,
                        Pair.is_tracked == True,
                        Pair.users_count > 0
                    )
                )
                .order_by(desc(Pair.users_count), desc(Pair.signals_count))
                .limit(limit)
            )

            result = await session.execute(stmt)
            pairs = list(result.scalars().all())

            log_database_operation("SELECT", "pairs", filter="popular", count=len(pairs))
            logger.info("Retrieved popular pairs", count=len(pairs))

            return pairs

        except Exception as e:
            logger.error("Error getting popular pairs", error=str(e))
            return []

    async def search_pairs_by_base_asset(
            self,
            session: AsyncSession,
            base_asset: str,
            limit: int = 10
    ) -> List[Pair]:
        """
        Найти пары по базовой валюте.

        Args:
            session: Сессия базы данных
            base_asset: Базовая валюта для поиска
            limit: Максимальное количество результатов

        Returns:
            List[Pair]: Список найденных пар
        """
        try:
            pairs = await self.search(
                session,
                search_term=base_asset.upper(),
                search_fields=["base_asset"],
                limit=limit
            )

            # Фильтруем только активные пары
            active_pairs = [pair for pair in pairs if pair.is_active]

            log_database_operation(
                "SELECT", "pairs",
                action="search_by_base",
                base_asset=base_asset,
                count=len(active_pairs)
            )

            return active_pairs

        except Exception as e:
            logger.error("Error searching pairs by base asset", base_asset=base_asset, error=str(e))
            return []

    async def increment_users_count(self, session: AsyncSession, pair_id: int) -> bool:
        """
        Увеличить счетчик пользователей пары.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            bool: True если счетчик увеличен
        """
        try:
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                raise RecordNotFoundError("Pair", pair_id)

            pair.increment_users_count()

            await session.commit()

            log_database_operation("UPDATE", "pairs", pair_id=pair_id, action="increment_users")

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error incrementing users count", pair_id=pair_id, error=str(e))
            return False

    async def decrement_users_count(self, session: AsyncSession, pair_id: int) -> bool:
        """
        Уменьшить счетчик пользователей пары.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            bool: True если счетчик уменьшен
        """
        try:
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                raise RecordNotFoundError("Pair", pair_id)

            pair.decrement_users_count()

            await session.commit()

            log_database_operation("UPDATE", "pairs", pair_id=pair_id, action="decrement_users")

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error decrementing users count", pair_id=pair_id, error=str(e))
            return False

    async def increment_signals_count(self, session: AsyncSession, pair_id: int) -> bool:
        """
        Увеличить счетчик сигналов пары.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            bool: True если счетчик увеличен
        """
        try:
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                raise RecordNotFoundError("Pair", pair_id)

            pair.increment_signals_count()

            await session.commit()

            log_database_operation("UPDATE", "pairs", pair_id=pair_id, action="increment_signals")

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error incrementing signals count", pair_id=pair_id, error=str(e))
            return False

    async def activate_pair(self, session: AsyncSession, pair_id: int) -> bool:
        """
        Активировать торговую пару.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            bool: True если пара активирована
        """
        try:
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                raise RecordNotFoundError("Pair", pair_id)

            pair.activate()

            await session.commit()

            log_database_operation("UPDATE", "pairs", pair_id=pair_id, action="activated")
            logger.info("Pair activated", pair_id=pair_id, symbol=pair.symbol)

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error activating pair", pair_id=pair_id, error=str(e))
            return False

    async def deactivate_pair(self, session: AsyncSession, pair_id: int) -> bool:
        """
        Деактивировать торговую пару.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            bool: True если пара деактивирована
        """
        try:
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                raise RecordNotFoundError("Pair", pair_id)

            pair.deactivate()

            await session.commit()

            log_database_operation("UPDATE", "pairs", pair_id=pair_id, action="deactivated")
            logger.info("Pair deactivated", pair_id=pair_id, symbol=pair.symbol)

            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error deactivating pair", pair_id=pair_id, error=str(e))
            return False

    async def get_pair_with_candles_count(
            self,
            session: AsyncSession,
            pair_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Получить пару с информацией о количестве свечей.

        Args:
            session: Сессия базы данных
            pair_id: ID пары

        Returns:
            Optional[Dict[str, Any]]: Информация о паре с количеством свечей
        """
        try:
            # Получаем пару
            pair = await self.get_by_id(session, pair_id)

            if not pair:
                return None

            # Подсчитываем свечи по таймфреймам
            stmt = (
                select(Candle.timeframe, func.count(Candle.id))
                .where(Candle.pair_id == pair_id)
                .group_by(Candle.timeframe)
            )

            result = await session.execute(stmt)
            candles_by_timeframe = dict(result.fetchall())

            total_candles = sum(candles_by_timeframe.values())

            pair_info = {
                "pair": pair.to_dict(include_stats=True),
                "total_candles": total_candles,
                "candles_by_timeframe": candles_by_timeframe,
                "timeframes_with_data": list(candles_by_timeframe.keys())
            }

            log_database_operation("SELECT", "pairs", pair_id=pair_id, action="with_candles_count")

            return pair_info

        except Exception as e:
            logger.error("Error getting pair with candles count", pair_id=pair_id, error=str(e))
            return None

    async def get_pairs_summary(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Получить сводную статистику по парам.

        Args:
            session: Сессия базы данных

        Returns:
            Dict[str, Any]: Сводная статистика
        """
        try:
            # Общее количество пар
            total_count = await self.count(session)

            # Активные пары
            active_count = await self.count(session, {"is_active": True})

            # Отслеживаемые пары
            tracked_count = await self.count(session, {"is_tracked": True})

            # Пары с пользователями
            pairs_with_users = await self.count(session, {"users_count__gt": 0})

            # Топ базовых валют
            stmt = (
                select(Pair.base_asset, func.count(Pair.id))
                .where(Pair.is_active == True)
                .group_by(Pair.base_asset)
                .order_by(desc(func.count(Pair.id)))
                .limit(10)
            )
            result = await session.execute(stmt)
            top_base_assets = dict(result.fetchall())

            # Топ котируемых валют
            stmt = (
                select(Pair.quote_asset, func.count(Pair.id))
                .where(Pair.is_active == True)
                .group_by(Pair.quote_asset)
                .order_by(desc(func.count(Pair.id)))
                .limit(5)
            )
            result = await session.execute(stmt)
            top_quote_assets = dict(result.fetchall())

            summary = {
                "total_pairs": total_count,
                "active_pairs": active_count,
                "tracked_pairs": tracked_count,
                "pairs_with_users": pairs_with_users,
                "inactive_pairs": total_count - active_count,
                "top_base_assets": top_base_assets,
                "top_quote_assets": top_quote_assets
            }

            log_database_operation("SELECT", "pairs", action="summary")
            logger.info("Generated pairs summary", **{k: v for k, v in summary.items() if isinstance(v, int)})

            return summary

        except Exception as e:
            logger.error("Error getting pairs summary", error=str(e))
            return {}

    async def cleanup_unused_pairs(self, session: AsyncSession, dry_run: bool = True) -> Dict[str, Any]:
        """
        Очистка неиспользуемых пар (без пользователей и сигналов).

        Args:
            session: Сессия базы данных
            dry_run: Если True, только показывает что будет удалено

        Returns:
            Dict[str, Any]: Результат очистки
        """
        try:
            # Находим пары без пользователей и сигналов
            stmt = (
                select(Pair)
                .where(
                    and_(
                        Pair.users_count == 0,
                        Pair.signals_count == 0,
                        Pair.is_tracked == False
                    )
                )
            )

            result = await session.execute(stmt)
            unused_pairs = list(result.scalars().all())

            cleanup_info = {
                "pairs_found": len(unused_pairs),
                "pairs_symbols": [pair.symbol for pair in unused_pairs],
                "dry_run": dry_run,
                "deleted_count": 0
            }

            if not dry_run and unused_pairs:
                # Удаляем неиспользуемые пары
                for pair in unused_pairs:
                    await self.delete(session, pair.id)
                    cleanup_info["deleted_count"] += 1

                await session.commit()

                log_database_operation(
                    "DELETE", "pairs",
                    action="cleanup",
                    deleted_count=cleanup_info["deleted_count"]
                )

                logger.info("Unused pairs cleaned up", deleted_count=cleanup_info["deleted_count"])

            return cleanup_info

        except Exception as e:
            if not dry_run:
                await session.rollback()
            logger.error("Error during pairs cleanup", error=str(e))
            return {"error": str(e), "pairs_found": 0, "deleted_count": 0}