import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from data.database import get_session, init_database
from data.models.candle_model import Candle
from sqlalchemy import text

async def cleanup_invalid_candles():
    await init_database()  # добавь эту строку
    async with get_session() as session:

        # Найти записи с проблемными значениями
        result = await session.execute(
            text("SELECT id, volume, quote_volume FROM candles WHERE volume > 9999999999 OR quote_volume > 9999999999")
        )
        
        invalid_records = result.fetchall()
        print(f"Found {len(invalid_records)} invalid records")
        
        for record in invalid_records:
            # Обновить с ограниченными значениями
            await session.execute(
                text("UPDATE candles SET volume = LEAST(volume, 9999999999.99999999), quote_volume = LEAST(quote_volume, 9999999999.99999999) WHERE id = :id"),
                {"id": record.id}
            )
        
        await session.commit()
        print("Invalid records cleaned up")

if __name__ == "__main__":
    asyncio.run(cleanup_invalid_candles())
