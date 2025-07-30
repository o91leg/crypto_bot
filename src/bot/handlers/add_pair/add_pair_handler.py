"""
Путь: src/bot/handlers/add_pair/add_pair_handler.py
Описание: Основные FSM обработчики для добавления торговых пар
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from bot.keyboards.main_menu_kb import get_main_menu_keyboard, get_back_to_menu_keyboard, get_confirmation_keyboard, get_loading_keyboard
from utils.logger import log_user_action
from .add_pair_formatters import (
    create_add_pair_instruction, create_pair_confirmation_text,
    create_pair_error_text, create_pair_added_text, create_add_error_text
)
from .add_pair_logic import process_symbol_input, execute_add_pair

# Настройка логирования
logger = structlog.get_logger(__name__)

# Создаем роутер для обработчиков
add_pair_router = Router()


class AddPairStates(StatesGroup):
    """Состояния FSM для добавления пары."""
    waiting_for_symbol = State()
    confirming_pair = State()


@add_pair_router.callback_query(F.data == "add_pair")
async def handle_add_pair_start(callback: CallbackQuery, state: FSMContext):
    """
    Начать процесс добавления новой торговой пары.

    Args:
        callback: Callback query
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Очищаем предыдущее состояние
        await state.clear()

        # Устанавливаем состояние ожидания символа
        await state.set_state(AddPairStates.waiting_for_symbol)

        instruction_text = create_add_pair_instruction()

        await callback.message.edit_text(
            instruction_text,
            reply_markup=get_back_to_menu_keyboard()
        )

        await callback.answer()
        logger.info("User started adding pair", user_id=user_id)

    except Exception as e:
        logger.error("Error starting add pair process", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@add_pair_router.message(AddPairStates.waiting_for_symbol)
async def handle_pair_symbol_input(message: Message, session: AsyncSession, state: FSMContext):
    """
    Обработать ввод символа торговой пары.

    Args:
        message: Сообщение от пользователя
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = message.from_user.id
    symbol_input = message.text.strip() if message.text else ""

    try:
        # Удаляем сообщение пользователя
        await message.delete()

        if not symbol_input:
            await message.answer(
                "❌ <b>Пустой ввод</b>\n\nВведите символ торговой пары:",
                reply_markup=get_back_to_menu_keyboard()
            )
            return

        # Показываем индикатор загрузки
        loading_msg = await message.answer(
            f"🔍 <b>Проверяем пару {symbol_input.upper()}...</b>\n\nПодождите, идет валидация через Binance API.",
            reply_markup=get_back_to_menu_keyboard()
        )

        # Обрабатываем символ
        result = await process_symbol_input(session, symbol_input, user_id)

        if result["success"]:
            # Символ валидный - показываем подтверждение
            await state.update_data(
                symbol=result["symbol"],
                base_asset=result.get("base_asset", ""),
                quote_asset=result.get("quote_asset", ""),
                display_name=result.get("display_name", ""),
                is_new_pair=result.get("is_new_pair", False)
            )

            await state.set_state(AddPairStates.confirming_pair)

            confirmation_text = create_pair_confirmation_text(result)

            # Создаем клавиатуру подтверждения
            confirmation_keyboard = get_confirmation_keyboard("add_pair", result["symbol"])

            await loading_msg.edit_text(
                confirmation_text,
                reply_markup=confirmation_keyboard
            )

            log_user_action(user_id, "pair_validated", symbol=result["symbol"])

        else:
            # Ошибка валидации
            error_text = create_pair_error_text(result["error"], symbol_input)

            await loading_msg.edit_text(
                error_text,
                reply_markup=get_back_to_menu_keyboard()
            )

            log_user_action(user_id, "pair_validation_failed",
                          symbol=symbol_input, error=result["error"])

    except Exception as e:
        logger.error("Error processing symbol input", user_id=user_id, symbol=symbol_input, error=str(e))

        error_text = f"""❌ <b>Ошибка обработки</b>

Не удалось обработать символ '{symbol_input}'.

Попробуйте еще раз или вернитесь в главное меню."""

        await message.answer(
            error_text,
            reply_markup=get_back_to_menu_keyboard()
        )


@add_pair_router.callback_query(F.data.startswith("confirm_add_pair_"))
async def handle_add_pair_confirmation(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Обработать подтверждение добавления пары.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        symbol = data.get("symbol")

        if not symbol:
            await callback.answer("Ошибка: нет данных о паре", show_alert=True)
            await state.clear()
            return

        # Показываем индикатор загрузки
        await callback.message.edit_text(
            "⏳ <b>Добавляем торговую пару...</b>\n\n"
            "Загружаем исторические данные и настраиваем отслеживание.",
            reply_markup=get_loading_keyboard()
        )

        # Выполняем добавление пары
        result = await execute_add_pair(session, user_id, data)

        if result["success"]:
            # Успешное добавление
            success_text = create_pair_added_text(result)

            await callback.message.edit_text(
                success_text,
                reply_markup=get_main_menu_keyboard()
            )

            logger.info(
                "Pair added successfully",
                user_id=user_id,
                symbol=symbol,
                historical_candles=result.get("historical_candles", 0)
            )
        else:
            # Ошибка добавления
            error_text = create_add_error_text(result["error"])

            await callback.message.edit_text(
                error_text,
                reply_markup=get_main_menu_keyboard()
            )

        await callback.answer()
        await state.clear()

    except Exception as e:
        logger.error("Error confirming pair addition", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)
        await state.clear()


@add_pair_router.callback_query(F.data.startswith("cancel_add_pair"))
async def handle_add_pair_cancellation(callback: CallbackQuery, state: FSMContext):
    """
    Обработать отмену добавления пары.

    Args:
        callback: Callback query
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        await state.clear()

        cancel_text = (
            "❌ <b>Добавление пары отменено</b>\n\n"
            "Вы можете попробовать добавить другую пару или вернуться в главное меню."
        )

        await callback.message.edit_text(
            cancel_text,
            reply_markup=get_main_menu_keyboard()
        )

        await callback.answer("Операция отменена")
        logger.info("User cancelled pair addition", user_id=user_id)

    except Exception as e:
        logger.error("Error cancelling pair addition", user_id=user_id, error=str(e))
        await callback.answer("Ошибка отмены", show_alert=True)


def register_add_pair_handlers(dp):
    """
    Зарегистрировать обработчики добавления пар.

    Args:
        dp: Диспетчер aiogram
    """
    dp.include_router(add_pair_router)