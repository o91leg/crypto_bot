"""
Принудительная загрузка исторических данных для всех пар
"""
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.database import async_session_factory
from data.models.pair_model import Pair
from services.data_fetchers.historical.historical_fetcher import HistoricalDataFetcher
from utils.logger import get_logger

logger = get_logger(__name__)


async def force_load_all_pairs():
    """Принудительно загрузить данные для всех пар"""
    async with async_session_factory() as session:
        # Получаем все пары
        try:
            pairs = await Pair.get_all_pairs(session)
            print(f"Найдено пар: {len(pairs)}")
        except Exception as e:
            print(f"Ошибка получения пар: {e}")
            # Альтернативный способ
            from sqlalchemy import select
            result = await session.execute(select(Pair))
            pairs = result.scalars().all()
            print(f"Найдено пар (альтернативно): {len(pairs)}")

        if not pairs:
            print("❌ В БД нет пар для загрузки!")
            return

        # Загружаем данные для каждой пары
        async with HistoricalDataFetcher() as fetcher:
            for pair in pairs:
                print(f"\n📥 Загружаем данные для {pair.symbol}...")

                try:
                    candles_loaded = await fetcher.fetch_pair_historical_data(
                        session=session,
                        pair_id=pair.id,
                        symbol=pair.symbol,
                        timeframes=['1m', '5m', '15m', '1h', '2h', '4h', '1d', '1w'],
                        limit=500
                    )

                    print(f"✅ {pair.symbol}: загружено {candles_loaded} свечей")
                    await session.commit()

                except Exception as e:
                    print(f"❌ {pair.symbol}: ошибка - {str(e)}")
                    await session.rollback()

        print("\n🎉 Загрузка завершена!")


if __name__ == "__main__":
    asyncio.run(force_load_all_pairs())