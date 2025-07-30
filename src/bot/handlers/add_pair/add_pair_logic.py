"""
Путь: src/bot/handlers/add_pair/add_pair_logic.py
Описание: Бизнес-логика для добавления торговых пар
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from data.models.pair_model import Pair
from data.models.user_pair_model import UserPair
from services.data_fetchers.pair_validator import PairValidator
from services.data_fetchers.historical.historical_fetcher import HistoricalDataFetcher
from utils.validators import extract_base_quote_assets, sanitize_user_input
from config.bot_config import get_bot_config

# Настройка логирования
logger = structlog.get_logger(__name__)


async def process_symbol_input(session: AsyncSession, symbol_input: str, user_id: int) -> dict:
    """
    Обработать ввод символа и валидировать торговую пару.

    Args:
        session: Сессия базы данных
        symbol_input: Введенный символ
        user_id: ID пользователя

    Returns:
        dict: Результат обработки символа
    """
    try:
        # Очищаем ввод
        symbol_input = sanitize_user_input(symbol_input, 20)

        # Создаем экземпляр валидатора и используем контекстный менеджер
        async with PairValidator() as validator:
            # Пытаемся определить полный символ
            possible_symbols = []

            # Если введен полный символ (например, BTCUSDT)
            if len(symbol_input) >= 6:
                pair_info = await validator.validate_pair(symbol_input.upper())
                if pair_info:
                    possible_symbols.append(symbol_input.upper())

            # Если введена только базовая валюта (например, BTC)
            if len(symbol_input) <= 10:
                # Пробуем популярные котируемые валюты
                for quote in ["USDT", "BTC", "ETH", "BNB"]:
                    test_symbol = symbol_input.upper() + quote
                    pair_info = await validator.validate_pair(test_symbol)
                    if pair_info:
                        possible_symbols.append(test_symbol)

            if not possible_symbols:
                return {
                    "success": False,
                    "error": "invalid_format",
                    "message": f"Не удается определить торговую пару для '{symbol_input}'"
                }

            # Используем первый найденный валидный символ
            symbol = possible_symbols[0]

            # Проверяем, не добавлена ли уже эта пара пользователем
            existing_pair = await Pair.get_by_symbol(session, symbol)
            if existing_pair:
                # Проверяем связь с пользователем
                user_pair = await UserPair.get_by_user_and_pair(session, user_id, existing_pair.id)
                if user_pair:
                    return {
                        "success": False,
                        "error": "already_exists",
                        "message": f"Пара {symbol} уже добавлена в ваше отслеживание"
                    }

            # Получаем информацию о паре из Binance
            pair_info = await validator.validate_pair(symbol)
            if not pair_info:
                return {
                    "success": False,
                    "error": "not_found",
                    "message": f"Информация о паре {symbol} не найдена"
                }

            # Извлекаем базовую и котируемую валюты
            base_asset = pair_info.get("baseAsset", "")
            quote_asset = pair_info.get("quoteAsset", "")

            return {
                "success": True,
                "symbol": symbol,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "pair_info": pair_info,
                "display_name": f"{base_asset}/{quote_asset}",
                "is_new_pair": existing_pair is None
            }

    except Exception as e:
        logger.error("Error processing symbol input", symbol=symbol_input, user_id=user_id, error=str(e))
        return {
            "success": False,
            "error": "processing_error",
            "message": f"Ошибка при обработке символа '{symbol_input}'"
        }


async def execute_add_pair(session: AsyncSession, user_id: int, pair_data: dict) -> dict:
    """
    Выполнить добавление пары в отслеживание.

    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        pair_data: Данные о паре из состояния FSM

    Returns:
        dict: Результат выполнения
    """
    symbol = pair_data.get("symbol")
    base_asset = pair_data.get("base_asset")
    quote_asset = pair_data.get("quote_asset")
    is_new_pair = pair_data.get("is_new_pair", False)

    config = get_bot_config()

    try:
        # Получаем или создаем пару в БД
        if is_new_pair:
            # Создаем новую пару
            pair = await Pair.create_from_symbol(session, symbol)
            logger.info("New pair created in database", symbol=symbol, pair_id=pair.id)
        else:
            # Получаем существующую пару
            pair = await Pair.get_by_symbol(session, symbol)
            if not pair:
                return {
                    "success": False,
                    "error": "Торговая пара не найдена в базе данных"
                }

        # Создаем связь пользователь-пара с дефолтными таймфреймами
        user_pair = await UserPair.create_user_pair(
            session=session,
            user_id=user_id,
            pair_id=pair.id,
            timeframes={tf: True for tf in config.default_timeframes}
        )

        # Увеличиваем счетчик пользователей пары
        pair.increment_users_count()

        # Загружаем исторические данные если это новая пара
        historical_candles = 0
        if is_new_pair:
            try:
                async with HistoricalDataFetcher() as fetcher:
                    historical_candles = await fetcher.fetch_pair_historical_data(
                        session, pair.id, symbol, config.default_timeframes
                    )
                    logger.info(
                        "Historical data loaded",
                        symbol=symbol,
                        candles_count=historical_candles
                    )
            except Exception as e:
                # Не критичная ошибка - продолжаем без исторических данных
                logger.warning(
                    "Failed to load historical data",
                    symbol=symbol,
                    error=str(e)
                )

        # Коммитим изменения
        await session.commit()

        return {
            "success": True,
            "pair": pair,
            "user_pair": user_pair,
            "symbol": symbol,
            "display_name": f"{base_asset}/{quote_asset}",
            "timeframes": config.default_timeframes,
            "historical_candles": historical_candles,
            "is_new_pair": is_new_pair
        }

    except Exception as e:
        await session.rollback()
        logger.error("Error executing pair addition", symbol=symbol, user_id=user_id, error=str(e))

        return {
            "success": False,
            "error": f"Ошибка при добавлении пары: {str(e)}"
        }


def validate_symbol_format(symbol: str) -> tuple[bool, str]:
    """
    Валидировать формат символа торговой пары.

    Args:
        symbol: Символ для валидации

    Returns:
        tuple: (is_valid, error_message)
    """
    if not symbol or not isinstance(symbol, str):
        return False, "Символ должен быть строкой"

    symbol = symbol.strip().upper()

    if len(symbol) < 4:
        return False, "Символ слишком короткий (минимум 4 символа)"

    if len(symbol) > 20:
        return False, "Символ слишком длинный (максимум 20 символов)"

    if not symbol.isalnum():
        return False, "Символ должен содержать только буквы и цифры"

    return True, ""


async def check_pair_exists_for_user(session: AsyncSession, user_id: int, symbol: str) -> bool:
    """
    Проверить, добавлена ли уже пара для пользователя.

    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        symbol: Символ пары

    Returns:
        bool: True если пара уже добавлена
    """
    try:
        pair = await Pair.get_by_symbol(session, symbol)
        if not pair:
            return False

        user_pair = await UserPair.get_by_user_and_pair(session, user_id, pair.id)
        return user_pair is not None

    except Exception as e:
        logger.error("Error checking if pair exists for user", error=str(e))
        return False