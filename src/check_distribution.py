"""
Проверка распределения данных по парам и таймфреймам
"""
import asyncio
from sqlalchemy import text
from data.database import get_session, init_database


async def check_distribution():
    await init_database()

    async with get_session() as session:
        # Детальная проверка по парам и таймфреймам
        result = await session.execute(text("""
            SELECT p.symbol, c.timeframe, COUNT(*) as count
            FROM pairs p 
            JOIN candles c ON p.id = c.pair_id 
            GROUP BY p.symbol, c.timeframe 
            ORDER BY p.symbol, c.timeframe
        """))

        print("📊 Распределение свечей по парам и таймфреймам:")
        current_pair = None

        for row in result:
            if current_pair != row.symbol:
                print(f"\n📈 {row.symbol}:")
                current_pair = row.symbol

            status = "✅" if row.count >= 15 else "❌"
            print(f"  {status} {row.timeframe}: {row.count} свечей")


if __name__ == "__main__":
    asyncio.run(check_distribution())