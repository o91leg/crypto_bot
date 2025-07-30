"""
Скрипт для проверки данных свечей в базе данных
"""
import asyncio
from sqlalchemy import text
from data.database import get_async_session


async def check_candles_data():
    """Проверить количество свечей в БД по парам и таймфреймам"""
    async with get_async_session() as session:
        # Проверяем общее количество свечей
        result = await session.execute(text("SELECT COUNT(*) FROM candles"))
        total_candles = result.scalar()
        print(f"Всего свечей в БД: {total_candles}")

        if total_candles == 0:
            print("❌ КРИТИЧНО: В БД нет свечей!")
            return

        # Проверяем по парам
        result = await session.execute(text("""
            SELECT p.symbol, p.display_name, COUNT(c.id) as candle_count
            FROM pairs p 
            LEFT JOIN candles c ON p.id = c.pair_id 
            GROUP BY p.id, p.symbol, p.display_name
            ORDER BY candle_count DESC
        """))

        print("\nСвечи по парам:")
        for row in result:
            print(f"  {row.symbol} ({row.display_name}): {row.candle_count} свечей")

        # Проверяем по таймфреймам
        result = await session.execute(text("""
            SELECT timeframe, COUNT(*) as count 
            FROM candles 
            GROUP BY timeframe 
            ORDER BY count DESC
        """))

        print("\nСвечи по таймфреймам:")
        for row in result:
            print(f"  {row.timeframe}: {row.count} свечей")


if __name__ == "__main__":
    asyncio.run(check_candles_data())
