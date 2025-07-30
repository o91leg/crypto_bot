"""
Путь: src/services/indicators/rsi_calculator.py
Описание: Сервис для расчета индикатора RSI (Relative Strength Index)
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Optional, Dict, Any
import structlog

from utils.math_helpers import (
    calculate_smoothed_rsi,
    normalize_price_array,
)
from utils.exceptions import (
    InsufficientDataError,
    InvalidIndicatorParameterError,
    DatabaseError,
    RecordNotFoundError,
)
from utils.logger import LoggerMixin
from data.models.candle_model import Candle
from sqlalchemy.ext.asyncio import AsyncSession

# Настройка логирования
logger = structlog.get_logger(__name__)


class RSIResult:
    """Результат расчета RSI."""

    def __init__(
            self,
            value: float,
            period: int,
            avg_gain: Optional[float] = None,
            avg_loss: Optional[float] = None,
            price_changes: Optional[List[float]] = None
    ):
        """
        Инициализация результата RSI.

        Args:
            value: Значение RSI (0-100)
            period: Период расчета
            avg_gain: Среднее значение прибылей
            avg_loss: Среднее значение убытков
            price_changes: Изменения цен для отладки
        """
        self.value = value
        self.period = period
        self.avg_gain = avg_gain
        self.avg_loss = avg_loss
        self.price_changes = price_changes or []

    def is_oversold(self, threshold: float = 30.0) -> bool:
        """Проверить, находится ли RSI в зоне перепроданности."""
        return self.value < threshold

    def is_overbought(self, threshold: float = 70.0) -> bool:
        """Проверить, находится ли RSI в зоне перекупленности."""
        return self.value > threshold

    def get_signal_strength(self) -> str:
        """
        Получить силу сигнала RSI.

        Returns:
            str: Сила сигнала (strong, medium, normal, neutral)
        """
        if self.value <= 20:
            return "strong_oversold"
        elif self.value <= 25:
            return "medium_oversold"
        elif self.value <= 30:
            return "normal_oversold"
        elif self.value >= 80:
            return "strong_overbought"
        elif self.value >= 75:
            return "medium_overbought"
        elif self.value >= 70:
            return "normal_overbought"
        else:
            return "neutral"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать результат в словарь."""
        return {
            "value": round(self.value, 2),
            "period": self.period,
            "signal_strength": self.get_signal_strength(),
            "is_oversold": self.is_oversold(),
            "is_overbought": self.is_overbought(),
            "avg_gain": round(self.avg_gain, 6) if self.avg_gain else None,
            "avg_loss": round(self.avg_loss, 6) if self.avg_loss else None,
        }


