"""
Путь: src/bot/keyboards/main_menu_kb.py
Описание: Inline клавиатура главного меню бота
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру главного меню.

    Returns:
        InlineKeyboardMarkup: Клавиатура главного меню
    """
    builder = InlineKeyboardBuilder()

    # Первый ряд - основные функции
    builder.row(
        InlineKeyboardButton(
            text="📈 Мои пары",
            callback_data="my_pairs"
        ),
        InlineKeyboardButton(
            text="➕ Добавить пару",
            callback_data="add_pair"
        ),
        width=2
    )

    # Второй ряд - управление
    builder.row(
        InlineKeyboardButton(
            text="➖ Удалить пару",
            callback_data="remove_pair"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings"
        ),
        width=2
    )

    # Третий ряд - помощь
    builder.row(
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data="help"
        ),
        width=1
    )

    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с кнопкой возврата в главное меню.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой возврата
    """
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()


def get_confirmation_keyboard(action: str, item_id: str = None) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру подтверждения действия.

    Args:
        action: Действие для подтверждения
        item_id: ID элемента (опционально)

    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    builder = InlineKeyboardBuilder()

    # Формируем callback_data для подтверждения
    confirm_data = f"confirm_{action}"
    cancel_data = f"cancel_{action}"

    if item_id:
        confirm_data += f"_{item_id}"
        cancel_data += f"_{item_id}"

    builder.row(
        InlineKeyboardButton(
            text="✅ Да",
            callback_data=confirm_data
        ),
        InlineKeyboardButton(
            text="❌ Нет",
            callback_data=cancel_data
        ),
        width=2
    )

    # Кнопка возврата в меню
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        ),
        width=1
    )

    return builder.as_markup()


def get_loading_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру с индикатором загрузки.

    Returns:
        InlineKeyboardMarkup: Клавиатура с индикатором загрузки
    """
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(
            text="⏳ Загрузка...",
            callback_data="loading"
        )
    )

    return builder.as_markup()


def get_menu_with_notification_button(show_notification_controls: bool = True) -> InlineKeyboardMarkup:
    """
    Создать расширенное меню с дополнительными кнопками.

    Args:
        show_notification_controls: Показать ли кнопки управления уведомлениями

    Returns:
        InlineKeyboardMarkup: Расширенная клавиатура меню
    """
    builder = InlineKeyboardBuilder()

    # Основные кнопки меню
    builder.row(
        InlineKeyboardButton(
            text="📈 Мои пары",
            callback_data="my_pairs"
        ),
        InlineKeyboardButton(
            text="➕ Добавить пару",
            callback_data="add_pair"
        ),
        width=2
    )

    builder.row(
        InlineKeyboardButton(
            text="➖ Удалить пару",
            callback_data="remove_pair"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings"
        ),
        width=2
    )

    # Дополнительные кнопки управления уведомлениями
    if show_notification_controls:
        builder.row(
            InlineKeyboardButton(
                text="🔔 Уведомления ВКЛ",
                callback_data="toggle_notifications"
            ),
            width=1
        )

    builder.row(
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data="help"
        ),
        width=1
    )

    return builder.as_markup()


def get_navigation_keyboard(
        back_callback: str = "main_menu",
        additional_buttons: list = None
) -> InlineKeyboardMarkup:
    """
    Создать навигационную клавиатуру.

    Args:
        back_callback: Callback для кнопки "Назад"
        additional_buttons: Дополнительные кнопки [(text, callback), ...]

    Returns:
        InlineKeyboardMarkup: Навигационная клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Добавляем дополнительные кнопки если есть
    if additional_buttons:
        for button_text, button_callback in additional_buttons:
            builder.add(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=button_callback
                )
            )

    # Кнопка возврата
    back_text = "🏠 Главное меню" if back_callback == "main_menu" else "⬅️ Назад"
    builder.row(
        InlineKeyboardButton(
            text=back_text,
            callback_data=back_callback
        ),
        width=1
    )

    return builder.as_markup()


def get_error_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для сообщений об ошибках.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой возврата в меню
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔄 Попробовать снова",
            callback_data="main_menu"
        ),
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data="help"
        ),
        width=2
    )

    return builder.as_markup()