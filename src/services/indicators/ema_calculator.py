"""
Путь: src/services/indicators/ema_calculator.py
Описание: Сервис для расчета индикатора EMA (Exponential Moving Average)
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
import structlog

from utils.math_helpers import (
    calculate_exponential_moving_average,
    calculate_simple_moving_average,
    normalize_price_array,
    is_valid_price
)
from utils.exceptions import InsufficientDataError, InvalidIndicatorParameterError
from utils.logger import LoggerMixin
from data.models.candle_model import Candle
from config.bot_config import get_bot_config
from sqlalchemy.ext.asyncio import AsyncSession

# Настройка логирования
logger = structlog.get_logger(__name__)


class EMAResult:
    """Результат расчета EMA."""

    def __init__(
            self,
            value: float,
            period: int,
            multiplier: float,
            previous_ema: Optional[float] = None,
            current_price: Optional[float] = None
    ):
        """
        Инициализация результата EMA.

        Args:
            value: Значение EMA
            period: Период расчета
            multiplier: Множитель сглаживания
            previous_ema: Предыдущее значение EMA
            current_price: Текущая цена
        """
        self.value = value
        self.period = period
        self.multiplier = multiplier
        self.previous_ema = previous_ema
        self.current_price = current_price

    def is_price_above_ema(self, price: float) -> bool:
        """Проверить, находится ли цена выше EMA."""
        return price > self.value

    def is_price_below_ema(self, price: float) -> bool:
        """Проверить, находится ли цена ниже EMA."""
        return price < self.value

    def get_distance_percent(self, price: float) -> float:
        """
        Получить процентное расстояние от цены до EMA.

        Returns:
            float: Процентное расстояние (положительное если цена выше EMA)
        """
        if self.value == 0:
            return 0.0
        return ((price - self.value) / self.value) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать результат в словарь."""
        return {
            "value": round(self.value, 8),
            "period": self.period,
            "multiplier": round(self.multiplier, 6),
            "previous_ema": round(self.previous_ema, 8) if self.previous_ema else None,
            "current_price": round(self.current_price, 8) if self.current_price else None,
        }


