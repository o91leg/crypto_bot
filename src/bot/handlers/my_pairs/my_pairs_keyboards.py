"""
Путь: src/bot/handlers/my_pairs/my_pairs_keyboards.py
Описание: Клавиатуры для интерфейса управления торговыми парами
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config.bot_config import get_bot_config
from utils.time_helpers import get_timeframe_display_name


def create_no_pairs_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для случая отсутствия пар.

    Returns:
        InlineKeyboardMarkup: Клавиатура без пар
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить пару",
            callback_data="add_pair"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()


def create_pairs_list_keyboard(user_pairs: list) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со списком пар.

    Args:
        user_pairs: Список пар пользователя

    Returns:
        InlineKeyboardMarkup: Клавиатура с парами
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для каждой пары
    for user_pair in user_pairs:
        pair = user_pair.pair
        enabled_count = len(user_pair.get_enabled_timeframes())

        button_text = f"{pair.display_name} ({enabled_count} TF)"

        builder.add(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"manage_pair_{pair.id}"
            )
        )

    # Располагаем по одной кнопке в ряд
    builder.adjust(1)

    # Добавляем кнопку возврата
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()


# ЗАМЕНИТЬ ФУНКЦИЮ create_pair_management_keyboard В ФАЙЛЕ src/bot/handlers/my_pairs/my_pairs_keyboards.py

def create_pair_management_keyboard(user_pair) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру управления парой.

    Args:
        user_pair: Пользовательская пара

    Returns:
        InlineKeyboardMarkup: Клавиатуру управления
    """
    builder = InlineKeyboardBuilder()
    config = get_bot_config()

    # Кнопки переключения таймфреймов
    for timeframe in config.default_timeframes:
        is_enabled = user_pair.is_timeframe_enabled(timeframe)

        # Эмодзи для состояния
        status_emoji = "✅" if is_enabled else "❌"
        display_name = get_timeframe_display_name(timeframe)

        button_text = f"{status_emoji} {display_name}"

        builder.add(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"toggle_timeframe_{timeframe}"
            )
        )

    # Располагаем таймфреймы по 2 в ряд
    builder.adjust(2)

    # Кнопки просмотра RSI - ДВА ВАРИАНТА
    builder.row(
        InlineKeyboardButton(
            text="📊 Текущий RSI",  # Быстрый просмотр из кеша
            callback_data=f"rsi_current_{user_pair.pair_id}"
        ),
        InlineKeyboardButton(
            text="📈 Полный RSI",   # Полный расчет с историей
            callback_data=f"view_rsi_{user_pair.pair_id}"
        )
    )

    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку пар",
            callback_data="my_pairs"
        ),
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()

def create_rsi_current_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для быстрого просмотра RSI.

    Args:
        pair_id: ID пары

    Returns:
        InlineKeyboardMarkup: Клавиатура для RSI
    """
    builder = InlineKeyboardBuilder()

    # Кнопка обновления
    builder.row(
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=f"rsi_current_{pair_id}"
        ),
        InlineKeyboardButton(
            text="📈 Полный RSI",
            callback_data=f"view_rsi_{pair_id}"
        )
    )

    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Управление парой",
            callback_data=f"back_to_management_{pair_id}"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку пар",
            callback_data="my_pairs"
        ),
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()

def create_rsi_display_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для отображения RSI.

    Args:
        pair_id: ID пары

    Returns:
        InlineKeyboardMarkup: Клавиатура RSI
    """
    builder = InlineKeyboardBuilder()

    # Кнопки обновления и действий
    builder.row(
        InlineKeyboardButton(
            text="🔄 Обновить RSI",
            callback_data=f"refresh_rsi_{pair_id}"
        ),
        InlineKeyboardButton(
            text="⚡ Быстрый RSI",
            callback_data=f"rsi_current_{pair_id}"
        )
    )

    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Управление парой",
            callback_data=f"back_to_management_{pair_id}"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ К списку пар",
            callback_data="my_pairs"
        ),
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()

def get_back_to_management_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру возврата к управлению.

    Args:
        pair_id: ID пары

    Returns:
        InlineKeyboardMarkup: Клавиатура возврата
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="⚙️ Управление парой",
            callback_data=f"back_to_management_{pair_id}"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()