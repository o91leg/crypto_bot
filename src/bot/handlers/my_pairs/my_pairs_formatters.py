"""
Путь: src/bot/handlers/my_pairs/my_pairs_formatters.py
Описание: Форматирование текстовых сообщений для интерфейса торговых пар
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from config.bot_config import get_bot_config
from utils.time_helpers import get_timeframe_display_name


def create_no_pairs_message() -> str:
    """
    Создать сообщение об отсутствии пар.

    Returns:
        str: Сообщение об отсутствии пар
    """
    return """📈 <b>Мои торговые пары</b>

У вас пока нет торговых пар в отслеживании.

<b>Что можно сделать:</b>
• Добавить новую пару через "➕ Добавить пару"
• Изучить справку о работе бота

<i>После добавления пар здесь будет отображаться список с возможностью управления таймфреймами и просмотра индикаторов.</i>"""


def create_pairs_list_message(user_pairs: list) -> str:
    """
    Создать сообщение со списком пар пользователя.

    Args:
        user_pairs: Список пар пользователя

    Returns:
        str: Сообщение со списком пар
    """
    pairs_count = len(user_pairs)

    text = f"📈 <b>Мои торговые пары ({pairs_count})</b>\n\n"

    for i, user_pair in enumerate(user_pairs, 1):
        pair = user_pair.pair
        enabled_timeframes = user_pair.get_enabled_timeframes()

        text += f"<b>{i}. {pair.display_name}</b>\n"
        text += f"   • Символ: {pair.symbol}\n"
        text += f"   • Таймфреймы: {len(enabled_timeframes)}/{len(user_pair.timeframes)} активных\n"
        text += f"   • Сигналов получено: {user_pair.signals_received}\n\n"

    text += "<i>Нажмите на пару для управления таймфреймами и просмотра индикаторов.</i>"

    return text


def create_pair_management_message(user_pair) -> str:
    """
    Создать сообщение управления парой.

    Args:
        user_pair: Пользовательская пара

    Returns:
        str: Сообщение управления парой
    """
    pair = user_pair.pair
    enabled_timeframes = user_pair.get_enabled_timeframes()
    config = get_bot_config()

    text = f"""⚙️ <b>Управление парой {pair.display_name}</b>

<b>Информация о паре:</b>
• Символ: {pair.symbol}
• Базовая валюта: {pair.base_asset}
• Котируемая валюта: {pair.quote_asset}
• Получено сигналов: {user_pair.signals_received}

<b>Настройка таймфреймов:</b>
Включите нужные таймфреймы для получения сигналов"""

    # Добавляем информацию о состоянии таймфреймов
    if enabled_timeframes:
        text += f"\n\n<b>Активные таймфреймы ({len(enabled_timeframes)}):</b>\n"
        text += ", ".join(enabled_timeframes)
    else:
        text += f"\n\n⚠️ <b>Нет активных таймфреймов</b>\nВы не будете получать сигналы по этой паре."

    text += f"\n\n<i>💡 Используйте кнопки ниже для управления таймфреймами и просмотра RSI.</i>"

    return text


def create_rsi_display_message(user_pair, rsi_data: dict) -> str:
    """
    Создать сообщение с отображением RSI.

    Args:
        user_pair: Пользовательская пара
        rsi_data: Данные RSI по таймфреймам

    Returns:
        str: Сообщение с RSI данными
    """
    pair = user_pair.pair

    text = f"""📊 <b>RSI для {pair.display_name}</b>

<b>Текущие значения индикатора RSI:</b>"""

    if not rsi_data:
        text += "\n\n❌ <b>Нет данных для отображения</b>\nПроверьте активные таймфреймы."
        return text

    # Добавляем данные по каждому таймфрейму
    for timeframe, data in rsi_data.items():
        display_name = get_timeframe_display_name(timeframe)

        if "error" in data:
            error_text = str(data['error']).replace('<', '&lt;').replace('>', '&gt;')
            text += f"\n\n<b>{display_name}:</b> ❌ {error_text}"
        else:
            rsi_value = data.get("value", 0)
            interpretation = data.get("interpretation", {})

            # Эмодзи для уровня RSI
            if rsi_value <= 30:
                emoji = "🔴"  # Перепроданность
                level = "перепроданность"
            elif rsi_value >= 70:
                emoji = "🟢"  # Перекупленность
                level = "перекупленность"
            else:
                emoji = "🟡"  # Нейтральная зона
                level = "нейтральная зона"

            text += f"\n\n<b>{display_name}:</b> {emoji} <b>{rsi_value:.1f}</b>"
            text += f"\n   └ {level}"

    text += f"\n\n<i>⏰ Данные обновляются в реальном времени</i>"
    text += f"\n<i>💡 RSI &lt; 30 = перепроданность, RSI &gt; 70 = перекупленность</i>"
    # Добавляем уникальный элемент для предотвращения дублирования
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    text += f"\n\n<i>🕐 Последнее обновление: {timestamp}</i>"

    return text

def create_rsi_error_message() -> str:
    """
    Создать сообщение об ошибке RSI.

    Returns:
        str: Сообщение об ошибке
    """
    return """❌ <b>Ошибка загрузки RSI данных</b>

Не удалось рассчитать индикатор RSI для этой пары.

<b>Возможные причины:</b>
• Недостаточно исторических данных
• Временные проблемы с расчетом
• Проблемы подключения к базе данных

<b>Что можно сделать:</b>
• Попробовать через несколько минут
• Проверить, что пара недавно добавлена
• Обратиться к администратору

<i>Обычно данные становятся доступны через 1-2 минуты после добавления пары.</i>"""