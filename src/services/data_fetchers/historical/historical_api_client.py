"""
Путь: src/services/data_fetchers/historical/historical_api_client.py
Описание: API клиент для загрузки исторических данных с Binance
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import structlog

from config.binance_config import get_binance_config
from utils.exceptions import BinanceAPIError, BinanceConnectionError, BinanceRateLimitError
from utils.logger import LoggerMixin

# Настройка логирования
logger = structlog.get_logger(__name__)


class HistoricalAPIClient(LoggerMixin):
    """
    API клиент для загрузки исторических данных с Binance.

    Отвечает за:
    - Выполнение HTTP запросов к Binance API
    - Обработку rate limits и ошибок API
    - Управление HTTP сессией
    """

    def __init__(self):
        """Инициализация API клиента."""
        self.config = get_binance_config()
        self.session: Optional[aiohttp.ClientSession] = None

        self.logger.info("HistoricalAPIClient initialized")

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        await self._close_session()

    async def _ensure_session(self) -> None:
        """Убедиться что HTTP сессия создана."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections_per_host
            )

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "CryptoBot/1.0",
                    "Accept": "application/json"
                }
            )

            self.logger.debug("HTTP session created")

    async def _close_session(self) -> None:
        """Закрыть HTTP сессию."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug("HTTP session closed")

    async def fetch_klines_batch(
            self,
            symbol: str,
            timeframe: str,
            start_time: int,
            end_time: int,
            limit: int
    ) -> List[List]:
        """
        Загрузить пакет kline данных от Binance API.

        Args:
            symbol: Символ торговой пары
            timeframe: Таймфрейм
            start_time: Начальное время
            end_time: Конечное время
            limit: Максимальное количество записей

        Returns:
            List[List]: Список kline данных
        """
        params = {
            "symbol": symbol.upper(),
            "interval": timeframe,
            "startTime": start_time,
            "endTime": end_time,
            "limit": min(limit, self.config.max_candles_per_request)
        }

        endpoint = "/api/v3/klines"

        try:
            data = await self._make_api_request(endpoint, params)

            self.logger.debug(
                "Klines batch fetched",
                symbol=symbol,
                timeframe=timeframe,
                records=len(data),
                start_time=start_time,
                end_time=end_time
            )

            return data

        except Exception as e:
            self.logger.error(
                "Failed to fetch klines batch",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise

    async def _make_api_request(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """
        Выполнить запрос к Binance API.

        Args:
            endpoint: API endpoint
            params: Параметры запроса

        Returns:
            Any: Ответ от API

        Raises:
            BinanceAPIError: При ошибке API
            BinanceConnectionError: При ошибке соединения
            BinanceRateLimitError: При превышении лимитов
        """
        await self._ensure_session()

        url = self.config.rest_api_url + endpoint
        max_retries = self.config.max_retries
        retry_delay = self.config.retry_delay

        for attempt in range(max_retries + 1):
            try:
                async with self.session.get(url, params=params) as response:
                    # Проверяем статус ответа
                    if response.status == 200:
                        data = await response.json()
                        return data

                    elif response.status == 429:  # Rate limit
                        retry_after = int(response.headers.get("Retry-After", 60))
                        raise BinanceRateLimitError(
                            "Rate limit exceeded",
                            details={"retry_after": retry_after}
                        )

                    elif response.status >= 400:
                        error_data = await response.json()
                        raise BinanceAPIError(
                            f"API error: {error_data.get('msg', 'Unknown error')}",
                            status_code=response.status,
                            details=error_data
                        )

            except aiohttp.ClientError as e:
                if attempt < max_retries:
                    self.logger.warning(
                        "Connection error, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e)
                    )
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    raise BinanceConnectionError(f"Connection failed after {max_retries} retries: {str(e)}")

            except BinanceRateLimitError:
                # Перебрасываем rate limit ошибки без повторов
                raise

            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(
                        "Unexpected error, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e)
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    raise BinanceAPIError(f"Unexpected API error: {str(e)}")

        # Этот код не должен выполняться, но на всякий случай
        raise BinanceAPIError("Maximum retries exceeded")

    async def test_connection(self) -> bool:
        """
        Проверить соединение с API.

        Returns:
            bool: True если соединение работает
        """
        try:
            await self._make_api_request("/api/v3/ping")
            self.logger.info("API connection test successful")
            return True
        except Exception as e:
            self.logger.error("API connection test failed", error=str(e))
            return False

    async def get_server_time(self) -> int:
        """
        Получить время сервера Binance.

        Returns:
            int: Время сервера в миллисекундах
        """
        try:
            response = await self._make_api_request("/api/v3/time")
            return response["serverTime"]
        except Exception as e:
            self.logger.error("Failed to get server time", error=str(e))
            raise

    async def get_exchange_info(self, symbol: str = None) -> Dict[str, Any]:
        """
        Получить информацию о бирже.

        Args:
            symbol: Символ пары (опционально)

        Returns:
            Dict[str, Any]: Информация о бирже
        """
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol.upper()

            response = await self._make_api_request("/api/v3/exchangeInfo", params)
            return response
        except Exception as e:
            self.logger.error("Failed to get exchange info", error=str(e))
            raise