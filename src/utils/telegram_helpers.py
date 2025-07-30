"""
Путь: src/utils/telegram_helpers.py
Описание: Утилиты для безопасной работы с Telegram API
Автор: Crypto Bot Team
Дата создания: 2025-07-30
"""

import re
from datetime import datetime
from typing import Optional
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from utils.logger import get_logger

logger = get_logger(__name__)


async def safe_edit_message(
    message: Message,
    new_text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    force_unique: bool = True
) -> bool:
    """
    Безопасно отредактировать сообщение с предотвращением ошибок дублирования.
    
    Args:
        message: Сообщение для редактирования
        new_text: Новый текст сообщения
        reply_markup: Клавиатура (опционально)
        force_unique: Принудительно делать сообщение уникальным
        
    Returns:
        bool: True если успешно отредактировано
    """
    try:
        # Если нужно - делаем сообщение уникальным
        if force_unique:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if "<i>🕐" not in new_text:  # Избегаем дублирования timestamp
                new_text += f"\n\n<i>🕐 Обновлено: {timestamp}</i>"
        
        await message.edit_text(new_text, reply_markup=reply_markup)
        return True
        
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.warning("Message content identical, skipping edit")
            return True
        elif "message to edit not found" in str(e):
            logger.warning("Message to edit not found")
            return False
        else:
            logger.error("Telegram Bad Request", error=str(e))
            return False
    except Exception as e:
        logger.error("Error editing message", error=str(e))
        return False


async def safe_send_message(
    bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Optional[Message]:
    """
    Безопасно отправить сообщение с обработкой ошибок.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст сообщения
        reply_markup: Клавиатура
        
    Returns:
        Message или None при ошибке
    """
    try:
        return await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        logger.error("Failed to send message", chat_id=chat_id, error=str(e))
        return None
    except Exception as e:
        logger.error("Unexpected error sending message", chat_id=chat_id, error=str(e))
        return None
