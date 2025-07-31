"""
Быстрая проверка БД
"""
import asyncio
from sqlalchemy import text
from data.database import get_session, init_database

async def quick_check():
    await init_database()

    async with get_session() as session:
        # Проверяем свечи
        result = await session.execute(text("SELECT COUNT(*) FROM candles"))
        candles = result.scalar()
        print(f"✅ Свечей в БД: {candles}")

        # Проверяем пары
        result = await session.execute(text("SELECT COUNT(*) FROM pairs"))
        pairs = result.scalar()
        print(f"✅ Пар в БД: {pairs}")

        # Показываем пары (убираем display_name)
        if pairs > 0:
            result = await session.execute(text("SELECT symbol FROM pairs"))
            print("\nПары:")
            for row in result:
                print(f"  📈 {row.symbol}")

        # Проверяем по таймфреймам
        result = await session.execute(text("""
            SELECT timeframe, COUNT(*) as count 
            FROM candles 
            GROUP BY timeframe 
            ORDER BY count DESC
        """))

        print("\nСвечи по таймфреймам:")
        for row in result:
            print(f"  ⏰ {row.timeframe}: {row.count} свечей")

        # Проверяем для BTC на 1m
        result = await session.execute(text("""
            SELECT COUNT(*) as count 
            FROM candles c
            JOIN pairs p ON c.pair_id = p.id 
            WHERE p.symbol = 'BTCUSDT' AND c.timeframe = '1m'
        """))

        btc_1m_count = result.scalar()
        print(f"\n🔍 BTC 1m свечей: {btc_1m_count}")

        if btc_1m_count >= 15:
            print("✅ Достаточно данных для RSI расчета!")
        else:
            print("❌ Недостаточно данных для RSI")

if __name__ == "__main__":
    asyncio.run(quick_check())