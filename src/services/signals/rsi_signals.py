"""
Путь: src/services/signals/rsi_signals.py
Описание: Сервис для генерации RSI сигналов
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from services.cache.indicator_cache import indicator_cache
from services.notifications.notification_queue import notification_queue
from data.models.signal_history_model import SignalHistory
from data.models.user_pair_model import UserPair
from utils.logger import get_logger
from utils.constants import RSI_PERIODS, SIGNAL_REPEAT_INTERVALS
from utils.exceptions import SignalError


class RSISignalGenerator:
    """
    Генератор RSI сигналов.

    Включает:
    - Определение зон RSI
    - Проверку условий сигналов
    - Предотвращение спама
    - Генерацию уведомлений
    """

    def __init__(self):
        """Инициализация генератора RSI сигналов."""
        self.logger = get_logger(__name__)

        # Зоны RSI для сигналов
        self.rsi_zones = {
            "oversold_strong": 20,  # Сильная перепроданность
            "oversold_medium": 25,  # Средняя перепроданность
            "oversold_normal": 30,  # Обычная перепроданность
            "overbought_normal": 70,  # Обычная перекупленность
            "overbought_medium": 75,  # Средняя перекупленность
            "overbought_strong": 80  # Сильная перекупленность
        }

        # Минимальные интервалы между сигналами (в секундах)
        self.signal_intervals = {
            "oversold_strong": 120,  # 2 минуты
            "oversold_medium": 150,  # 2.5 минуты
            "oversold_normal": 180,  # 3 минуты
            "overbought_normal": 180,  # 3 минуты
            "overbought_medium": 150,  # 2.5 минуты
            "overbought_strong": 120  # 2 минуты
        }

    async def check_rsi_signals(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            current_rsi: float,
            current_price: float,
            volume_change_percent: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Проверить условия RSI сигналов.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            current_rsi: Текущее значение RSI
            current_price: Текущая цена
            volume_change_percent: Изменение объема в %

        Returns:
            List[Dict]: Список сигналов для отправки
        """
        try:
            # Определяем тип сигнала
            signal_type = self._determine_rsi_signal_type(current_rsi)

            if not signal_type:
                # RSI в нормальной зоне, сигналов нет
                return []

            # Получаем пользователей, отслеживающих эту пару на данном таймфрейме
            users_to_notify = await self._get_users_for_notification(
                session, symbol, timeframe
            )

            if not users_to_notify:
                return []

            # Проверяем каждого пользователя на спам-фильтр
            signals_to_send = []

            for user_id in users_to_notify:
                # Проверяем можно ли отправить сигнал этому пользователю
                can_send = await self._can_send_signal(
                    session, user_id, symbol, timeframe, signal_type
                )

                if can_send:
                    signal_data = {
                        "user_id": user_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "signal_type": signal_type,
                        "rsi_value": current_rsi,
                        "price": current_price,
                        "volume_change_percent": volume_change_percent,
                        "timestamp": datetime.now()
                    }

                    signals_to_send.append(signal_data)

            # Сохраняем историю сигналов
            if signals_to_send:
                await self._save_signal_history(session, signals_to_send)

            self.logger.info(
                "RSI signals generated",
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                rsi_value=current_rsi,
                users_count=len(signals_to_send)
            )

            return signals_to_send

        except Exception as e:
            self.logger.error(
                "Error checking RSI signals",
                symbol=symbol,
                timeframe=timeframe,
                current_rsi=current_rsi,
                error=str(e)
            )
            return []

    async def generate_notifications(
            self,
            signals: List[Dict[str, Any]]
    ) -> int:
        """
        Сгенерировать уведомления для RSI сигналов.

        Args:
            signals: Список сигналов

        Returns:
            int: Количество добавленных уведомлений
        """
        if not signals:
            return 0

        notifications_added = 0

        try:
            for signal in signals:
                # Определяем приоритет на основе силы сигнала
                priority = self._get_signal_priority(signal["signal_type"])

                # Подготавливаем данные для уведомления
                notification_data = {
                    "signal_type": signal["signal_type"],
                    "rsi_value": signal["rsi_value"],
                    "price": signal["price"],
                    "volume_change_percent": signal.get("volume_change_percent"),
                    "rsi_signal_type": signal["signal_type"]
                }

                # Добавляем в очередь уведомлений
                task_id = await notification_queue.add_signal_notification(
                    user_id=signal["user_id"],
                    symbol=signal["symbol"],
                    timeframe=signal["timeframe"],
                    signal_data=notification_data,
                    priority=priority
                )

                if task_id:
                    notifications_added += 1

                    self.logger.debug(
                        "RSI notification queued",
                        task_id=task_id,
                        user_id=signal["user_id"],
                        symbol=signal["symbol"],
                        timeframe=signal["timeframe"],
                        signal_type=signal["signal_type"]
                    )

            return notifications_added

        except Exception as e:
            self.logger.error(
                "Error generating RSI notifications",
                signals_count=len(signals),
                error=str(e)
            )
            return notifications_added

    async def process_rsi_update(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str,
            rsi_value: float,
            price: float,
            volume_change_percent: Optional[float] = None
    ) -> int:
        """
        Обработать обновление RSI и сгенерировать сигналы.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            rsi_value: Значение RSI
            price: Текущая цена
            volume_change_percent: Изменение объема

        Returns:
            int: Количество сгенерированных уведомлений
        """
        try:
            # Проверяем сигналы
            signals = await self.check_rsi_signals(
                session=session,
                symbol=symbol,
                timeframe=timeframe,
                current_rsi=rsi_value,
                current_price=price,
                volume_change_percent=volume_change_percent
            )

            # Генерируем уведомления
            notifications_count = await self.generate_notifications(signals)

            return notifications_count

        except Exception as e:
            self.logger.error(
                "Error processing RSI update",
                symbol=symbol,
                timeframe=timeframe,
                rsi_value=rsi_value,
                error=str(e)
            )
            return 0

    def _determine_rsi_signal_type(self, rsi_value: float) -> Optional[str]:
        """
        Определить тип RSI сигнала по значению.

        Args:
            rsi_value: Значение RSI

        Returns:
            str: Тип сигнала или None
        """
        if rsi_value <= self.rsi_zones["oversold_strong"]:
            return "rsi_oversold_strong"
        elif rsi_value <= self.rsi_zones["oversold_medium"]:
            return "rsi_oversold_medium"
        elif rsi_value <= self.rsi_zones["oversold_normal"]:
            return "rsi_oversold_normal"
        elif rsi_value >= self.rsi_zones["overbought_strong"]:
            return "rsi_overbought_strong"
        elif rsi_value >= self.rsi_zones["overbought_medium"]:
            return "rsi_overbought_medium"
        elif rsi_value >= self.rsi_zones["overbought_normal"]:
            return "rsi_overbought_normal"
        else:
            return None

    def _get_signal_priority(self, signal_type: str) -> str:
        """
        Определить приоритет сигнала.

        Args:
            signal_type: Тип сигнала

        Returns:
            str: Приоритет (HIGH, MEDIUM, LOW)
        """
        if "strong" in signal_type:
            return "HIGH"
        elif "medium" in signal_type:
            return "MEDIUM"
        else:
            return "LOW"

    async def _get_users_for_notification(
            self,
            session: AsyncSession,
            symbol: str,
            timeframe: str
    ) -> List[int]:
        """
        Получить список пользователей для уведомления.

        Args:
            session: Сессия базы данных
            symbol: Символ торговой пары
            timeframe: Таймфрейм

        Returns:
            List[int]: Список ID пользователей
        """
        try:
            # Получаем пользователей через модель UserPair
            user_pairs = await UserPair.get_active_users_for_pair(
                session, symbol, timeframe
            )

            user_ids = [up.user_id for up in user_pairs]

            self.logger.debug(
                "Found users for notification",
                symbol=symbol,
                timeframe=timeframe,
                users_count=len(user_ids)
            )

            return user_ids

        except Exception as e:
            self.logger.error(
                "Error getting users for notification",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return []

    async def _can_send_signal(
            self,
            session: AsyncSession,
            user_id: int,
            symbol: str,
            timeframe: str,
            signal_type: str
    ) -> bool:
        """
        Проверить можно ли отправить сигнал пользователю.

        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            signal_type: Тип сигнала

        Returns:
            bool: True если можно отправлять
        """
        try:
            # Получаем минимальный интервал для этого типа сигнала
            min_interval = self.signal_intervals.get(
                signal_type.replace("rsi_", ""),
                180  # По умолчанию 3 минуты
            )

            # Проверяем последний сигнал этого типа
            cutoff_time = datetime.now() - timedelta(seconds=min_interval)

            last_signal = await SignalHistory.get_last_signal(
                session=session,
                user_id=user_id,
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                since=cutoff_time
            )

            # Если есть недавний сигнал - не отправляем
            can_send = last_signal is None

            if not can_send:
                self.logger.debug(
                    "Signal blocked by rate limit",
                    user_id=user_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type=signal_type,
                    last_signal_time=last_signal.sent_at if last_signal else None
                )

            return can_send

        except Exception as e:
            self.logger.error(
                "Error checking signal rate limit",
                user_id=user_id,
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                error=str(e)
            )
            # В случае ошибки разрешаем отправку
            return True

    async def _save_signal_history(
            self,
            session: AsyncSession,
            signals: List[Dict[str, Any]]
    ) -> None:
        """
        Сохранить историю сигналов в БД.

        Args:
            session: Сессия базы данных
            signals: Список сигналов
        """
        try:
            for signal in signals:
                signal_history = SignalHistory(
                    user_id=signal["user_id"],
                    pair_id=None,  # Будет заполнен через триггер или отдельно
                    timeframe=signal["timeframe"],
                    signal_type=signal["signal_type"],
                    signal_value=Decimal(str(signal["rsi_value"])),
                    price=Decimal(str(signal["price"])),
                    sent_at=signal["timestamp"]
                )

                session.add(signal_history)

            await session.commit()

            self.logger.debug(
                "Signal history saved",
                count=len(signals)
            )

        except Exception as e:
            self.logger.error(
                "Error saving signal history",
                count=len(signals),
                error=str(e)
            )
            await session.rollback()


# Глобальный экземпляр генератора
rsi_signal_generator = RSISignalGenerator()