class RSICalculator(LoggerMixin):
    """
    Калькулятор индикатора RSI (Relative Strength Index).

    RSI - это осциллятор импульса, который измеряет скорость и изменение
    ценовых движений. RSI колеблется между 0 и 100.

    Традиционно RSI считается:
    - Перекупленным когда выше 70
    - Перепроданным когда ниже 30
    """

    def __init__(self, default_period: int = 14):
        """
        Инициализация калькулятора RSI.

        Args:
            default_period: Период по умолчанию для расчета RSI
        """
        self.default_period = default_period

        # Кеш для хранения промежуточных результатов
        self._rsi_cache: Dict[str, RSIResult] = {}

        self.logger.info("RSI Calculator initialized", default_period=default_period)

    async def calculate_rsi_from_candles(
            self,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            period: int = None,
            limit: int = None
    ) -> Optional[RSIResult]:
        """
        Рассчитать RSI из свечей в базе данных.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм
            period: Период для расчета RSI
            limit: Максимальное количество свечей для загрузки

        Returns:
            Optional[RSIResult]: Результат расчета RSI или None
        """
        if period is None:
            period = self.default_period

        if limit is None:
            limit = period * 3  # Загружаем достаточно данных для стабильного расчета

        try:
            # Получаем последние свечи из базы данных
            candles = await Candle.get_latest_candles(
                session=session,
                pair_id=pair_id,
                timeframe=timeframe,
                limit=limit,
            )
        except (DatabaseError, RecordNotFoundError) as e:
            self.logger.error(
                "Database error while loading candles for RSI",
                pair_id=pair_id,
                timeframe=timeframe,
                error=str(e),
                details=e.details,
            )
            return None
        except Exception as e:
            self.logger.error(
                "Unexpected error loading candles for RSI",
                pair_id=pair_id,
                timeframe=timeframe,
                error=str(e),
            )
            return None

        try:
            if len(candles) < period + 1:
                raise InsufficientDataError("RSI", period + 1, len(candles))

            # Извлекаем цены закрытия
            close_prices = [float(candle.close_price) for candle in candles]

            # Рассчитываем RSI
            return self.calculate_standard_rsi(close_prices, period)

        except InsufficientDataError as e:
            self.logger.warning(
                "Insufficient candle data for RSI",
                pair_id=pair_id,
                timeframe=timeframe,
                required=e.details.get("required"),
                provided=e.details.get("provided"),
            )
            return None
        except InvalidIndicatorParameterError as e:
            self.logger.error(
                "Invalid RSI parameter",
                pair_id=pair_id,
                timeframe=timeframe,
                parameter=e.details.get("parameter"),
                value=e.details.get("value"),
            )
            return None
        except (TypeError, ValueError) as e:
            self.logger.error(
                "Invalid candle values for RSI",
                pair_id=pair_id,
                timeframe=timeframe,
                error=str(e),
            )
            return None
        except Exception as e:
            self.logger.error(
                "Error calculating RSI from candles",
                pair_id=pair_id,
                timeframe=timeframe,
                period=period,
                error=str(e),
            )
            return None

    def calculate_standard_rsi(self, prices: List[float], period: int = None) -> Optional[RSIResult]:
        """
        Рассчитать стандартный RSI по классической формуле Wilder.

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss

        Args:
            prices: Список цен закрытия (от старых к новым)
            period: Период для расчета (по умолчанию 14)

        Returns:
            RSIResult или None при ошибке
        """
        if period is None:
            period = self.default_period

        if len(prices) < period + 1:
            raise InsufficientDataError("RSI", period + 1, len(prices))

        try:
            # Вычисляем изменения цен
            price_changes = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i - 1]
                price_changes.append(change)

            # Разделяем на прибыли и убытки
            gains = [max(change, 0) for change in price_changes]
            losses = [abs(min(change, 0)) for change in price_changes]

            # Первый RSI - простое среднее
            if len(gains) < period:
                raise InsufficientDataError("RSI", period, len(gains))

            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period

            # Избегаем деления на ноль
            if avg_loss == 0:
                rsi_value = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_value = 100 - (100 / (1 + rs))

            # Для последующих значений используем экспоненциальное сглаживание
            for i in range(period, len(gains)):
                avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
                avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

                if avg_loss == 0:
                    rsi_value = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi_value = 100 - (100 / (1 + rs))

            # Проверяем корректность результата
            if not (0 <= rsi_value <= 100):
                self.logger.error("Invalid RSI value calculated", rsi=rsi_value)
                return None

            # Создаем результат
            return RSIResult(
                value=round(rsi_value, 2),
                period=period,
                avg_gain=avg_gain,
                avg_loss=avg_loss,
                price_changes=price_changes[-period:]
            )

        except Exception as e:
            self.logger.error(
                "Error in RSI calculation",
                error=str(e),
                period=period,
                prices_count=len(prices)
            )
            return None

    def calculate_smoothed_rsi(
            self,
            prices: List[float],
            period: int = None,
            previous_avg_gain: Optional[float] = None,
            previous_avg_loss: Optional[float] = None
    ) -> Optional[RSIResult]:
        """
        Рассчитать сглаженный RSI (как в TradingView).

        Args:
            prices: Список цен закрытия
            period: Период для расчета
            previous_avg_gain: Предыдущее среднее значение прибылей
            previous_avg_loss: Предыдущее среднее значение убытков

        Returns:
            Optional[RSIResult]: Результат расчета сглаженного RSI
        """
        if period is None:
            period = self.default_period

        # Валидация
        if len(prices) < 2:
            raise InsufficientDataError("Smoothed RSI", 2, len(prices))

        try:
            # Нормализуем цены
            normalized_prices = normalize_price_array(prices)

            # Рассчитываем изменения цен
            price_changes = []
            for i in range(1, len(normalized_prices)):
                change = normalized_prices[i] - normalized_prices[i - 1]
                price_changes.append(change)

            # Рассчитываем сглаженный RSI
            rsi_value, avg_gain, avg_loss = calculate_smoothed_rsi(
                price_changes=price_changes,
                period=period,
                previous_avg_gain=previous_avg_gain,
                previous_avg_loss=previous_avg_loss
            )

            if rsi_value is None:
                return None

            result = RSIResult(
                value=rsi_value,
                period=period,
                avg_gain=avg_gain,
                avg_loss=avg_loss,
                price_changes=price_changes
            )

            self.logger.debug(
                "Smoothed RSI calculated",
                rsi=round(rsi_value, 2),
                period=period
            )

            return result

        except Exception as e:
            self.logger.error(
                "Error in smoothed RSI calculation",
                period=period,
                error=str(e)
            )
            return None

    def calculate_rsi_multiple_periods(
            self,
            prices: List[float],
            periods: List[int]
    ) -> Dict[int, Optional[RSIResult]]:
        """
        Рассчитать RSI для нескольких периодов одновременно.

        Args:
            prices: Список цен закрытия
            periods: Список периодов для расчета

        Returns:
            Dict[int, Optional[RSIResult]]: Результаты RSI для каждого периода
        """
        results = {}

        for period in periods:
            try:
                result = self.calculate_standard_rsi(prices, period)
                results[period] = result

                self.logger.debug(
                    "Multi-period RSI calculated",
                    period=period,
                    rsi=result.value if result else None
                )

            except Exception as e:
                self.logger.error(
                    "Error calculating RSI for period",
                    period=period,
                    error=str(e)
                )
                results[period] = None

        return results

    async def calculate_rsi_for_multiple_pairs(
            self,
            session: AsyncSession,
            pair_timeframe_configs: List[Dict[str, Any]],
            period: int = None
    ) -> Dict[str, Optional[RSIResult]]:
        """
        Рассчитать RSI для нескольких пар и таймфреймов.

        Args:
            session: Сессия базы данных
            pair_timeframe_configs: Список конфигураций [{pair_id, timeframe, symbol}]
            period: Период для расчета

        Returns:
            Dict[str, Optional[RSIResult]]: Результаты с ключами "symbol_timeframe"
        """
        if period is None:
            period = self.default_period

        results = {}

        for config in pair_timeframe_configs:
            pair_id = config.get("pair_id")
            timeframe = config.get("timeframe")
            symbol = config.get("symbol", f"pair_{pair_id}")

            if not pair_id or not timeframe:
                self.logger.warning("Invalid config for multi-pair RSI", config=config)
                continue

            key = f"{symbol}_{timeframe}"

            try:
                result = await self.calculate_rsi_from_candles(
                    session=session,
                    pair_id=pair_id,
                    timeframe=timeframe,
                    period=period
                )

                results[key] = result

                self.logger.debug(
                    "Multi-pair RSI calculated",
                    key=key,
                    rsi=result.value if result else None
                )

            except Exception as e:
                self.logger.error(
                    "Error calculating RSI for pair",
                    key=key,
                    error=str(e)
                )
                results[key] = None

        return results

    def get_rsi_signals(
            self,
            current_rsi: RSIResult,
            previous_rsi: Optional[RSIResult] = None
    ) -> List[Dict[str, Any]]:
        """
        Определить сигналы на основе значений RSI.

        Args:
            current_rsi: Текущий RSI
            previous_rsi: Предыдущий RSI (для определения пересечений)

        Returns:
            List[Dict[str, Any]]: Список сигналов
        """
        signals = []

        if not current_rsi:
            return signals

        current_value = current_rsi.value
        signal_strength = current_rsi.get_signal_strength()

        # Сигналы перепроданности
        if signal_strength == "strong_oversold":
            signals.append({
                "type": "rsi_oversold_strong",
                "value": current_value,
                "threshold": 20,
                "message": "Сильная перепроданность",
                "priority": "high"
            })
        elif signal_strength == "medium_oversold":
            signals.append({
                "type": "rsi_oversold_medium",
                "value": current_value,
                "threshold": 25,
                "message": "Средняя перепроданность",
                "priority": "medium"
            })
        elif signal_strength == "normal_oversold":
            signals.append({
                "type": "rsi_oversold_normal",
                "value": current_value,
                "threshold": 30,
                "message": "Перепроданность",
                "priority": "low"
            })

        # Сигналы перекупленности
        elif signal_strength == "strong_overbought":
            signals.append({
                "type": "rsi_overbought_strong",
                "value": current_value,
                "threshold": 80,
                "message": "Сильная перекупленность",
                "priority": "high"
            })
        elif signal_strength == "medium_overbought":
            signals.append({
                "type": "rsi_overbought_medium",
                "value": current_value,
                "threshold": 75,
                "message": "Средняя перекупленность",
                "priority": "medium"
            })
        elif signal_strength == "normal_overbought":
            signals.append({
                "type": "rsi_overbought_normal",
                "value": current_value,
                "threshold": 70,
                "message": "Перекупленность",
                "priority": "low"
            })

        # Сигналы пересечения уровней (если есть предыдущий RSI)
        if previous_rsi:
            cross_signals = self._detect_rsi_crossovers(previous_rsi, current_rsi)
            signals.extend(cross_signals)

        return signals

    def _detect_rsi_crossovers(
            self,
            previous_rsi: RSIResult,
            current_rsi: RSIResult
    ) -> List[Dict[str, Any]]:
        """
        Определить пересечения ключевых уровней RSI.

        Args:
            previous_rsi: Предыдущее значение RSI
            current_rsi: Текущее значение RSI

        Returns:
            List[Dict[str, Any]]: Список сигналов пересечения
        """
        signals = []
        prev_val = previous_rsi.value
        curr_val = current_rsi.value

        # Пересечение уровня 30 снизу вверх (выход из перепроданности)
        if prev_val <= 30 and curr_val > 30:
            signals.append({
                "type": "rsi_exit_oversold",
                "value": curr_val,
                "threshold": 30,
                "message": "Выход из зоны перепроданности",
                "priority": "medium",
                "direction": "up"
            })

        # Пересечение уровня 70 сверху вниз (выход из перекупленности)
        elif prev_val >= 70 and curr_val < 70:
            signals.append({
                "type": "rsi_exit_overbought",
                "value": curr_val,
                "threshold": 70,
                "message": "Выход из зоны перекупленности",
                "priority": "medium",
                "direction": "down"
            })

        # Пересечение средней линии 50
        elif prev_val < 50 and curr_val >= 50:
            signals.append({
                "type": "rsi_cross_above_50",
                "value": curr_val,
                "threshold": 50,
                "message": "RSI пересек 50 вверх",
                "priority": "low",
                "direction": "up"
            })
        elif prev_val > 50 and curr_val <= 50:
            signals.append({
                "type": "rsi_cross_below_50",
                "value": curr_val,
                "threshold": 50,
                "message": "RSI пересек 50 вниз",
                "priority": "low",
                "direction": "down"
            })

        return signals

    def calculate_rsi_divergence(
            self,
            prices: List[float],
            rsi_values: List[float],
            lookback_periods: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Определить дивергенцию между ценой и RSI.

        Args:
            prices: Список цен
            rsi_values: Список значений RSI
            lookback_periods: Количество периодов для анализа

        Returns:
            Optional[Dict[str, Any]]: Информация о дивергенции или None
        """
        if len(prices) < lookback_periods or len(rsi_values) < lookback_periods:
            return None

        try:
            # Анализируем последние периоды
            recent_prices = prices[-lookback_periods:]
            recent_rsi = rsi_values[-lookback_periods:]

            # Находим максимумы и минимумы
            price_max_idx = recent_prices.index(max(recent_prices))
            price_min_idx = recent_prices.index(min(recent_prices))
            rsi_max_idx = recent_rsi.index(max(recent_rsi))
            rsi_min_idx = recent_rsi.index(min(recent_rsi))

            divergence_type = None

            # Медвежья дивергенция: цена растет, RSI падает
            if (price_max_idx > len(recent_prices) // 2 and
                    rsi_max_idx < len(recent_rsi) // 2):
                divergence_type = "bearish"

            # Бычья дивергенция: цена падает, RSI растет
            elif (price_min_idx > len(recent_prices) // 2 and
                  rsi_min_idx < len(recent_rsi) // 2):
                divergence_type = "bullish"

            if divergence_type:
                return {
                    "type": divergence_type,
                    "strength": "medium",
                    "price_extreme": recent_prices[price_max_idx if divergence_type == "bearish" else price_min_idx],
                    "rsi_extreme": recent_rsi[rsi_max_idx if divergence_type == "bearish" else rsi_min_idx],
                    "lookback_periods": lookback_periods
                }

            return None

        except Exception as e:
            self.logger.error("Error calculating RSI divergence", error=str(e))
            return None

    def get_rsi_interpretation(self, rsi_result: RSIResult) -> Dict[str, Any]:
        """
        Получить интерпретацию значения RSI.

        Args:
            rsi_result: Результат расчета RSI

        Returns:
            Dict[str, Any]: Интерпретация с цветом, описанием и рекомендацией
        """
        rsi_value = rsi_result.value
        signal_strength = rsi_result.get_signal_strength()

        # Определяем цвет эмодзи и интерпретацию
        if signal_strength == "strong_oversold":
            color = "🔴"
            interpretation = "Крайне перепродано"
            recommended_action = "Сильный сигнал на покупку"
            zone = "oversold"
        elif signal_strength == "medium_oversold":
            color = "🟠"
            interpretation = "Перепродано"
            recommended_action = "Возможный сигнал на покупку"
            zone = "oversold"
        elif signal_strength == "normal_oversold":
            color = "🟡"
            interpretation = "Слабо перепродано"
            recommended_action = "Следить за разворотом"
            zone = "oversold"
        elif signal_strength == "strong_overbought":
            color = "🔴"
            interpretation = "Крайне перекуплено"
            recommended_action = "Сильный сигнал на продажу"
            zone = "overbought"
        elif signal_strength == "medium_overbought":
            color = "🟠"
            interpretation = "Перекуплено"
            recommended_action = "Возможный сигнал на продажу"
            zone = "overbought"
        elif signal_strength == "normal_overbought":
            color = "🟡"
            interpretation = "Слабо перекуплено"
            recommended_action = "Следить за разворотом"
            zone = "overbought"
        else:  # neutral
            color = "🟢"
            interpretation = "Нейтрально"
            recommended_action = "Ожидание сигнала"
            zone = "neutral"

        return {
            "color": color,
            "interpretation": interpretation,
            "recommended_action": recommended_action,
            "zone": zone,
            "strength": signal_strength,
            "value": round(rsi_value, 1),
            "is_extreme": signal_strength in ["strong_oversold", "strong_overbought"]
        }

    def get_rsi_trend_analysis(
            self,
            current_rsi: RSIResult,
            previous_rsi_values: List[float],
            lookback_periods: int = 5
    ) -> Dict[str, Any]:
        """
        Проанализировать тренд RSI.

        Args:
            current_rsi: Текущий результат RSI
            previous_rsi_values: Предыдущие значения RSI
            lookback_periods: Количество периодов для анализа

        Returns:
            Dict[str, Any]: Анализ тренда RSI
        """
        if len(previous_rsi_values) < lookback_periods:
            return {
                "trend": "unknown",
                "trend_strength": "weak",
                "direction": "sideways",
                "description": "Недостаточно данных для анализа тренда"
            }

        recent_values = previous_rsi_values[-lookback_periods:] + [current_rsi.value]

        # Анализируем направление
        increases = 0
        decreases = 0

        for i in range(1, len(recent_values)):
            if recent_values[i] > recent_values[i - 1]:
                increases += 1
            elif recent_values[i] < recent_values[i - 1]:
                decreases += 1

        # Определяем тренд
        if increases > decreases * 1.5:
            trend = "bullish"
            direction = "вверх"
        elif decreases > increases * 1.5:
            trend = "bearish"
            direction = "вниз"
        else:
            trend = "sideways"
            direction = "боком"

        # Определяем силу тренда
        total_changes = increases + decreases
        if total_changes == 0:
            trend_strength = "weak"
        else:
            dominant_ratio = max(increases, decreases) / total_changes
            if dominant_ratio >= 0.8:
                trend_strength = "strong"
            elif dominant_ratio >= 0.6:
                trend_strength = "medium"
            else:
                trend_strength = "weak"

        # Создаем описание
        if trend == "bullish":
            description = f"RSI растёт ({increases}/{lookback_periods} периодов)"
        elif trend == "bearish":
            description = f"RSI падает ({decreases}/{lookback_periods} периодов)"
        else:
            description = f"RSI движется боком"

        return {
            "trend": trend,
            "trend_strength": trend_strength,
            "direction": direction,
            "description": description,
            "increases": increases,
            "decreases": decreases,
            "recent_values": recent_values
        }

    def detect_rsi_divergence(
            self,
            price_highs: List[float],
            price_lows: List[float],
            rsi_values: List[float],
            min_periods: int = 3
    ) -> Dict[str, Any]:
        """
        Обнаружить дивергенцию между ценой и RSI.

        Args:
            price_highs: Максимумы цен
            price_lows: Минимумы цен
            rsi_values: Значения RSI
            min_periods: Минимальное количество периодов для анализа

        Returns:
            Dict[str, Any]: Информация о дивергенции
        """
        if len(rsi_values) < min_periods or len(price_highs) < 2 or len(price_lows) < 2:
            return {
                "has_divergence": False,
                "type": None,
                "description": "Недостаточно данных для анализа дивергенции"
            }

        # Проверяем бычью дивергенцию (цена падает, RSI растёт)
        if len(price_lows) >= 2 and len(rsi_values) >= 2:
            recent_price = price_lows[-1]
            previous_price = price_lows[-2]
            recent_rsi = rsi_values[-1]
            previous_rsi = rsi_values[-2]

            if recent_price < previous_price and recent_rsi > previous_rsi:
                return {
                    "has_divergence": True,
                    "type": "bullish",
                    "description": "Бычья дивергенция: цена обновляет минимумы, RSI растёт",
                    "strength": "medium" if abs(recent_rsi - previous_rsi) > 5 else "weak"
                }

        # Проверяем медвежью дивергенцию (цена растёт, RSI падает)
        if len(price_highs) >= 2 and len(rsi_values) >= 2:
            recent_price = price_highs[-1]
            previous_price = price_highs[-2]
            recent_rsi = rsi_values[-1]
            previous_rsi = rsi_values[-2]

            if recent_price > previous_price and recent_rsi < previous_rsi:
                return {
                    "has_divergence": True,
                    "type": "bearish",
                    "description": "Медвежья дивергенция: цена обновляет максимумы, RSI падает",
                    "strength": "medium" if abs(recent_rsi - previous_rsi) > 5 else "weak"
                }

        return {
            "has_divergence": False,
            "type": None,
            "description": "Дивергенция не обнаружена"
        }

    def clear_cache(self) -> None:
        """Очистить кеш RSI расчетов."""
        self._rsi_cache.clear()
        self.logger.debug("RSI cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кеша.

        Returns:
            Dict[str, Any]: Статистика кеша
        """
        return {
            "cached_calculations": len(self._rsi_cache),
            "cache_keys": list(self._rsi_cache.keys())
        }

    def calculate_williams_r(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Рассчитать Williams %R осциллятор.

        Args:
            prices: Список цен (должен содержать high, low, close)
            period: Период для расчета

        Returns:
            Optional[float]: Значение Williams %R
        """
        if len(prices) < period:
            return None

        # Для упрощения используем цены как close, high и low одновременно
        recent_prices = prices[-period:]

        highest_high = max(recent_prices)
        lowest_low = min(recent_prices)
        current_close = prices[-1]

        if highest_high == lowest_low:
            return -50.0  # Средняя позиция когда нет волатильности

        williams_r = ((highest_high - current_close) / (highest_high - lowest_low)) * -100

        return williams_r

    def calculate_stochastic_oscillator(
            highs: List[float],
            lows: List[float],
            closes: List[float],
            period: int = 14
    ) -> Optional[Dict[str, float]]:
        """
        Рассчитать стохастический осциллятор.

        Args:
            highs: Список максимальных цен
            lows: Список минимальных цен
            closes: Список цен закрытия
            period: Период для расчета

        Returns:
            Optional[Dict[str, float]]: %K и %D значения или None
        """
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return None

        if not (len(highs) == len(lows) == len(closes)):
            return None

        # Рассчитываем %K
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        current_close = closes[-1]

        highest_high = max(recent_highs)
        lowest_low = min(recent_lows)

        if highest_high == lowest_low:
            k_percent = 50.0
        else:
            k_percent = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100

        # Для %D нужно больше данных, упрощаем
        d_percent = k_percent  # В реальной реализации это SMA от %K

        return {
            "k_percent": k_percent,
            "d_percent": d_percent
        }