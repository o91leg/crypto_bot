"""
Путь: src/utils/telegram_helpers.py
Описание: Вспомогательные функции для безопасной работы с Telegram сообщениями
"""

from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def safe_edit_message(
    message: Message,
    text: str,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    **kwargs,
) -> None:
    """Безопасно редактировать сообщение.

    При возникновении ``TelegramBadRequest`` ошибка игнорируется,
    чтобы не прерывать работу бота.

    Args:
        message: Объект сообщения Telegram.
        text: Новый текст сообщения.
        keyboard: Клавиатура для прикрепления к сообщению.
        **kwargs: Дополнительные параметры для ``edit_text``.
    """
    try:
        await message.edit_text(text, reply_markup=keyboard, **kwargs)
    except TelegramBadRequest:
        pass

