"""
Путь: src/bot/handlers/remove_pair_handler.py
Описание: Обработчик удаления торговых пар из отслеживания
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from bot.keyboards.main_menu_kb import (
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
    get_confirmation_keyboard
)
from data.models.user_model import User
from data.models.pair_model import Pair
from data.models.user_pair_model import UserPair
from utils.exceptions import RecordNotFoundError
from utils.logger import log_user_action

# Настройка логирования
logger = structlog.get_logger(__name__)

# Создаем роутер для обработчиков
remove_pair_router = Router()


class RemovePairStates(StatesGroup):
    """Состояния FSM для удаления пары."""
    selecting_pair = State()
    confirming_removal = State()


@remove_pair_router.callback_query(F.data == "remove_pair")
async def handle_remove_pair_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Начать процесс удаления торговой пары.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Очищаем предыдущее состояние
        await state.clear()

        # Получаем пары пользователя
        user_pairs = await UserPair.get_user_pairs(session, user_id)

        if not user_pairs:
            # У пользователя нет пар для удаления
            no_pairs_text = create_no_pairs_message()

            await callback.message.edit_text(
                no_pairs_text,
                reply_markup=get_back_to_menu_keyboard()
            )

            await callback.answer("У вас нет пар для удаления")
            log_user_action(user_id, "remove_pair_no_pairs")
            return

        # Устанавливаем состояние выбора пары
        await state.set_state(RemovePairStates.selecting_pair)

        # Создаем клавиатуру с парами пользователя
        pairs_keyboard = create_pairs_selection_keyboard(user_pairs)
        instruction_text = create_pair_selection_instruction(len(user_pairs))

        await callback.message.edit_text(
            instruction_text,
            reply_markup=pairs_keyboard
        )

        await callback.answer()

        log_user_action(user_id, "remove_pair_started", pairs_count=len(user_pairs))
        logger.info("User started removing pair", user_id=user_id, pairs_count=len(user_pairs))

    except Exception as e:
        logger.error("Error starting remove pair process", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@remove_pair_router.callback_query(F.data.startswith("select_remove_pair_"))
async def handle_pair_selection(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Обработать выбор пары для удаления.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары из callback_data
        pair_id = int(callback.data.split("_")[-1])

        # Получаем информацию о паре и пользовательской связи
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Сохраняем информацию в состоянии
        await state.update_data(
            pair_id=pair_id,
            pair_symbol=user_pair.pair.symbol,
            pair_display_name=user_pair.pair.display_name,
            enabled_timeframes=user_pair.get_enabled_timeframes(),
            signals_received=user_pair.signals_received,
            user_pair=user_pair
        )

        # Переходим к подтверждению
        await state.set_state(RemovePairStates.confirming_removal)

        # Создаем сообщение подтверждения
        confirmation_text = create_removal_confirmation_text(user_pair)

        await callback.message.edit_text(
            confirmation_text,
            reply_markup=get_confirmation_keyboard("remove_pair", str(pair_id))
        )

        await callback.answer()

        log_user_action(user_id, "remove_pair_selected", pair_symbol=user_pair.pair.symbol)
        logger.info("User selected pair for removal", user_id=user_id, pair_symbol=user_pair.pair.symbol)

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error selecting pair for removal", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@remove_pair_router.callback_query(F.data.startswith("confirm_remove_pair_"))
async def handle_remove_confirmation(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Обработать подтверждение удаления пары.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        pair_id = data.get("pair_id")
        pair_symbol = data.get("pair_symbol")

        if not pair_id or not pair_symbol:
            await callback.answer("Ошибка: нет данных о паре", show_alert=True)
            await state.clear()
            return

        # Выполняем удаление пары
        result = await execute_pair_removal(session, user_id, pair_id)

        if result["success"]:
            # Успешное удаление
            success_text = create_removal_success_text(result)

            await callback.message.edit_text(
                success_text,
                reply_markup=get_main_menu_keyboard()
            )

            log_user_action(user_id, "remove_pair_success", pair_symbol=pair_symbol)
            logger.info("Pair removed successfully", user_id=user_id, pair_symbol=pair_symbol)
        else:
            # Ошибка удаления
            error_text = create_removal_error_text(result["error"], pair_symbol)

            await callback.message.edit_text(
                error_text,
                reply_markup=get_main_menu_keyboard()
            )

            log_user_action(user_id, "remove_pair_error", pair_symbol=pair_symbol, error=result["error"])

        await callback.answer()
        await state.clear()

    except Exception as e:
        logger.error("Error confirming pair removal", user_id=user_id, error=str(e), exc_info=True)

        await callback.answer("Произошла ошибка", show_alert=True)
        await state.clear()


@remove_pair_router.callback_query(F.data.startswith("cancel_remove_pair"))
async def handle_remove_cancellation(callback: CallbackQuery, state: FSMContext):
    """
    Обработать отмену удаления пары.

    Args:
        callback: Callback query
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        await state.clear()

        cancel_text = (
            "❌ <b>Удаление пары отменено</b>\n\n"
            "Все ваши пары остаются в отслеживании.\n"
            "Вы можете вернуться в главное меню или попробовать удалить другую пару."
        )

        await callback.message.edit_text(
            cancel_text,
            reply_markup=get_main_menu_keyboard()
        )

        await callback.answer("Операция отменена")

        log_user_action(user_id, "remove_pair_cancelled")
        logger.info("User cancelled pair removal", user_id=user_id)

    except Exception as e:
        logger.error("Error cancelling pair removal", user_id=user_id, error=str(e))
        await callback.answer("Ошибка отмены", show_alert=True)