class EMASet:
    """Набор EMA для разных периодов."""

    def __init__(self, emas: Dict[int, EMAResult]):
        """
        Инициализация набора EMA.

        Args:
            emas: Словарь EMA результатов {period: EMAResult}
        """
        self.emas = emas
        self.periods = sorted(emas.keys())

    def get_ema(self, period: int) -> Optional[EMAResult]:
        """Получить EMA для конкретного периода."""
        return self.emas.get(period)

    def get_trend_direction(self) -> str:
        """
        Определить направление тренда по расположению EMA.

        Returns:
            str: Направление тренда (bullish, bearish, sideways)
        """
        if len(self.periods) < 2:
            return "sideways"

        # Проверяем упорядоченность EMA (быстрые выше медленных = бычий тренд)
        values = [self.emas[period].value for period in self.periods]

        # Бычий тренд: короткие EMA выше длинных
        if all(values[i] >= values[i + 1] for i in range(len(values) - 1)):
            return "bullish"
        # Медвежий тренд: короткие EMA ниже длинных
        elif all(values[i] <= values[i + 1] for i in range(len(values) - 1)):
            return "bearish"
        else:
            return "sideways"

    def detect_crossovers(self, previous_ema_set: Optional["EMASet"] = None) -> List[Dict[str, Any]]:
        """
        Определить пересечения EMA.

        Args:
            previous_ema_set: Предыдущий набор EMA для сравнения

        Returns:
            List[Dict[str, Any]]: Список пересечений
        """
        crossovers = []

        if not previous_ema_set or len(self.periods) < 2:
            return crossovers

        # Проверяем пересечения между соседними периодами
        for i in range(len(self.periods) - 1):
            fast_period = self.periods[i]
            slow_period = self.periods[i + 1]

            current_fast = self.emas[fast_period]
            current_slow = self.emas[slow_period]
            previous_fast = previous_ema_set.get_ema(fast_period)
            previous_slow = previous_ema_set.get_ema(slow_period)

            if not previous_fast or not previous_slow:
                continue

            # Золотой крест: быстрая EMA пересекает медленную вверх
            if (previous_fast.value <= previous_slow.value and
                    current_fast.value > current_slow.value):
                crossovers.append({
                    "type": "golden_cross",
                    "fast_period": fast_period,
                    "slow_period": slow_period,
                    "direction": "up",
                    "fast_value": current_fast.value,
                    "slow_value": current_slow.value
                })

            # Мертвый крест: быстрая EMA пересекает медленную вниз
            elif (previous_fast.value >= previous_slow.value and
                  current_fast.value < current_slow.value):
                crossovers.append({
                    "type": "death_cross",
                    "fast_period": fast_period,
                    "slow_period": slow_period,
                    "direction": "down",
                    "fast_value": current_fast.value,
                    "slow_value": current_slow.value
                })

        return crossovers

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать набор в словарь."""
        return {
            "emas": {period: ema.to_dict() for period, ema in self.emas.items()},
            "periods": self.periods,
            "trend_direction": self.get_trend_direction()
        }


class EMACalculator(LoggerMixin):
    """
    Калькулятор индикатора EMA (Exponential Moving Average).

    EMA - экспоненциальное скользящее среднее, которое придает больший вес
    более свежим ценам. EMA реагирует быстрее на изменения цены чем SMA.

    Формула: EMA = (Price * Multiplier) + (Previous EMA * (1 - Multiplier))
    где Multiplier = 2 / (Period + 1)
    """

    def __init__(self):
        """Инициализация калькулятора EMA."""
        self.config = get_bot_config()
        self.default_periods = self.config.ema_periods

        # Кеш для хранения промежуточных результатов
        self._ema_cache: Dict[str, EMAResult] = {}

        self.logger.info("EMA Calculator initialized", default_periods=self.default_periods)

    async def calculate_ema_from_candles(
            self,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            period: int,
            price_type: str = "close",
            limit: int = None
    ) -> Optional[EMAResult]:
        """
        Рассчитать EMA из свечей в базе данных.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм
            period: Период для расчета EMA
            price_type: Тип цены (close, open, high, low, typical)
            limit: Максимальное количество свечей для загрузки

        Returns:
            Optional[EMAResult]: Результат расчета EMA или None
        """
        if limit is None:
            limit = period * 3  # Загружаем достаточно данных для стабильного расчета

        try:
            # Получаем последние свечи
            candles = await Candle.get_latest_candles(
                session=session,
                pair_id=pair_id,
                timeframe=timeframe,
                limit=limit
            )

            if len(candles) < period:
                raise InsufficientDataError("EMA", period, len(candles))

            # Извлекаем цены
            prices = self._extract_prices_from_candles(candles, price_type)

            # Рассчитываем EMA
            return self.calculate_ema(prices, period)

        except Exception as e:
            self.logger.error(
                "Error calculating EMA from candles",
                pair_id=pair_id,
                timeframe=timeframe,
                period=period,
                error=str(e)
            )
            return None

    def calculate_ema(
            self,
            prices: List[float],
            period: int,
            previous_ema: Optional[float] = None
    ) -> Optional[EMAResult]:
        """
        Рассчитать EMA для списка цен.

        Args:
            prices: Список цен
            period: Период для расчета
            previous_ema: Предыдущее значение EMA

        Returns:
            Optional[EMAResult]: Результат расчета EMA
        """
        # Валидация параметров
        if period < 1:
            raise InvalidIndicatorParameterError("EMA", "period", period, "Period must be >= 1")

        if period > 1000:
            raise InvalidIndicatorParameterError("EMA", "period", period, "Period must be <= 1000")

        # Нормализуем цены
        normalized_prices = normalize_price_array(prices)

        if len(normalized_prices) < period and previous_ema is None:
            raise InsufficientDataError("EMA", period, len(normalized_prices))

        try:
            # Рассчитываем EMA
            ema_value = calculate_exponential_moving_average(
                values=normalized_prices,
                period=period,
                previous_ema=previous_ema
            )

            if ema_value is None:
                self.logger.warning("EMA calculation returned None", period=period, prices_count=len(prices))
                return None

            # Рассчитываем множитель сглаживания
            multiplier = 2.0 / (period + 1)
            current_price = normalized_prices[-1] if normalized_prices else None

            result = EMAResult(
                value=ema_value,
                period=period,
                multiplier=multiplier,
                previous_ema=previous_ema,
                current_price=current_price
            )

            self.logger.debug(
                "EMA calculated",
                ema=round(ema_value, 6),
                period=period,
                current_price=current_price
            )

            return result

        except Exception as e:
            self.logger.error(
                "Error in EMA calculation",
                period=period,
                prices_count=len(prices),
                error=str(e)
            )
            return None

    async def calculate_ema_set_from_candles(
            self,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            periods: List[int] = None,
            price_type: str = "close"
    ) -> Optional[EMASet]:
        """
        Рассчитать набор EMA для разных периодов из свечей.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм
            periods: Список периодов (по умолчанию используются стандартные)
            price_type: Тип цены

        Returns:
            Optional[EMASet]: Набор EMA результатов
        """
        if periods is None:
            periods = self.default_periods

        try:
            # Загружаем достаточно данных для самого длинного периода
            max_period = max(periods)
            limit = max_period * 3

            candles = await Candle.get_latest_candles(
                session=session,
                pair_id=pair_id,
                timeframe=timeframe,
                limit=limit
            )

            if len(candles) < max_period:
                raise InsufficientDataError("EMA Set", max_period, len(candles))

            # Извлекаем цены
            prices = self._extract_prices_from_candles(candles, price_type)

            # Рассчитываем EMA для всех периодов
            return self.calculate_ema_set(prices, periods)

        except Exception as e:
            self.logger.error(
                "Error calculating EMA set from candles",
                pair_id=pair_id,
                timeframe=timeframe,
                periods=periods,
                error=str(e)
            )
            return None

    def calculate_ema_set(
            self,
            prices: List[float],
            periods: List[int] = None
    ) -> Optional[EMASet]:
        """
        Рассчитать набор EMA для разных периодов.

        Args:
            prices: Список цен
            periods: Список периодов

        Returns:
            Optional[EMASet]: Набор EMA результатов
        """
        if periods is None:
            periods = self.default_periods

        emas = {}

        for period in periods:
            try:
                ema_result = self.calculate_ema(prices, period)
                if ema_result:
                    emas[period] = ema_result

                self.logger.debug(
                    "EMA set calculation",
                    period=period,
                    ema=ema_result.value if ema_result else None
                )

            except Exception as e:
                self.logger.error(
                    "Error calculating EMA for period",
                    period=period,
                    error=str(e)
                )

        if not emas:
            return None

        return EMASet(emas)

    def detect_price_ema_signals(
            self,
            current_price: float,
            current_ema: EMAResult,
            previous_price: Optional[float] = None,
            previous_ema: Optional[EMAResult] = None
    ) -> List[Dict[str, Any]]:
        """
        Определить сигналы взаимодействия цены с EMA.

        Args:
            current_price: Текущая цена
            current_ema: Текущий EMA
            previous_price: Предыдущая цена
            previous_ema: Предыдущий EMA

        Returns:
            List[Dict[str, Any]]: Список сигналов
        """
        signals = []

        # Сигналы пересечения цены с EMA
        if previous_price is not None and previous_ema is not None:
            # Цена пересекает EMA вверх
            if (previous_price <= previous_ema.value and
                    current_price > current_ema.value):
                signals.append({
                    "type": "price_cross_ema_up",
                    "price": current_price,
                    "ema_value": current_ema.value,
                    "ema_period": current_ema.period,
                    "direction": "up",
                    "message": f"Цена пересекла EMA{current_ema.period} вверх"
                })

            # Цена пересекает EMA вниз
            elif (previous_price >= previous_ema.value and
                  current_price < current_ema.value):
                signals.append({
                    "type": "price_cross_ema_down",
                    "price": current_price,
                    "ema_value": current_ema.value,
                    "ema_period": current_ema.period,
                    "direction": "down",
                    "message": f"Цена пересекла EMA{current_ema.period} вниз"
                })

        # Сигналы расстояния от EMA
        distance_percent = current_ema.get_distance_percent(current_price)

        if abs(distance_percent) > 10:  # Цена далеко от EMA
            signals.append({
                "type": "price_far_from_ema",
                "distance_percent": distance_percent,
                "ema_period": current_ema.period,
                "message": f"Цена на {abs(distance_percent):.1f}% {'выше' if distance_percent > 0 else 'ниже'} EMA{current_ema.period}"
            })

        return signals

    def analyze_ema_trend_strength(self, ema_set: EMASet) -> Dict[str, Any]:
        """
        Проанализировать силу тренда по EMA.

        Args:
            ema_set: Набор EMA

        Returns:
            Dict[str, Any]: Анализ силы тренда
        """
        if len(ema_set.periods) < 2:
            return {"error": "Insufficient EMA periods for trend analysis"}

        trend_direction = ema_set.get_trend_direction()

        # Рассчитываем расстояния между EMA
        ema_distances = []
        for i in range(len(ema_set.periods) - 1):
            fast_period = ema_set.periods[i]
            slow_period = ema_set.periods[i + 1]

            fast_ema = ema_set.get_ema(fast_period)
            slow_ema = ema_set.get_ema(slow_period)

            if fast_ema and slow_ema:
                distance = abs(fast_ema.value - slow_ema.value)
                relative_distance = (distance / slow_ema.value) * 100
                ema_distances.append(relative_distance)

        # Определяем силу тренда
        if not ema_distances:
            strength = "unknown"
        elif max(ema_distances) > 5:
            strength = "strong"
        elif max(ema_distances) > 2:
            strength = "medium"
        else:
            strength = "weak"

        return {
            "trend_direction": trend_direction,
            "trend_strength": strength,
            "ema_distances": ema_distances,
            "max_distance_percent": max(ema_distances) if ema_distances else 0,
            "periods_analyzed": ema_set.periods
        }

    def calculate_ema_support_resistance(
            self,
            ema_set: EMASet,
            current_price: float
    ) -> Dict[str, Any]:
        """
        Определить уровни поддержки/сопротивления на основе EMA.

        Args:
            ema_set: Набор EMA
            current_price: Текущая цена

        Returns:
            Dict[str, Any]: Уровни поддержки и сопротивления
        """
        support_levels = []
        resistance_levels = []

        for period in ema_set.periods:
            ema = ema_set.get_ema(period)
            if not ema:
                continue

            if ema.value < current_price:
                support_levels.append({
                    "level": ema.value,
                    "period": period,
                    "distance_percent": ((current_price - ema.value) / current_price) * 100
                })
            else:
                resistance_levels.append({
                    "level": ema.value,
                    "period": period,
                    "distance_percent": ((ema.value - current_price) / current_price) * 100
                })

        # Сортируем по близости к текущей цене
        support_levels.sort(key=lambda x: x["distance_percent"])
        resistance_levels.sort(key=lambda x: x["distance_percent"])

        return {
            "current_price": current_price,
            "support_levels": support_levels[:3],  # Ближайшие 3 уровня
            "resistance_levels": resistance_levels[:3],
            "nearest_support": support_levels[0] if support_levels else None,
            "nearest_resistance": resistance_levels[0] if resistance_levels else None
        }

    def _extract_prices_from_candles(
            self,
            candles: List[Candle],
            price_type: str
    ) -> List[float]:
        """
        Извлечь цены из свечей по типу.

        Args:
            candles: Список свечей
            price_type: Тип цены (close, open, high, low, typical)

        Returns:
            List[float]: Список цен
        """
        prices = []

        for candle in candles:
            if price_type == "close":
                price = float(candle.close_price)
            elif price_type == "open":
                price = float(candle.open_price)
            elif price_type == "high":
                price = float(candle.high_price)
            elif price_type == "low":
                price = float(candle.low_price)
            elif price_type == "typical":
                price = float(candle.typical_price)
            else:
                price = float(candle.close_price)  # По умолчанию используем close

            prices.append(price)

        return prices

    def clear_cache(self) -> None:
        """Очистить кеш EMA расчетов."""
        self._ema_cache.clear()
        self.logger.debug("EMA cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кеша.

        Returns:
            Dict[str, Any]: Статистика кеша
        """
        return {
            "cached_calculations": len(self._ema_cache),
            "cache_keys": list(self._ema_cache.keys())
        }