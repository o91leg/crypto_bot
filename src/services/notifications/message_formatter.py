"""
Путь: src/services/notifications/message_formatter.py
Описание: Сервис для форматирования уведомлений и сообщений
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime

from utils.constants import EMOJI, TREND_EMOJIS, CURRENCY_SYMBOLS
from utils.logger import get_logger


class MessageFormatter:
    """
    Сервис для форматирования сообщений.

    Включает:
    - Форматирование сигналов RSI/EMA
    - Форматирование цен и процентов
    - Эмодзи для разных типов сигналов
    - HTML разметку для Telegram
    """

    def __init__(self):
        """Инициализация форматировщика."""
        self.logger = get_logger(__name__)

    def format_signal_message(
            self,
            symbol: str,
            timeframe: str,
            price: float,
            price_change_percent: Optional[float] = None,
            rsi_value: Optional[float] = None,
            rsi_signal_type: Optional[str] = None,
            volume_change_percent: Optional[float] = None,
            ema_trend: Optional[str] = None,
            signal_type: str = "rsi_signal"
    ) -> str:
        """
        Форматировать сообщение о сигнале.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            price: Текущая цена
            price_change_percent: Изменение цены в %
            rsi_value: Значение RSI
            rsi_signal_type: Тип RSI сигнала
            volume_change_percent: Изменение объема в %
            ema_trend: Тренд EMA
            signal_type: Тип сигнала

        Returns:
            str: Отформатированное сообщение
        """
        try:
            # Определяем эмодзи для сигнала
            signal_emoji = self._get_signal_emoji(rsi_signal_type or signal_type)

            # Форматируем заголовок
            header = f"{signal_emoji} <b>{symbol}</b> - {timeframe}"

            # Форматируем цену
            price_text = self._format_price_line(price, price_change_percent)

            # Форматируем RSI
            rsi_text = self._format_rsi_line(rsi_value, rsi_signal_type)

            # Форматируем объем
            volume_text = self._format_volume_line(volume_change_percent)

            # Форматируем EMA тренд
            ema_text = self._format_ema_trend_line(ema_trend)

            # Собираем сообщение
            message_parts = [header, price_text]

            if rsi_text:
                message_parts.append(rsi_text)

            if volume_text:
                message_parts.append(volume_text)

            if ema_text:
                message_parts.append(ema_text)

            message = "\n".join(message_parts)

            self.logger.debug(
                "Signal message formatted",
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type
            )

            return message

        except Exception as e:
            self.logger.error(
                "Error formatting signal message",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )

            # Возвращаем простое сообщение в случае ошибки
            return f"🔔 {symbol} - {timeframe}\nЦена: ${price:.4f}"

    def format_pair_added_message(
            self,
            symbol: str,
            current_price: Optional[float] = None
    ) -> str:
        """
        Форматировать сообщение о добавлении пары.

        Args:
            symbol: Символ торговой пары
            current_price: Текущая цена

        Returns:
            str: Отформатированное сообщение
        """
        message = f"✅ <b>Пара {symbol} добавлена в отслеживание</b>\n\n"

        if current_price:
            message += f"Текущая цена: <b>${current_price:.4f}</b>\n"

        message += (
            f"{EMOJI['bell']} Уведомления включены для всех таймфреймов\n"
            f"{EMOJI['chart']} Исторические данные загружаются...\n\n"
            f"<i>Вы будете получать сигналы RSI и EMA для этой пары</i>"
        )

        return message

    def format_pair_removed_message(self, symbol: str) -> str:
        """
        Форматировать сообщение об удалении пары.

        Args:
            symbol: Символ торговой пары

        Returns:
            str: Отформатированное сообщение
        """
        return (
            f"❌ <b>Пара {symbol} удалена из отслеживания</b>\n\n"
            f"{EMOJI['info']} Уведомления для этой пары отключены\n"
            f"<i>Вы можете добавить её обратно в любое время</i>"
        )

    def format_my_pairs_message(
            self,
            pairs: List[Dict[str, Any]],
            user_name: Optional[str] = None
    ) -> str:
        """
        Форматировать сообщение со списком пар пользователя.

        Args:
            pairs: Список пар пользователя
            user_name: Имя пользователя

        Returns:
            str: Отформатированное сообщение
        """
        if user_name:
            header = f"📈 <b>Пары пользователя {user_name}</b>\n\n"
        else:
            header = "📈 <b>Ваши отслеживаемые пары</b>\n\n"

        if not pairs:
            return (
                    header +
                    f"{EMOJI['info']} У вас пока нет отслеживаемых пар\n\n"
                    f"Используйте кнопку <b>\"➕ Добавить пару\"</b> для начала работы"
            )

        pairs_text = []
        for pair in pairs:
            symbol = pair.get("symbol", "")
            current_price = pair.get("current_price")
            price_change = pair.get("price_change_24h")
            active_timeframes = pair.get("active_timeframes", 0)

            pair_line = f"• <b>{symbol}</b>"

            if current_price:
                pair_line += f" - ${current_price:.4f}"

                if price_change is not None:
                    change_emoji = "📈" if price_change >= 0 else "📉"
                    pair_line += f" ({change_emoji}{price_change:+.2f}%)"

            pair_line += f"\n  {EMOJI['gear']} Активных таймфреймов: {active_timeframes}"

            pairs_text.append(pair_line)

        message = header + "\n\n".join(pairs_text)
        message += f"\n\n<i>Нажмите на пару для настройки таймфреймов</i>"

        return message

    def format_rsi_current_values(
            self,
            symbol: str,
            rsi_values: Dict[str, float]
    ) -> str:
        """
        Форматировать текущие значения RSI.

        Args:
            symbol: Символ торговой пары
            rsi_values: Словарь значений RSI по таймфреймам

        Returns:
            str: Отформатированное сообщение
        """
        header = f"📊 <b>RSI для {symbol}</b>\n\n"

        if not rsi_values:
            return header + "⏳ Данные RSI загружаются..."

        rsi_lines = []
        for timeframe in ["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1w"]:
            if timeframe in rsi_values:
                rsi_value = rsi_values[timeframe]
                rsi_emoji = self._get_rsi_emoji(rsi_value)
                zone_text = self._get_rsi_zone_text(rsi_value)

                rsi_lines.append(
                    f"{rsi_emoji} <b>{timeframe}</b>: {rsi_value:.1f} <i>({zone_text})</i>"
                )

        if rsi_lines:
            message = header + "\n".join(rsi_lines)
        else:
            message = header + "⏳ Данные RSI загружаются..."

        message += f"\n\n<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"

        return message

    def format_settings_message(
            self,
            notifications_enabled: bool,
            total_pairs: int,
            active_timeframes: int
    ) -> str:
        """
        Форматировать сообщение настроек.

        Args:
            notifications_enabled: Включены ли уведомления
            total_pairs: Общее количество пар
            active_timeframes: Активных таймфреймов

        Returns:
            str: Отформатированное сообщение
        """
        status_emoji = "🔔" if notifications_enabled else "🔕"
        status_text = "включены" if notifications_enabled else "отключены"

        message = (
            f"⚙️ <b>Настройки бота</b>\n\n"
            f"{status_emoji} <b>Уведомления:</b> {status_text}\n"
            f"📈 <b>Отслеживаемых пар:</b> {total_pairs}\n"
            f"⏰ <b>Активных таймфреймов:</b> {active_timeframes}\n\n"
            f"<i>Используйте кнопки ниже для изменения настроек</i>"
        )

        return message

    def format_help_message(self) -> str:
        """
        Форматировать сообщение помощи.

        Returns:
            str: Отформатированное сообщение
        """
        return (
            f"❓ <b>Помощь по использованию бота</b>\n\n"

            f"<b>🚀 Начало работы:</b>\n"
            f"1. Добавьте криптопару (например: BTC, ETH, SOL)\n"
            f"2. Выберите нужные таймфреймы\n"
            f"3. Получайте сигналы в реальном времени!\n\n"

            f"<b>📊 Индикаторы:</b>\n"
            f"• <b>RSI</b> - индекс относительной силы\n"
            f"  🔴 &lt;25: сильная перепроданность\n"
            f"  🟠 25-30: средняя перепроданность\n"
            f"  🟡 30-70: нормальная зона\n"
            f"  🟠 70-75: средняя перекупленность\n"
            f"  🔴 &gt;75: сильная перекупленность\n\n"

            f"• <b>EMA</b> - экспоненциальное скользящее среднее\n"
            f"  📈 Восходящий тренд\n"
            f"  📉 Нисходящий тренд\n"
            f"  ➡️ Боковое движение\n\n"

            f"<b>🔔 Уведомления:</b>\n"
            f"• Приходят при входе в зоны RSI\n"
            f"• Повторяются каждые 2 минуты\n"
            f"• Включают данные об объеме\n\n"

            f"<b>⚙️ Настройки:</b>\n"
            f"• Включение/отключение уведомлений\n"
            f"• Выбор таймфреймов для каждой пары\n"
            f"• Просмотр текущих значений RSI\n\n"

            f"<i>Если у вас есть вопросы, обратитесь к администратору</i>"
        )

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def _format_price_line(
            self,
            price: float,
            price_change_percent: Optional[float] = None
    ) -> str:
        """Форматировать строку с ценой."""
        price_text = f"Цена: <b>${price:.4f}</b>"

        if price_change_percent is not None:
            if price_change_percent >= 0:
                change_emoji = "📈"
                sign = "+"
            else:
                change_emoji = "📉"
                sign = ""

            price_text += f" ({change_emoji}{sign}{price_change_percent:.1f}%)"

        return price_text

    def _format_rsi_line(
            self,
            rsi_value: Optional[float],
            rsi_signal_type: Optional[str]
    ) -> Optional[str]:
        """Форматировать строку с RSI."""
        if rsi_value is None:
            return None

        rsi_emoji = self._get_rsi_emoji(rsi_value)
        zone_text = self._get_rsi_zone_text(rsi_value)

        return f"RSI: <b>{rsi_value:.1f}</b> {rsi_emoji} <i>({zone_text})</i>"

    def _format_volume_line(
            self,
            volume_change_percent: Optional[float]
    ) -> Optional[str]:
        """Форматировать строку с объемом."""
        if volume_change_percent is None:
            return None

        if volume_change_percent >= 0:
            volume_emoji = "📊"
            sign = "+"
        else:
            volume_emoji = "📉"
            sign = ""

        return f"Объем: {volume_emoji} {sign}{volume_change_percent:.0f}% от предыдущей свечи"

    def _format_ema_trend_line(
            self,
            ema_trend: Optional[str]
    ) -> Optional[str]:
        """Форматировать строку с EMA трендом."""
        if not ema_trend:
            return None

        trend_emoji = TREND_EMOJIS.get(ema_trend, "➡️")

        trend_names = {
            "bullish": "восходящий",
            "bearish": "нисходящий",
            "sideways": "боковой",
            "strong_up": "сильный рост",
            "strong_down": "сильное падение"
        }

        trend_name = trend_names.get(ema_trend, ema_trend)

        return f"EMA тренд: {trend_emoji} <i>{trend_name}</i>"

    def _get_signal_emoji(self, signal_type: str) -> str:
        """Получить эмодзи для типа сигнала."""
        signal_emojis = {
            "rsi_oversold_strong": "🔴",
            "rsi_oversold_medium": "🟠",
            "rsi_oversold_normal": "🟡",
            "rsi_overbought_normal": "🟡",
            "rsi_overbought_medium": "🟠",
            "rsi_overbought_strong": "🔴",
            "ema_cross_up": "🚀",
            "ema_cross_down": "💥",
            "volume_spike": "🔥"
        }

        return signal_emojis.get(signal_type, "🔔")

    def _get_rsi_emoji(self, rsi_value: float) -> str:
        """Получить эмодзи для значения RSI."""
        if rsi_value < 20:
            return "🔴"
        elif rsi_value < 25:
            return "🟠"
        elif rsi_value < 30:
            return "🟡"
        elif rsi_value > 80:
            return "🔴"
        elif rsi_value > 75:
            return "🟠"
        elif rsi_value > 70:
            return "🟡"
        else:
            return "🟢"

    def _get_rsi_zone_text(self, rsi_value: float) -> str:
        """Получить текстовое описание зоны RSI."""
        if rsi_value < 20:
            return "сильная перепроданность"
        elif rsi_value < 25:
            return "средняя перепроданность"
        elif rsi_value < 30:
            return "обычная перепроданность"
        elif rsi_value > 80:
            return "сильная перекупленность"
        elif rsi_value > 75:
            return "средняя перекупленность"
        elif rsi_value > 70:
            return "обычная перекупленность"
        else:
            return "нормальная зона"


# Глобальная функция для удобства
def format_signal_message(
        symbol: str,
        timeframe: str,
        price: float,
        price_change_percent: Optional[float] = None,
        rsi_value: Optional[float] = None,
        rsi_signal_type: Optional[str] = None,
        volume_change_percent: Optional[float] = None,
        ema_trend: Optional[str] = None,
        signal_type: str = "rsi_signal"
) -> str:
    """
    Глобальная функция для форматирования сигналов.

    Args:
        symbol: Символ торговой пары
        timeframe: Таймфрейм
        price: Текущая цена
        price_change_percent: Изменение цены в %
        rsi_value: Значение RSI
        rsi_signal_type: Тип RSI сигнала
        volume_change_percent: Изменение объема в %
        ema_trend: Тренд EMA
        signal_type: Тип сигнала

    Returns:
        str: Отформатированное сообщение
    """
    formatter = MessageFormatter()
    return formatter.format_signal_message(
        symbol=symbol,
        timeframe=timeframe,
        price=price,
        price_change_percent=price_change_percent,
        rsi_value=rsi_value,
        rsi_signal_type=rsi_signal_type,
        volume_change_percent=volume_change_percent,
        ema_trend=ema_trend,
        signal_type=signal_type
    )