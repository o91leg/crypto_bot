"""
Тест расчета RSI
"""
import asyncio
from data.database import get_session, init_database
from data.models.pair_model import Pair
from data.models.candle_model import Candle
from services.indicators.rsi_calculator import RSICalculator
from sqlalchemy import select


async def test_rsi_calculation():
    await init_database()

    async with get_session() as session:
        # Получаем BTC пару
        result = await session.execute(select(Pair).where(Pair.symbol == 'BTCUSDT'))
        btc_pair = result.scalar_one_or_none()

        if not btc_pair:
            print("❌ BTC пара не найдена")
            return

        print(f"✅ Найдена пара: {btc_pair.symbol} (ID: {btc_pair.id})")

        # Получаем свечи для 1m
        result = await session.execute(
            select(Candle)
            .where(Candle.pair_id == btc_pair.id, Candle.timeframe == '1m')
            .order_by(Candle.open_time.asc())
            .limit(50)
        )
        candles = result.scalars().all()

        print(f"✅ Получено свечей: {len(candles)}")

        if len(candles) < 15:
            print("❌ Недостаточно свечей для RSI")
            return

        # Показываем последние цены
        prices = [float(candle.close_price) for candle in candles]
        print(f"📊 Последние 5 цен: {prices[-5:]}")

        # Рассчитываем RSI
        print("\n🔢 Тестируем RSI калькулятор...")

        try:
            rsi_calc = RSICalculator()
            rsi_result = rsi_calc.calculate_standard_rsi(prices, 14)

            if rsi_result:
                print(f"✅ RSI рассчитан: {rsi_result.value}")
                print(f"📈 Интерпретация: {rsi_result.interpretation}")
            else:
                print("❌ RSI не рассчитан (вернул None)")

        except Exception as e:
            print(f"❌ Ошибка расчета RSI: {str(e)}")
            import traceback
            traceback.print_exc()

        # Тестируем через модель
        print("\n🔢 Тестируем через Candle.get_latest_candles...")

        try:
            candles_via_model = await Candle.get_latest_candles(
                session=session,
                pair_id=btc_pair.id,
                timeframe='1m',
                limit=50
            )

            print(f"✅ Получено через модель: {len(candles_via_model)} свечей")

            if candles_via_model:
                model_prices = [float(c.close_price) for c in candles_via_model]
                print(f"📊 Цены через модель: {model_prices[-5:]}")

                rsi_result2 = rsi_calc.calculate_standard_rsi(model_prices, 14)
                if rsi_result2:
                    print(f"✅ RSI через модель: {rsi_result2.value}")
                else:
                    print("❌ RSI через модель не рассчитан")

        except Exception as e:
            print(f"❌ Ошибка получения через модель: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_rsi_calculation())