async def execute_pair_removal(session: AsyncSession, user_id: int, pair_id: int) -> dict:
    """
    Выполнить удаление пары из отслеживания пользователя.

    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        pair_id: ID пары

    Returns:
        dict: Результат выполнения
    """
    try:
        # Получаем связь пользователь-пара
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            return {
                "success": False,
                "error": "Пара не найдена в вашем отслеживании"
            }

        # Получаем информацию о паре для ответа
        pair = user_pair.pair
        pair_symbol = pair.symbol
        pair_display_name = pair.display_name
        signals_received = user_pair.signals_received

        # Удаляем связь пользователь-пара
        await session.delete(user_pair)

        # Уменьшаем счетчик пользователей пары
        pair.decrement_users_count()

        # Коммитим изменения
        await session.commit()

        return {
            "success": True,
            "pair_symbol": pair_symbol,
            "pair_display_name": pair_display_name,
            "signals_received": signals_received,
            "remaining_users": pair.users_count
        }

    except Exception as e:
        await session.rollback()
        logger.error("Error executing pair removal", user_id=user_id, pair_id=pair_id, error=str(e))

        return {
            "success": False,
            "error": f"Ошибка при удалении пары: {str(e)}"
        }


def create_pairs_selection_keyboard(user_pairs: list) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора пары для удаления.

    Args:
        user_pairs: Список пар пользователя

    Returns:
        InlineKeyboardMarkup: Клавиатура с парами
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для каждой пары
    for user_pair in user_pairs:
        pair = user_pair.pair
        enabled_timeframes = user_pair.get_enabled_timeframes()

        # Создаем текст кнопки с информацией о паре
        button_text = f"{pair.display_name} ({len(enabled_timeframes)} TF)"

        builder.add(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_remove_pair_{pair.id}"
            )
        )

    # Располагаем кнопки по одной в ряд для лучшей читаемости
    builder.adjust(1)

    # Добавляем кнопку возврата в меню
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )

    return builder.as_markup()


def create_no_pairs_message() -> str:
    """
    Создать сообщение об отсутствии пар для удаления.

    Returns:
        str: Сообщение об отсутствии пар
    """
    return """ℹ️ <b>Нет пар для удаления</b>

У вас пока нет торговых пар в отслеживании.

<b>Что можно сделать:</b>
• Добавить новую пару через "➕ Добавить пару"
• Вернуться в главное меню

<i>После добавления пар вы сможете управлять ими здесь.</i>"""


def create_pair_selection_instruction(pairs_count: int) -> str:
    """
    Создать инструкцию для выбора пары.

    Args:
        pairs_count: Количество пар

    Returns:
        str: Текст инструкции
    """
    return f"""➖ <b>Удаление торговой пары</b>

У вас в отслеживании <b>{pairs_count}</b> {_get_pairs_word(pairs_count)}.

Выберите пару, которую хотите удалить из отслеживания:

<i>⚠️ При удалении пары вы перестанете получать сигналы по ней, но сможете добавить её снова в любое время.</i>"""


def create_removal_confirmation_text(user_pair) -> str:
    """
    Создать текст подтверждения удаления.

    Args:
        user_pair: Связь пользователь-пара

    Returns:
        str: Текст подтверждения
    """
    pair = user_pair.pair
    enabled_timeframes = user_pair.get_enabled_timeframes()

    return f"""⚠️ <b>Подтвердите удаление</b>

<b>Пара:</b> {pair.display_name}
<b>Символ:</b> {pair.symbol}
<b>Активные таймфреймы:</b> {', '.join(enabled_timeframes) if enabled_timeframes else 'Нет'}
<b>Получено сигналов:</b> {user_pair.signals_received}

<b>Что произойдет при удалении:</b>
• Вы перестанете получать сигналы по этой паре
• Настройки таймфреймов будут удалены
• История сигналов сохранится
• Вы сможете добавить пару снова в любое время

<b>Удалить эту пару из отслеживания?</b>"""


def create_removal_success_text(result: dict) -> str:
    """
    Создать текст успешного удаления пары.

    Args:
        result: Результат удаления

    Returns:
        str: Текст успеха
    """
    pair_display_name = result.get("pair_display_name")
    signals_received = result.get("signals_received", 0)

    return f"""✅ <b>Пара успешно удалена</b>

<b>Удаленная пара:</b> {pair_display_name}
<b>Было получено сигналов:</b> {signals_received}

<b>Результат:</b>
• Уведомления по этой паре отключены
• Настройки таймфреймов удалены
• История сигналов сохранена

<b>Что дальше?</b>
• Вы можете добавить другие пары для отслеживания
• Эту же пару можно добавить снова в любое время
• История ваших сигналов доступна в разделе настроек

<i>💡 Для добавления новых пар используйте "➕ Добавить пару"</i>"""


def create_removal_error_text(error: str, pair_symbol: str) -> str:
    """
    Создать текст ошибки удаления пары.

    Args:
        error: Описание ошибки
        pair_symbol: Символ пары

    Returns:
        str: Текст ошибки
    """
    return f"""❌ <b>Ошибка удаления пары</b>

<b>Пара:</b> {pair_symbol}
<b>Ошибка:</b> {error}

<b>Что можно сделать:</b>
• Попробовать удалить пару еще раз
• Проверить, что пара все еще в отслеживании
• Обратиться к администратору

Вы можете вернуться в главное меню и попробовать позже."""


def _get_pairs_word(count: int) -> str:
    """
    Получить правильное склонение слова "пара".

    Args:
        count: Количество пар

    Returns:
        str: Склоненное слово
    """
    if count % 10 == 1 and count % 100 != 11:
        return "пара"
    elif count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
        return "пары"
    else:
        return "пар"


def register_remove_pair_handlers(dp):
    """
    Зарегистрировать обработчики удаления пар.

    Args:
        dp: Диспетчер aiogram
    """
    dp.include_router(remove_pair_router)