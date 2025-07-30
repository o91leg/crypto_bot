"""
Путь: src/services/data_fetchers/pair_validator.py
Описание: Валидатор торговых пар через Binance API
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

import asyncio
from typing import Optional, Dict, Any, List
import aiohttp
import structlog

from config.binance_config import get_binance_config
from utils.exceptions import BinanceAPIError, BinanceConnectionError, BinanceRateLimitError
from utils.validators import validate_trading_pair_symbol
from utils.logger import LoggerMixin

# Настройка логирования
logger = structlog.get_logger(__name__)


class PairValidator(LoggerMixin):
    """
    Валидатор торговых пар через Binance API.

    Отвечает за:
    - Проверку существования торговых пар на Binance
    - Получение информации о символах
    - Валидацию статуса торговли
    - Кеширование результатов валидации
    """

    def __init__(self):
        """Инициализация валидатора."""
        self.config = get_binance_config()
        self.session: Optional[aiohttp.ClientSession] = None

        # Кеш для информации о символах
        self._symbols_cache: Dict[str, Dict[str, Any]] = {}
        self._exchange_info_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 3600  # 1 час

        self.logger.info("PairValidator initialized")

    async def __aenter__(self):
        """Асинхронный вход в контекстный менеджер."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        await self._close_session()

    async def validate_pair(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Валидировать торговую пару через Binance API.

        Args:
            symbol: Символ торговой пары (например, BTCUSDT)

        Returns:
            Optional[Dict[str, Any]]: Информация о паре или None если не найдена
        """
        # Валидация формата символа
        is_valid, error_msg = validate_trading_pair_symbol(symbol)
        if not is_valid:
            self.logger.error("Invalid symbol format", symbol=symbol, error=error_msg)
            return None

        symbol = symbol.upper()

        # Проверяем кеш
        if symbol in self._symbols_cache:
            cached_info = self._symbols_cache[symbol]
            self.logger.debug("Symbol info retrieved from cache", symbol=symbol)
            return cached_info

        try:
            # Получаем информацию о паре
            pair_info = await self._get_symbol_info(symbol)

            if pair_info:
                # Кешируем результат
                self._symbols_cache[symbol] = pair_info

                self.logger.info(
                    "Pair validation successful",
                    symbol=symbol,
                    status=pair_info.get("status"),
                    base_asset=pair_info.get("baseAsset"),
                    quote_asset=pair_info.get("quoteAsset")
                )

                return pair_info
            else:
                self.logger.warning("Pair not found on Binance", symbol=symbol)
                return None

        except Exception as e:
            self.logger.error("Error validating pair", symbol=symbol, error=str(e))
            raise

    async def validate_multiple_pairs(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Валидировать несколько торговых пар одновременно.

        Args:
            symbols: Список символов торговых пар

        Returns:
            Dict[str, Optional[Dict[str, Any]]]: Результаты валидации для каждого символа
        """
        if not symbols:
            return {}

        self.logger.info("Validating multiple pairs", symbols_count=len(symbols))

        # Загружаем информацию о бирже если нужно
        await self._ensure_exchange_info()

        results = {}

        for symbol in symbols:
            try:
                result = await self.validate_pair(symbol)
                results[symbol] = result
            except Exception as e:
                self.logger.error("Error validating symbol", symbol=symbol, error=str(e))
                results[symbol] = None

        successful_validations = sum(1 for result in results.values() if result is not None)

        self.logger.info(
            "Multiple pairs validation completed",
            total=len(symbols),
            successful=successful_validations
        )

        return results

    async def get_trading_pairs_by_base_asset(self, base_asset: str) -> List[Dict[str, Any]]:
        """
        Получить все торговые пары для базовой валюты.

        Args:
            base_asset: Базовая валюта (например, BTC)

        Returns:
            List[Dict[str, Any]]: Список торговых пар
        """
        base_asset = base_asset.upper()

        self.logger.info("Getting trading pairs for base asset", base_asset=base_asset)

        try:
            # Загружаем информацию о всех символах
            await self._ensure_exchange_info()

            if not self._exchange_info_cache:
                return []

            matching_pairs = []

            for symbol_info in self._exchange_info_cache.get("symbols", []):
                if (symbol_info.get("baseAsset") == base_asset and
                        symbol_info.get("status") == "TRADING"):
                    matching_pairs.append(symbol_info)

            self.logger.info(
                "Found trading pairs for base asset",
                base_asset=base_asset,
                pairs_count=len(matching_pairs)
            )

            return matching_pairs

        except Exception as e:
            self.logger.error(
                "Error getting pairs for base asset",
                base_asset=base_asset,
                error=str(e)
            )
            return []

    async def get_popular_pairs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить популярные торговые пары.

        Args:
            limit: Максимальное количество пар

        Returns:
            List[Dict[str, Any]]: Список популярных пар
        """
        self.logger.info("Getting popular trading pairs", limit=limit)

        try:
            await self._ensure_exchange_info()

            if not self._exchange_info_cache:
                return []

            # Приоритет для USDT пар популярных криптовалют
            priority_bases = [
                "BTC", "ETH", "BNB", "ADA", "XRP", "SOL", "DOT", "LINK", "MATIC", "AVAX",
                "ATOM", "LTC", "BCH", "FIL", "ETC", "THETA", "VET", "TRX", "EOS", "NEO"
            ]

            popular_pairs = []

            # Сначала добавляем приоритетные USDT пары
            for base in priority_bases:
                symbol = f"{base}USDT"
                pair_info = await self._get_symbol_info_from_cache(symbol)

                if pair_info and pair_info.get("status") == "TRADING":
                    popular_pairs.append(pair_info)

                    if len(popular_pairs) >= limit:
                        break

            # Если нужно больше пар, добавляем другие USDT пары
            if len(popular_pairs) < limit:
                for symbol_info in self._exchange_info_cache.get("symbols", []):
                    if (symbol_info.get("quoteAsset") == "USDT" and
                            symbol_info.get("status") == "TRADING" and
                            symbol_info not in popular_pairs):

                        popular_pairs.append(symbol_info)

                        if len(popular_pairs) >= limit:
                            break

            self.logger.info("Popular pairs retrieved", count=len(popular_pairs))
            return popular_pairs[:limit]

        except Exception as e:
            self.logger.error("Error getting popular pairs", error=str(e))
            return []

    async def is_pair_tradable(self, symbol: str) -> bool:
        """
        Проверить, доступна ли пара для торговли.

        Args:
            symbol: Символ торговой пары

        Returns:
            bool: True если пара доступна для торговли
        """
        try:
            pair_info = await self.validate_pair(symbol)
            return pair_info is not None and pair_info.get("status") == "TRADING"
        except Exception as e:
            self.logger.error("Error checking if pair is tradable", symbol=symbol, error=str(e))
            return False

    async def _ensure_session(self) -> None:
        """Обеспечить наличие HTTP сессии."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "CryptoBotValidator/1.0"
                }
            )

    async def _close_session(self) -> None:
        """Закрыть HTTP сессию."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _ensure_exchange_info(self) -> None:
        """Обеспечить наличие актуальной информации о бирже."""
        current_time = asyncio.get_event_loop().time()

        # Проверяем кеш
        if (self._exchange_info_cache and
                self._cache_timestamp and
                current_time - self._cache_timestamp < self._cache_ttl):
            return

        try:
            await self._ensure_session()

            url = f"{self.config.rest_api_url}/api/v3/exchangeInfo"

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self._exchange_info_cache = data
                    self._cache_timestamp = current_time

                    symbols_count = len(data.get("symbols", []))
                    self.logger.info("Exchange info updated", symbols_count=symbols_count)

                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise BinanceRateLimitError(retry_after)

                else:
                    raise BinanceAPIError(f"HTTP {response.status}: {await response.text()}")

        except aiohttp.ClientError as e:
            raise BinanceConnectionError(f"Connection error: {str(e)}")

    async def _get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о символе из Binance API.

        Args:
            symbol: Символ торговой пары

        Returns:
            Optional[Dict[str, Any]]: Информация о символе или None
        """
        # Сначала проверяем кеш exchange info
        symbol_info = await self._get_symbol_info_from_cache(symbol)
        if symbol_info:
            return symbol_info

        # Если не найдено в кеше, обновляем информацию о бирже
        await self._ensure_exchange_info()

        # Повторно проверяем кеш
        return await self._get_symbol_info_from_cache(symbol)

    async def _get_symbol_info_from_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о символе из кеша.

        Args:
            symbol: Символ торговой пары

        Returns:
            Optional[Dict[str, Any]]: Информация о символе или None
        """
        if not self._exchange_info_cache:
            return None

        for symbol_info in self._exchange_info_cache.get("symbols", []):
            if symbol_info.get("symbol") == symbol:
                return symbol_info

        return None

    async def _make_api_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполнить запрос к Binance API.

        Args:
            endpoint: Endpoint API
            params: Параметры запроса

        Returns:
            Dict[str, Any]: Ответ от API
        """
        await self._ensure_session()

        url = f"{self.config.rest_api_url}{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()

                    elif response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))

                        if attempt < self.config.max_retries - 1:
                            self.logger.warning(
                                "Rate limit hit, retrying",
                                attempt=attempt + 1,
                                retry_after=retry_after
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            raise BinanceRateLimitError(retry_after)

                    else:
                        error_text = await response.text()
                        raise BinanceAPIError(f"HTTP {response.status}: {error_text}")

            except aiohttp.ClientError as e:
                if attempt < self.config.max_retries - 1:
                    self.logger.warning(
                        "Connection error, retrying",
                        attempt=attempt + 1,
                        error=str(e)
                    )
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                else:
                    raise BinanceConnectionError(
                        f"Connection failed after {self.config.max_retries} attempts: {str(e)}")

        raise BinanceAPIError("Max retries exceeded")

    def clear_cache(self) -> None:
        """Очистить кеш валидатора."""
        self._symbols_cache.clear()
        self._exchange_info_cache = None
        self._cache_timestamp = None

        self.logger.info("Validator cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кеша.

        Returns:
            Dict[str, Any]: Статистика кеша
        """
        current_time = asyncio.get_event_loop().time()

        cache_age = None
        if self._cache_timestamp:
            cache_age = current_time - self._cache_timestamp

        return {
            "symbols_cached": len(self._symbols_cache),
            "exchange_info_cached": self._exchange_info_cache is not None,
            "cache_age_seconds": cache_age,
            "cache_ttl_seconds": self._cache_ttl,
            "is_cache_valid": (
                    self._cache_timestamp is not None and
                    cache_age is not None and
                    cache_age < self._cache_ttl
            )
        }