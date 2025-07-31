"""
Исправление данных для BTC - загрузка недостающих таймфреймов
"""
import asyncio
from data.database import get_session, init_database
from data.models.pair_model import Pair
from services.data_fetchers.historical.historical_fetcher import HistoricalDataFetcher
from sqlalchemy import select


async def fix_btc_data():
    await init_database()

    async with get_session() as session:
        # Находим BTC пару
        result = await session.execute(select(Pair).where(Pair.symbol == 'BTCUSDT'))
        btc_pair = result.scalar_one_or_none()

        if not btc_pair:
            print("❌ BTC пара не найдена")
            return

        print(f"✅ Найдена пара: {btc_pair.symbol} (ID: {btc_pair.id})")

        # Недостающие таймфреймы для BTC
        missing_timeframes = ['5m', '15m', '1h', '2h', '4h', '1d', '1w']

        print(f"📥 Загружаем недостающие таймфреймы для BTC: {missing_timeframes}")

        try:
            async with HistoricalDataFetcher() as fetcher:
                candles_loaded = await fetcher.fetch_pair_historical_data(
                    session=session,
                    pair_id=btc_pair.id,
                    symbol='BTCUSDT',
                    timeframes=missing_timeframes,
                    limit=500
                )

                print(f"✅ BTCUSDT: загружено {candles_loaded} свечей")
                await session.commit()
                print("🎉 Данные для BTC загружены!")

        except Exception as e:
            print(f"❌ Ошибка загрузки BTC данных: {str(e)}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(fix_btc_data())