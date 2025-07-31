"""Реалтайм калькулятор индикаторов.

Предоставляет методы для получения свежих значений индикаторов
на основе актуальных данных из базы или внешних источников.
"""

from __future__ import annotations

from typing import Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from services.indicators.rsi_calculator import RSICalculator


logger = structlog.get_logger(__name__)


class RealtimeCalculator:
    """Калькулятор для получения свежих значений индикаторов."""

    def __init__(self) -> None:
        self._rsi = RSICalculator()

    async def get_fresh_rsi(
        self, session: AsyncSession, pair_id: int, timeframe: str
    ) -> Optional[Dict[str, object]]:
        """Получить актуальное значение RSI для пары."""

        rsi_result = await self._rsi.calculate_rsi_from_candles(
            session=session, pair_id=pair_id, timeframe=timeframe
        )
        if not rsi_result:
            return None

        interpretation = self._rsi.get_rsi_interpretation(rsi_result)
        return {
            "value": rsi_result.value,
            "signal_strength": rsi_result.get_signal_strength(),
            "interpretation": interpretation,
        }
