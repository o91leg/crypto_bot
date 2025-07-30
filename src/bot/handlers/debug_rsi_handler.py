"""
Путь: src/bot/handlers/debug_rsi_handler.py
Описание: Обработчик команд отладки RSI
Автор: Crypto Bot Team
Дата создания: 2025-07-30
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from utils.rsi_debug import debug_rsi_calculation
from services.indicators.rsi_calculator import RSICalculator
from data.models.candle_model import Candle
from utils.logger import get_logger

debug_router = Router()
logger = get_logger(__name__)

@debug_router.message(Command("debug_rsi"))
async def handle_debug_rsi(message: Message, session: AsyncSession):
    """
    Отладочная команда для проверки расчета RSI.
    Формат: /debug_rsi BTCUSDT 1h
    """
    user_id = message.from_user.id
    
    # Только для админов (замените на ваш ID)
    if user_id != 198024201:  # Ваш Telegram ID
        await message.reply("❌ Команда доступна только администратору")
        return
    
    try:
        # Парсим аргументы
        args = message.text.split()
        if len(args) != 3:
            await message.reply("Формат: /debug_rsi BTCUSDT 1h")
            return
            
        symbol = args[1].upper()
        timeframe = args[2]
        
        # Получаем пару
        from data.models.pair_model import Pair
        pair = await Pair.get_by_symbol(session, symbol)
        if not pair:
            await message.reply(f"❌ Пара {symbol} не найдена")
            return
        
        # Получаем последние 50 свечей
        candles = await Candle.get_latest_candles(
            session=session,
            pair_id=pair.id,
            timeframe=timeframe,
            limit=50
        )
        
        if len(candles) < 15:
            await message.reply(f"❌ Недостаточно данных: {len(candles)} свечей")
            return
        
        # Извлекаем цены
        prices = [float(candle.close_price) for candle in candles]
        
        # Отладка расчета
        debug_info = debug_rsi_calculation(prices, 14)
        
        # Рассчитываем RSI нашим калькулятором
        rsi_calc = RSICalculator()
        rsi_result = rsi_calc.calculate_standard_rsi(prices, 14)
        
        # Формируем ответ
        response = f"""🔍 <b>Отладка RSI для {symbol} ({timeframe})</b>

<b>Данные:</b>
- Свечей загружено: {len(candles)}
- Цены для расчета: {len(prices)}

<b>Последние 5 цен:</b>
{' → '.join([str(round(p, 2)) for p in prices[-5:]])}

<b>Расчет:</b>
- Средняя прибыль: {debug_info.get('avg_gain', 'N/A')}
- Средний убыток: {debug_info.get('avg_loss', 'N/A')}
- RS: {debug_info.get('rs', 'N/A')}

<b>Результат:</b>
- Наш RSI: {rsi_result.value if rsi_result else 'Ошибка расчета'}
- Отладочный RSI: {debug_info.get('rsi', 'N/A')}

<i>Сравните с TradingView для проверки точности</i>"""

        await message.reply(response)
        
    except Exception as e:
        logger.error("Error in debug RSI", error=str(e), user_id=user_id)
        await message.reply(f"❌ Ошибка: {str(e)}")


def register_debug_handlers(dp):
    """Зарегистрировать обработчики отладки"""
    dp.include_router(debug_router)
