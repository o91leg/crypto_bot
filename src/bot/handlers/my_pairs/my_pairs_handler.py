"""
Путь: src/bot/handlers/my_pairs/my_pairs_handler.py
Описание: Основные обработчики FSM для управления торговыми парами пользователя
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from datetime import datetime
import re
import structlog

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.user_pair_model import UserPair
from utils.logger import log_user_action
from .my_pairs_formatters import (
    create_no_pairs_message,
    create_pairs_list_message,
    create_pair_management_message,
    create_rsi_display_message,
    create_rsi_error_message,
)
from .my_pairs_keyboards import (
    create_no_pairs_keyboard,
    create_pairs_list_keyboard,
    create_pair_management_keyboard,
    create_rsi_display_keyboard,
    get_back_to_management_keyboard,
)
from .my_pairs_logic import calculate_rsi_for_pair

# Настройка логирования
logger = structlog.get_logger(__name__)

# Создаем роутер для обработчиков
my_pairs_router = Router()


# Временно отключаем кеш пока не исправим
class TempIndicatorCache:
    async def get_rsi(self, symbol, timeframe, period):
        return None

    async def invalidate_indicators(self, symbol):
        return True


indicator_cache = TempIndicatorCache()


async def safe_edit_message(
    message,
    new_text: str,
    reply_markup=None,
    max_retries: int = 3,
) -> bool:
    """
    Безопасно отредактировать сообщение с проверкой на изменения.

    Args:
        message: Сообщение для редактирования
        new_text: Новый текст
        reply_markup: Новая клавиатура
        max_retries: Максимум попыток

    Returns:
        bool: True если успешно отредактировано
    """
    try:
        # Сравниваем текст (убираем HTML теги для корректного сравнения)
        import re

        current_text = re.sub(r"<[^>]+>", "", message.text or "").strip()
        new_text_clean = re.sub(r"<[^>]+>", "", new_text).strip()

        # Если текст точно такой же - добавляем timestamp
        if current_text == new_text_clean:
            from datetime import datetime

            timestamp = datetime.now().strftime("%H:%M:%S")
            new_text += f"\n\n<i>🕐 Обновлено: {timestamp}</i>"

        await message.edit_text(new_text, reply_markup=reply_markup)
        return True

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.warning("Message content is identical, skipping edit")
            return True  # Считаем успешным, так как контент уже правильный
        else:
            logger.error("Telegram error editing message", error=str(e))
            return False
    except Exception as e:
        logger.error("Unexpected error editing message", error=str(e))
        return False


class MyPairsStates(StatesGroup):
    """Состояния FSM для управления парами."""

    viewing_pairs = State()
    managing_timeframes = State()
    viewing_rsi = State()


@my_pairs_router.callback_query(F.data == "my_pairs")
async def handle_my_pairs_start(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Показать пары пользователя.

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
            # У пользователя нет пар
            no_pairs_text = create_no_pairs_message()
            await callback.message.edit_text(
                no_pairs_text, reply_markup=create_no_pairs_keyboard()
            )
            await callback.answer("У вас нет отслеживаемых пар")
            log_user_action(user_id, "my_pairs_empty")
            return

        # Устанавливаем состояние просмотра пар
        await state.set_state(MyPairsStates.viewing_pairs)

        # Создаем сообщение со списком пар
        pairs_text = create_pairs_list_message(user_pairs)
        pairs_keyboard = create_pairs_list_keyboard(user_pairs)

        await callback.message.edit_text(pairs_text, reply_markup=pairs_keyboard)

        await callback.answer()
        log_user_action(user_id, "my_pairs_viewed", pairs_count=len(user_pairs))
        logger.info("User viewed pairs", user_id=user_id, pairs_count=len(user_pairs))

    except Exception as e:
        logger.error("Error showing user pairs", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@my_pairs_router.callback_query(F.data.startswith("manage_pair_"))
async def handle_pair_management(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Управление конкретной торговой парой.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары из callback_data
        pair_id = int(callback.data.split("_")[-1])

        # Получаем информацию о паре
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Сохраняем информацию в состоянии
        await state.update_data(
            pair_id=pair_id, pair_symbol=user_pair.pair.symbol, user_pair=user_pair
        )

        # Переходим к управлению таймфреймами
        await state.set_state(MyPairsStates.managing_timeframes)

        # Создаем сообщение управления парой
        management_text = create_pair_management_message(user_pair)
        management_keyboard = create_pair_management_keyboard(user_pair)

        await callback.message.edit_text(
            management_text, reply_markup=management_keyboard
        )

        await callback.answer()
        log_user_action(
            user_id, "pair_management_opened", pair_symbol=user_pair.pair.symbol
        )

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error managing pair", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@my_pairs_router.callback_query(F.data.startswith("toggle_timeframe_"))
async def handle_timeframe_toggle(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Переключить состояние таймфрейма с автозагрузкой данных.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем таймфрейм из callback_data
        timeframe = callback.data.split("_")[-1]

        # Получаем данные из состояния
        data = await state.get_data()
        pair_id = data.get("pair_id")

        if not pair_id:
            await callback.answer("Ошибка состояния", show_alert=True)
            return

        # Загружаем свежий объект из БД
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Переключаем таймфрейм
        new_state = user_pair.toggle_timeframe(timeframe)

        # Сохраняем изменения
        session.add(user_pair)
        await session.commit()

        # 🔥 НОВАЯ ЛОГИКА: Если таймфрейм ВКЛЮЧИЛИ - загружаем данные
        if new_state:  # Таймфрейм включен
            await callback.message.edit_text(
                f"📥 <b>Загрузка данных для {timeframe}</b>\n\n"
                f"Пара: {user_pair.pair.display_name}\n\n"
                f"⏳ Загружаем исторические данные...",
                reply_markup=create_pair_management_keyboard(user_pair),
            )

            # Загружаем данные для нового таймфрейма
            from services.data_fetchers.historical.historical_fetcher import (
                HistoricalDataFetcher,
            )

            try:
                async with HistoricalDataFetcher() as fetcher:
                    # ИСПРАВЛЕНИЕ: Используем fetch_timeframe_data вместо fetch_pair_historical_data
                    loaded_candles = await fetcher.fetch_timeframe_data(
                        session=session,
                        pair_id=pair_id,
                        symbol=user_pair.pair.symbol,
                        timeframe=timeframe,  # Только этот таймфрейм
                        limit=500,
                    )

                logger.info(
                    "Timeframe data loaded automatically",
                    timeframe=timeframe,
                    candles_loaded=loaded_candles,
                    pair_symbol=user_pair.pair.symbol,
                )

                if loaded_candles > 0:
                    success_message = f"✅ Таймфрейм {timeframe} включен\n📊 Загружено {loaded_candles} свечей"
                else:
                    success_message = (
                        f"⚠️ Таймфрейм {timeframe} включен\n❌ Нет данных для загрузки"
                    )

            except Exception as e:
                logger.error(
                    "Error loading timeframe data", timeframe=timeframe, error=str(e)
                )
                success_message = f"⚠️ Таймфрейм {timeframe} включен\n❌ Ошибка загрузки данных: {str(e)[:50]}"

        else:  # Таймфрейм выключен
            success_message = f"❌ Таймфрейм {timeframe} отключен"

        # Обновляем состояние с новым объектом
        await state.update_data(user_pair=user_pair)

        # Обновляем клавиатуру
        management_text = create_pair_management_message(user_pair)
        management_keyboard = create_pair_management_keyboard(user_pair)

        await callback.message.edit_text(
            management_text, reply_markup=management_keyboard
        )

        await callback.answer(success_message)

        log_user_action(
            user_id,
            "timeframe_toggled",
            timeframe=timeframe,
            new_state=new_state,
            pair_symbol=user_pair.pair.symbol,
        )

    except Exception as e:
        logger.error("Error toggling timeframe", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


@my_pairs_router.callback_query(F.data.startswith("view_rsi_"))
async def handle_rsi_view(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Просмотр RSI для пары с автоматической загрузкой исторических данных.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары из callback_data
        pair_id = int(callback.data.split("_")[-1])

        # Получаем информацию о паре
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Переходим к просмотру RSI
        await state.set_state(MyPairsStates.viewing_rsi)

        # Проверяем наличие исторических данных
        from data.models.candle_model import Candle

        # Проверяем есть ли хотя бы 15 свечей для RSI
        has_sufficient_data = False
        for timeframe in user_pair.get_enabled_timeframes():
            candle_count = await Candle.count_candles(session, pair_id, timeframe)
            if candle_count >= 15:  # Минимум для RSI
                has_sufficient_data = True
                break

        if not has_sufficient_data:
            # Показываем сообщение загрузки исторических данных
            await safe_edit_message(
                callback.message,
                (
                    f"📥 <b>Загрузка исторических данных</b>\n\n"
                    f"Пара: {user_pair.pair.display_name}\n\n"
                    f"⏳ Загружаем данные с Binance для расчета RSI...\n"
                    f"Это может занять 10-30 секунд."
                ),
                reply_markup=get_back_to_management_keyboard(pair_id),
            )

            # Загружаем исторические данные
            from services.data_fetchers.historical.historical_fetcher import (
                HistoricalDataFetcher,
            )
            from config.bot_config import get_bot_config

            config = get_bot_config()
            try:
                async with HistoricalDataFetcher() as fetcher:
                    historical_candles = await fetcher.fetch_pair_historical_data(
                        session=session,
                        pair_id=pair_id,
                        symbol=user_pair.pair.symbol,
                        timeframes=user_pair.get_enabled_timeframes(),
                        limit=500,  # Загружаем 500 свечей
                    )

                logger.info(
                    "Historical data loaded for RSI",
                    pair_symbol=user_pair.pair.symbol,
                    candles_loaded=historical_candles,
                )

                if historical_candles == 0:
                    # Не удалось загрузить данные
                    error_text = f"""❌ <b>Не удалось загрузить данные</b>

