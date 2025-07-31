"""
Скрипт для проверки данных свечей в базе данных
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from sqlalchemy import text
from data.database import get_session, init_database

async def check_candles_data():
    """Проверить количество свечей в БД по парам и таймфреймам"""
    await init_database()

    async with get_session() as session:
        # Проверяем общее количество свечей
        result = await session.execute(text("SELECT COUNT(*) FROM candles"))
        total_candles = result.scalar()
        print(f"✅ Всего свечей в БД: {total_candles}")

        if total_candles == 0:
            print("❌ КРИТИЧНО: В БД нет свечей!")
            return

        # Сначала проверим структуру таблицы pairs
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'pairs'
            ORDER BY ordinal_position
        """))

        print("\nКолонки в таблице pairs:")
        columns = []
        for row in result:
            columns.append(row.column_name)
            print(f"  - {row.column_name} ({row.data_type})")

        # Используем правильные названия колонок
        if 'name' in columns:
            name_column = 'p.name'
        elif 'display_name' in columns:
            name_column = 'p.display_name'
        else:
            name_column = 'p.symbol'  # fallback

        # Проверяем по парам
        result = await session.execute(text(f"""
            SELECT p.symbol, {name_column} as name, COUNT(c.id) as candle_count
            FROM pairs p 
            LEFT JOIN candles c ON p.id = c.pair_id 
            GROUP BY p.id, p.symbol, {name_column}
            ORDER BY candle_count DESC
        """))

        print("\nСвечи по парам:")
        for row in result:
            print(f"  📊 {row.symbol} ({row.name}): {row.candle_count} свечей")

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

        # Проверяем последние свечи
        result = await session.execute(text("""
            SELECT p.symbol, c.timeframe, c.close_price, c.open_time
            FROM candles c 
            JOIN pairs p ON c.pair_id = p.id 
            ORDER BY c.open_time DESC 
            LIMIT 5
        """))

        print("\nПоследние 5 свечей:")
        for row in result:
            print(f"  🕐 {row.symbol} {row.timeframe}: ${row.close_price} (время: {row.open_time})")

if __name__ == "__main__":
    asyncio.run(check_candles_data())