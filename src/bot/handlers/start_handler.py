"""
Путь: src/bot/handlers/start_handler.py
Описание: Обработчик команды /start и регистрации новых пользователей
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import Any
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from bot.keyboards.main_menu_kb import get_main_menu_keyboard
from data.models.user_model import User
from data.models.pair_model import Pair
from data.models.user_pair_model import UserPair
from config.bot_config import get_bot_config

# Настройка логирования
logger = structlog.get_logger(__name__)

# Создаем роутер для обработчиков
start_router = Router()


@start_router.message(CommandStart())
async def handle_start_command(message: Message, session: AsyncSession, state: FSMContext):
    """
    Обработчик команды /start.

    Args:
        message: Сообщение пользователя
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = message.from_user.id

    try:
        # Очищаем состояние FSM
        await state.clear()

        # Получаем или создаем пользователя
        user = await get_or_create_user(session, message.from_user)

        # Проверяем, первый ли это запуск для пользователя
        is_new_user = user.total_signals_received == 0

        if is_new_user:
            # Создаем дефолтную пару для нового пользователя
            await setup_default_pair_for_user(session, user.id)

            # Отправляем приветственное сообщение
            welcome_text = create_welcome_message(user.display_name)
            await message.answer(
                welcome_text,
                reply_markup=get_main_menu_keyboard()
            )

            logger.info("New user registered", user_id=user_id, username=message.from_user.username)
        else:
            # Отправляем обычное сообщение для существующего пользователя
            welcome_back_text = create_welcome_back_message(user.display_name)
            await message.answer(
                welcome_back_text,
                reply_markup=get_main_menu_keyboard()
            )

            logger.info("Existing user returned", user_id=user_id)

        # Коммитим изменения в БД
        await session.commit()

    except Exception as e:
        logger.error("Error in start command handler", user_id=user_id, error=str(e), exc_info=True)
        await session.rollback()

        # Отправляем сообщение об ошибке
        error_text = (
            "❌ <b>Произошла ошибка при запуске бота</b>\n\n"
            "Попробуйте еще раз через несколько секунд или обратитесь к администратору."
        )
        await message.answer(error_text)


@start_router.callback_query(F.data == "main_menu")
async def handle_main_menu_callback(callback: CallbackQuery):
    """
    Обработчик callback для возврата в главное меню.

    Args:
        callback: Callback query
    """
    try:
        # Обновляем сообщение с главным меню
        menu_text = create_main_menu_message()

        await callback.message.edit_text(
            menu_text,
            reply_markup=get_main_menu_keyboard()
        )

        # Подтверждаем callback
        await callback.answer()

        logger.info("User returned to main menu", user_id=callback.from_user.id)

    except Exception as e:
        logger.error(
            "Error in main menu callback",
            user_id=callback.from_user.id,
            error=str(e)
        )
        await callback.answer("Произошла ошибка", show_alert=True)


async def get_or_create_user(session: AsyncSession, telegram_user: Any) -> User:
    """
    Получить существующего пользователя или создать нового.

    Args:
        session: Сессия базы данных
        telegram_user: Объект пользователя от Telegram

    Returns:
        User: Пользователь из базы данных
    """
    user_id = telegram_user.id

    # Пытаемся найти существующего пользователя
    user = await User.get_by_telegram_id(session, user_id)

    if user is None:
        # Создаем нового пользователя
        user = User(
            id=user_id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
        )
        session.add(user)
        await session.flush()

        logger.info("New user created", user_id=user_id, username=telegram_user.username)
    else:
        # Обновляем информацию существующего пользователя
        updated = False

        if user.username != telegram_user.username:
            user.username = telegram_user.username
            updated = True

        if user.first_name != telegram_user.first_name:
            user.first_name = telegram_user.first_name
            updated = True

        if user.last_name != telegram_user.last_name:
            user.last_name = telegram_user.last_name
            updated = True

        if updated:
            logger.info("User information updated", user_id=user_id)

    return user


async def setup_default_pair_for_user(session: AsyncSession, user_id: int) -> None:
    """
    Настроить дефолтную пару для нового пользователя.

    Args:
        session: Сессия базы данных
        user_id: ID пользователя
    """
    config = get_bot_config()

    try:
        # Находим дефолтную пару
        default_pair = await Pair.get_by_symbol(session, config.default_pair)

        if default_pair is None:
            # Создаем пару если её нет
            default_pair = await Pair.create_from_symbol(session, config.default_pair)
            logger.info("Created default pair", symbol=config.default_pair)

        # Создаем связь пользователь-пара с дефолтными таймфреймами
        user_pair = await UserPair.create_user_pair(
            session=session,
            user_id=user_id,
            pair_id=default_pair.id,
            timeframes={tf: True for tf in config.default_timeframes}
        )

        # Увеличиваем счетчик пользователей пары
        default_pair.increment_users_count()

        logger.info(
            "Default pair configured for user",
            user_id=user_id,
            pair_symbol=default_pair.symbol
        )

    except Exception as e:
        logger.error("Failed to setup default pair", user_id=user_id, error=str(e))
        raise


def create_welcome_message(user_name: str) -> str:
    """
    Создать приветственное сообщение для нового пользователя.

    Args:
        user_name: Имя пользователя

    Returns:
        str: Приветственное сообщение
    """
    return f"""🚀 <b>Добро пожаловать, {user_name}!</b>

🤖 Я крипто-бот для отслеживания технических индикаторов на рынке криптовалют.

<b>Что я умею:</b>
📈 Отслеживать индикаторы RSI и EMA
⚡ Отправлять сигналы в реальном времени
📊 Работать с разными таймфреймами
🔔 Уведомлять о важных уровнях

<b>Для начала:</b>
• Пара BTC/USDT уже добавлена в отслеживание
• Все таймфреймы включены по умолчанию
• Уведомления активированы

Выберите действие в меню ниже:"""


def create_welcome_back_message(user_name: str) -> str:
    """
    Создать сообщение для возвращающегося пользователя.

    Args:
        user_name: Имя пользователя

    Returns:
        str: Сообщение для возвращающегося пользователя
    """
    return f"""👋 <b>С возвращением, {user_name}!</b>

📊 Ваш крипто-бот готов к работе.

Выберите действие в меню ниже:"""


def create_main_menu_message() -> str:
    """
    Создать сообщение главного меню.

    Returns:
        str: Сообщение главного меню
    """
    return """🏠 <b>Главное меню</b>

📊 Управляйте своими криптовалютными сигналами:"""


def register_start_handlers(dp):
    """
    Зарегистрировать обработчики команды /start.

    Args:
        dp: Диспетчер aiogram
    """
    dp.include_router(start_router)