Пара: {user_pair.pair.display_name}

<b>Возможные причины:</b>
• Проблемы с подключением к Binance API
• Временные технические неполадки
• Неверный символ пары

<b>Что делать:</b>
• Попробуйте через несколько минут
• Проверьте интернет-соединение
• Обратитесь к администратору"""

                    await safe_edit_message(
                        callback.message,
                        error_text,
                        reply_markup=get_back_to_management_keyboard(pair_id),
                    )
                    return

            except Exception as e:
                logger.error("Error loading historical data for RSI", error=str(e))

                error_text = f"""❌ <b>Ошибка загрузки данных</b>

Пара: {user_pair.pair.display_name}

Произошла ошибка при загрузке исторических данных: {str(e)[:100]}

Попробуйте позже или обратитесь к администратору."""

                await safe_edit_message(
                    callback.message,
                    error_text,
                    reply_markup=get_back_to_management_keyboard(pair_id),
                )
                return

        # Показываем индикатор расчета RSI
        await safe_edit_message(
            callback.message,
            (
                f"🔢 <b>Расчет RSI</b>\n\n"
                f"Пара: {user_pair.pair.display_name}\n\n"
                f"⏳ Рассчитываем индикаторы..."
            ),
            reply_markup=get_back_to_management_keyboard(pair_id),
        )

        # Рассчитываем RSI для активных таймфреймов
        rsi_data = await calculate_rsi_for_pair(session, user_pair)

        # Проверяем есть ли валидные данные RSI
        has_valid_rsi = any(
            "error" not in data and data.get("value") is not None
            for data in rsi_data.values()
        )

        if not has_valid_rsi:
            # Всё ещё нет данных для RSI
            error_text = f"""⚠️ <b>RSI пока недоступен</b>

