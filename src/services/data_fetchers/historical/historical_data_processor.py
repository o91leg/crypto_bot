"""
Путь: src/services/data_fetchers/historical/historical_data_processor.py
Описание: Обработчик данных для сохранения исторических свечей в БД
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from typing import List, Dict, Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from decimal import Decimal, InvalidOperation

from data.models.candle_model import Candle
from utils.validators import validate_binance_kline_data, validate_binance_kline_data_detailed
from utils.logger import LoggerMixin

# Настройка логирования
logger = structlog.get_logger(__name__)


def validate_numeric_field(value: str, field_name: str, max_digits: int = 24) -> Decimal:
    """Валидировать числовое поле перед сохранением в БД."""
    try:
        decimal_value = Decimal(value)
        max_value = Decimal('9999999999999999.99999999')
        if decimal_value > max_value:
            logger.warning(
                "Value exceeds maximum, capping",
                field_name=field_name,
                original_value=str(decimal_value),
                capped_value=str(max_value)
            )
            return max_value
        if decimal_value < 0:
            logger.warning(
                "Negative value, setting to zero",
                field_name=field_name,
                value=str(decimal_value)
            )
            return Decimal('0')
        return decimal_value
    except (ValueError, InvalidOperation):
        logger.error("Invalid decimal value", field_name=field_name, value=value)
        return Decimal('0')


class HistoricalDataProcessor(LoggerMixin):
    """
    Обработчик данных для сохранения исторических свечей в базу данных.

    Отвечает за:
    - Парсинг kline данных от Binance
    - Валидацию данных перед сохранением
    - Пакетное сохранение свечей в БД
    - Обработку дубликатов
    """

    def __init__(self):
        """Инициализация обработчика данных."""
        self.total_processed = 0
        self.total_saved = 0
        self.total_skipped = 0

        self.logger.info("HistoricalDataProcessor initialized")

    async def save_candle_safely(self, session: AsyncSession, candle: Candle) -> bool:
        """Безопасно сохранить свечу с обработкой ошибок."""
        try:
            session.add(candle)
            await session.flush()
            return True
        except Exception as e:
            self.logger.error(
                "Error saving candle, rolling back",
                error=str(e),
                pair_id=candle.pair_id,
                timeframe=candle.timeframe,
                open_time=candle.open_time,
            )
            await session.rollback()
            return False

    async def save_candles_to_db(
            self,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            klines: List[List]
    ) -> int:
        """
        Сохранить свечи в базу данных.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм
            klines: Список kline данных от Binance

        Returns:
            int: Количество сохраненных свечей
        """
        if not klines:
            return 0

        saved_count = 0

        for kline in klines:
            try:
                self.total_processed += 1

                # Преобразуем kline в формат словаря
                kline_dict = self._parse_kline_data(kline)

                # Простая валидация основных полей
                if not kline_dict.get('t') or not kline_dict.get('c'):
                    self.logger.warning("Missing basic kline fields", kline=kline)
                    self.total_skipped += 1
                    continue

                # Собираем объект свечи и сохраняем безопасно
                candle = Candle(
                    pair_id=pair_id,
                    timeframe=timeframe,
                    open_time=int(kline_dict["t"]),
                    close_time=int(kline_dict["T"]),
                    open_price=Decimal(str(kline_dict["o"])),
                    high_price=Decimal(str(kline_dict["h"])),
                    low_price=Decimal(str(kline_dict["l"])),
                    close_price=Decimal(str(kline_dict["c"])),
                    volume=Decimal(str(kline_dict["v"])),
                    quote_volume=Decimal(str(kline_dict["q"])),
                    trades_count=int(kline_dict["n"]),
                    is_closed=bool(kline_dict["x"]),
                )

                if await self.save_candle_safely(session, candle):
                    saved_count += 1
                    self.total_saved += 1
                else:
                    self.total_skipped += 1

            except Exception as e:
                # Скорее всего дублирующая запись - игнорируем
                if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
                    self.logger.debug(
                        "Duplicate candle skipped",
                        pair_id=pair_id,
                        timeframe=timeframe,
                        open_time=kline[0] if kline else None
                    )
                    self.total_skipped += 1
                else:
                    self.logger.error(
                        "Error saving candle",
                        pair_id=pair_id,
                        timeframe=timeframe,
                        error=str(e),
                        kline=kline
                    )
                    self.total_skipped += 1

        # Коммитим изменения пакетом
        try:
            await session.commit()

            self.logger.debug(
                "Candles batch saved",
                pair_id=pair_id,
                timeframe=timeframe,
                total_klines=len(klines),
                saved_count=saved_count,
                skipped_count=len(klines) - saved_count
            )

        except Exception as e:
            self.logger.error("Error committing candles to database", error=str(e))
            await session.rollback()
            return 0

        return saved_count

    def _parse_kline_data(self, kline: List) -> Dict[str, Any]:
        """
        Парсить kline данные от Binance в словарь.

        Args:
            kline: Список kline данных

        Returns:
            Dict[str, Any]: Словарь с kline данными
        """
        # Формат kline от Binance:
        # [
        #   0: open_time,
        #   1: open_price,
        #   2: high_price,
        #   3: low_price,
        #   4: close_price,
        #   5: volume,
        #   6: close_time,
        #   7: quote_asset_volume,
        #   8: number_of_trades,
        #   9: taker_buy_base_asset_volume,
        #   10: taker_buy_quote_asset_volume,
        #   11: ignore
        # ]

        try:
            return {
                "t": int(kline[0]),  # open_time
                "T": int(kline[6]),  # close_time
                "s": "",  # symbol (не используется в этом контексте)
                "i": "",  # interval (не используется в этом контексте)
                "o": str(kline[1]),  # open_price
                "h": str(kline[2]),  # high_price
                "l": str(kline[3]),  # low_price
                "c": str(kline[4]),  # close_price
                "v": str(kline[5]),  # volume
                "q": str(kline[7]),  # quote_asset_volume
                "n": int(kline[8]),  # number_of_trades
                "V": str(kline[9]),  # taker_buy_base_asset_volume
                "Q": str(kline[10]),  # taker_buy_quote_asset_volume
                "x": True  # kline is closed (historical data)
            }
        except (IndexError, ValueError, TypeError) as e:
            self.logger.error("Error parsing kline data", kline=kline, error=str(e))
            raise ValueError(f"Invalid kline format: {str(e)}")

    async def bulk_save_candles(
            self,
            session: AsyncSession,
            pair_id: int,
            timeframe: str,
            klines: List[List],
            batch_size: int = 100
    ) -> int:
        """
        Пакетное сохранение свечей с оптимизацией.

        Args:
            session: Сессия базы данных
            pair_id: ID торговой пары
            timeframe: Таймфрейм
            klines: Список kline данных
            batch_size: Размер пакета для сохранения

        Returns:
            int: Количество сохраненных свечей
        """
        if not klines:
            return 0

        total_saved = 0

        # Разделяем на пакеты
        for i in range(0, len(klines), batch_size):
            batch = klines[i:i + batch_size]

            try:
                saved_count = await self.save_candles_to_db(
                    session=session,
                    pair_id=pair_id,
                    timeframe=timeframe,
                    klines=batch
                )

                total_saved += saved_count

                self.logger.debug(
                    "Batch processed",
                    batch_number=i // batch_size + 1,
                    batch_size=len(batch),
                    saved=saved_count
                )

            except Exception as e:
                self.logger.error(
                    "Error processing batch",
                    batch_number=i // batch_size + 1,
                    error=str(e)
                )
                # Продолжаем с следующим пакетом
                continue

        return total_saved

    def validate_kline_format(self, kline: List) -> bool:
        """
        Валидировать формат kline данных.

        Args:
            kline: Kline данные

        Returns:
            bool: True если формат корректен
        """
        try:
            # Проверяем что это список с нужным количеством элементов
            if not isinstance(kline, list) or len(kline) < 11:
                return False

            # Проверяем основные поля
            int(kline[0])  # open_time
            float(kline[1])  # open_price
            float(kline[2])  # high_price
            float(kline[3])  # low_price
            float(kline[4])  # close_price
            float(kline[5])  # volume
            int(kline[6])  # close_time
            float(kline[7])  # quote_volume
            int(kline[8])  # trades_count

            return True

        except (ValueError, TypeError, IndexError):
            return False

    def get_statistics(self) -> Dict[str, int]:
        """
        Получить статистику обработки.

        Returns:
            Dict[str, int]: Статистика обработки
        """
        return {
            "total_processed": self.total_processed,
            "total_saved": self.total_saved,
            "total_skipped": self.total_skipped,
            "success_rate": (
                self.total_saved / self.total_processed * 100
                if self.total_processed > 0 else 0
            )
        }

    def reset_statistics(self) -> None:
        """Сбросить статистику обработки."""
        self.total_processed = 0
        self.total_saved = 0
        self.total_skipped = 0