Пара: {user_pair.pair.display_name}

Данные загружены, но для расчета RSI нужно больше свечей.

<b>Попробуйте:</b>
• Подождать 5-10 минут
• Нажать "🔄 Обновить данные" ещё раз
• Проверить активные таймфреймы"""

            await safe_edit_message(
                callback.message,
                error_text,
                reply_markup=create_rsi_display_keyboard(pair_id),
            )
            return

        # Создаем сообщение с RSI данными
        rsi_text = create_rsi_display_message(user_pair, rsi_data)
        rsi_keyboard = create_rsi_display_keyboard(pair_id)

        await safe_edit_message(
            callback.message,
            rsi_text,
            reply_markup=rsi_keyboard,
        )

        await callback.answer()
        log_user_action(user_id, "rsi_viewed", pair_symbol=user_pair.pair.symbol)

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error viewing RSI", user_id=user_id, error=str(e))

        error_text = create_rsi_error_message()
        await safe_edit_message(
            callback.message,
            error_text,
            reply_markup=get_back_to_management_keyboard(pair_id),
        )


@my_pairs_router.callback_query(F.data.startswith("back_to_management_"))
async def handle_back_to_management(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Вернуться к управлению парой.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары
        pair_id = int(callback.data.split("_")[-1])

        # Получаем пару
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Возвращаемся к управлению
        await state.set_state(MyPairsStates.managing_timeframes)
        await state.update_data(pair_id=pair_id, user_pair=user_pair)

        management_text = create_pair_management_message(user_pair)
        management_keyboard = create_pair_management_keyboard(user_pair)

        await callback.message.edit_text(
            management_text, reply_markup=management_keyboard
        )

        await callback.answer()

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error returning to management", user_id=user_id, error=str(e))
        await callback.answer("Произошла ошибка", show_alert=True)


def register_my_pairs_handlers(dp):
    """
    Зарегистрировать обработчики просмотра пар.

    Args:
        dp: Диспетчер aiogram
    """
    dp.include_router(my_pairs_router)


@my_pairs_router.callback_query(F.data.startswith("rsi_current_"))
async def handle_rsi_current_view(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Показать текущие значения RSI из кеша для быстрого просмотра.

    Args:
        callback: Callback query с данными "rsi_current:SYMBOL"
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары из callback data
        pair_id = int(callback.data.split("_")[-1])

        # Получаем информацию о паре
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        logger.info(
            "Showing current RSI values", user_id=user_id, symbol=user_pair.pair.symbol
        )

        # Получаем значения RSI из кеша для активных таймфреймов
        rsi_values = {}
        enabled_timeframes = user_pair.get_enabled_timeframes()

        for timeframe in enabled_timeframes:
            try:
                # Пока кеш не работает, возвращаем None
                rsi_value = None
                if rsi_value is not None:
                    rsi_values[timeframe] = rsi_value
            except Exception as e:
                logger.error(
                    "Error getting RSI value from cache",
                    symbol=user_pair.pair.symbol,
                    timeframe=timeframe,
                    error=str(e),
                )

        # Форматируем сообщение используя новый форматтер
        from services.notifications.message_formatter import MessageFormatter

        formatter = MessageFormatter()
        message_text = formatter.format_rsi_current_values(
            user_pair.pair.symbol, rsi_values
        )

        # Создаем клавиатуру с кнопками обновления и возврата
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()

        builder.row(
            InlineKeyboardButton(
                text="🔄 Обновить", callback_data=f"rsi_current_{pair_id}"
            )
        )

        builder.row(
            InlineKeyboardButton(
                text="📊 Полный RSI", callback_data=f"view_rsi_{pair_id}"
            )
        )

        builder.row(
            InlineKeyboardButton(
                text="⚙️ Управление парой", callback_data=f"back_to_management_{pair_id}"
            )
        )

        builder.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        )

        keyboard = builder.as_markup()

        # Отправляем сообщение
        await callback.message.edit_text(
            text=message_text, reply_markup=keyboard, parse_mode="HTML"
        )

        await callback.answer()

        log_user_action(
            user_id, "rsi_current_viewed", pair_symbol=user_pair.pair.symbol
        )

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error showing current RSI values", user_id=user_id, error=str(e))

        await callback.answer(
            text="❌ Ошибка при получении данных RSI", show_alert=True
        )


@my_pairs_router.callback_query(F.data.startswith("refresh_rsi_"))
async def handle_refresh_rsi(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
):
    """
    Принудительно обновить RSI данные.

    Args:
        callback: Callback query
        session: Сессия базы данных
        state: Состояние FSM
    """
    user_id = callback.from_user.id

    try:
        # Извлекаем ID пары
        pair_id = int(callback.data.split("_")[-1])

        # Получаем пару
        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair_id)

        if not user_pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return

        # Показываем индикатор загрузки
        await callback.message.edit_text(
            f"🔄 <b>Обновление RSI</b>\n\n"
            f"Пара: {user_pair.pair.display_name}\n\n"
            f"⏳ Пересчитываем индикаторы...",
            reply_markup=get_back_to_management_keyboard(pair_id),
        )

        # Принудительно очищаем кеш индикаторов для этой пары
        await indicator_cache.invalidate_indicators(user_pair.pair.symbol)

        # Пересчитываем RSI
        rsi_data = await calculate_rsi_for_pair(session, user_pair)

        # Показываем обновленные данные
        rsi_text = create_rsi_display_message(user_pair, rsi_data)
        rsi_keyboard = create_rsi_display_keyboard(pair_id)

        await callback.message.edit_text(rsi_text, reply_markup=rsi_keyboard)

        await callback.answer("✅ RSI обновлен")
        log_user_action(user_id, "rsi_refreshed", pair_symbol=user_pair.pair.symbol)

    except ValueError:
        await callback.answer("Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error("Error refreshing RSI", user_id=user_id, error=str(e))
        await callback.answer("❌ Ошибка при обновлении RSI", show_alert=True)
