"""
Путь: scripts/test_websocket.py
Описание: Тестовый скрипт для проверки WebSocket подключения к Binance
Автор: Crypto Bot Team
Дата создания: 2025-07-29
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.websocket.binance_websocket import BinanceWebSocketClient
from config.binance_config import get_binance_config, get_websocket_url


class WebSocketTester:
    """Класс для тестирования WebSocket подключения."""

    def __init__(self):
        self.message_count = 0
        self.error_count = 0
        self.test_duration = 30  # секунд
        self.test_symbols = ["btcusdt", "ethusdt", "adausdt"]
        self.test_timeframes = ["1m", "5m"]

    async def message_handler(self, message: dict):
        """Обработчик входящих сообщений."""
        self.message_count += 1

        print(f"\n📨 Получено сообщение #{self.message_count}")

        # Проверяем тип сообщения
        if 'stream' in message:
            stream_name = message['stream']
            data = message.get('data', {})

            if 'k' in data:  # Kline/Candle data
                kline = data['k']
                symbol = kline.get('s', 'Unknown')
                interval = kline.get('i', 'Unknown')
                open_price = kline.get('o', '0')
                close_price = kline.get('c', '0')
                high_price = kline.get('h', '0')
                low_price = kline.get('l', '0')
                volume = kline.get('v', '0')
                is_closed = kline.get('x', False)

                print(f"📊 {symbol} ({interval}) - O:{open_price} H:{high_price} L:{low_price} C:{close_price}")
                print(f"   Volume: {volume}, Closed: {'✅' if is_closed else '❌'}")

        elif 'id' in message:  # Response to subscription
            print(f"🔔 Ответ на подписку: {message}")

        elif 'error' in message:  # Error message
            self.error_count += 1
            print(f"❌ Ошибка: {message['error']}")

        else:
            print(f"❓ Неизвестный тип сообщения: {json.dumps(message, indent=2)}")

    async def error_handler(self, error: Exception):
        """Обработчик ошибок."""
        self.error_count += 1
        print(f"❌ Ошибка WebSocket: {error}")

    async def test_basic_connection(self):
        """Тест базового подключения."""
        print("🔄 Тестируем базовое подключение...")

        client = BinanceWebSocketClient(
            message_handler=self.message_handler,
            error_handler=self.error_handler
        )

        try:
            # Подключаемся
            print("🔗 Подключаемся к Binance WebSocket...")
            success = await client.connect()

            if not success:
                print("❌ Не удалось подключиться к WebSocket")
                return False

            print("✅ Подключение установлено!")

            # Ждем немного чтобы убедиться что соединение стабильно
            await asyncio.sleep(2)

            if client.is_connected():
                print("✅ Соединение стабильно")
                return True
            else:
                print("❌ Соединение нестабильно")
                return False

        except Exception as e:
            print(f"❌ Ошибка при тестировании подключения: {e}")
            return False
        finally:
            await client.disconnect()

    async def test_kline_subscription(self):
        """Тест подписки на kline данные."""
        print("\n🔄 Тестируем подписку на kline данные...")

        client = BinanceWebSocketClient(
            message_handler=self.message_handler,
            error_handler=self.error_handler
        )

        try:
            # Подключаемся
            await client.connect()

            if not client.is_connected():
                print("❌ Не удалось подключиться")
                return False

            # Подписываемся на несколько потоков
            streams = []
            for symbol in self.test_symbols[:2]:  # Только первые 2 символа
                for timeframe in self.test_timeframes:
                    stream_name = f"{symbol}@kline_{timeframe}"
                    streams.append(stream_name)

            print(f"📡 Подписываемся на потоки: {streams}")
            success = await client.subscribe(streams)

            if not success:
                print("❌ Не удалось подписаться на потоки")
                return False

            print("✅ Подписка успешна!")

            # Слушаем сообщения
            print(f"👂 Слушаем сообщения в течение {self.test_duration} секунд...")

            start_time = asyncio.get_event_loop().time()
            timeout_time = start_time + self.test_duration

            while asyncio.get_event_loop().time() < timeout_time:
                await asyncio.sleep(1)

                # Показываем прогресс каждые 5 секунд
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                if elapsed % 5 == 0 and elapsed > 0:
                    remaining = self.test_duration - elapsed
                    print(f"⏱️  Осталось {remaining} секунд. Получено {self.message_count} сообщений")

            print(f"\n📊 Результаты теста:")
            print(f"   📨 Всего сообщений: {self.message_count}")
            print(f"   ❌ Ошибок: {self.error_count}")
            print(f"   📡 Активных подписок: {len(client.subscribed_streams)}")

            # Отписываемся
            print("🚫 Отписываемся от потоков...")
            await client.unsubscribe(streams)

            return self.message_count > 0 and self.error_count == 0

        except Exception as e:
            print(f"❌ Ошибка при тестировании подписки: {e}")
            return False
        finally:
            await client.disconnect()

    async def test_reconnection(self):
        """Тест переподключения."""
        print("\n🔄 Тестируем переподключение...")

        client = BinanceWebSocketClient(
            message_handler=self.message_handler,
            error_handler=self.error_handler
        )

        try:
            # Подключаемся
            await client.connect()

            if not client.is_connected():
                print("❌ Не удалось подключиться")
                return False

            print("✅ Первоначальное подключение установлено")

            # Принудительно разрываем соединение
            print("🔌 Принудительно разрываем соединение...")
            await client.websocket.close()

            # Ждем попытки переподключения
            print("⏱️  Ждем переподключения...")
            await asyncio.sleep(10)

            if client.is_connected():
                print("✅ Переподключение успешно!")
                return True
            else:
                print("❌ Переподключение не удалось")
                return False

        except Exception as e:
            print(f"❌ Ошибка при тестировании переподключения: {e}")
            return False
        finally:
            await client.disconnect()


async def main():
    """Главная функция для запуска тестов."""
    print("🚀 Запуск тестирования WebSocket подключения к Binance")
    print("=" * 50)

    # Показываем конфигурацию
    config = get_binance_config()
    print(f"🔗 WebSocket URL: {get_websocket_url()}")
    print(f"📡 Ping интервал: {config.ping_interval}s")
    print(f"🔄 Максимум попыток переподключения: {config.max_reconnect_attempts}")
    print("=" * 50)

    tester = WebSocketTester()
    tests_passed = 0
    total_tests = 4

    # Тест 1: Базовое подключение
    test1_result = await tester.test_basic_connection()
    if test1_result:
        tests_passed += 1
        print("✅ Тест 1: Базовое подключение - ПРОЙДЕН")
    else:
        print("❌ Тест 1: Базовое подключение - ПРОВАЛЕН")

    # Тест 2: Подписка на данные (только если первый тест прошел)
    if test1_result:
        test2_result = await tester.test_kline_subscription()
        if test2_result:
            tests_passed += 1
            print("✅ Тест 2: Подписка на kline данные - ПРОЙДЕН")
        else:
            print("❌ Тест 2: Подписка на kline данные - ПРОВАЛЕН")
    else:
        print("⏭️  Тест 2: Пропущен из-за провала предыдущего теста")

    # Тест 3: Переподключение (только если первый тест прошел)
    if test1_result:
        test3_result = await tester.test_reconnection()
        if test3_result:
            tests_passed += 1
            print("✅ Тест 3: Переподключение - ПРОЙДЕН")
        else:
            print("❌ Тест 3: Переподключение - ПРОВАЛЕН")
    else:
        print("⏭️  Тест 3: Пропущен из-за провала предыдущего теста")

    # Тест 4: StreamManager (только если первый тест прошел)
    if test1_result:
        test4_result = await tester.test_stream_manager()
        if test4_result:
            tests_passed += 1
            print("✅ Тест 4: StreamManager - ПРОЙДЕН")
        else:
            print("❌ Тест 4: StreamManager - ПРОВАЛЕН")
    else:
        print("⏭️  Тест 4: Пропущен из-за провала предыдущего теста")

    # Итоговые результаты
    print("\n" + "=" * 50)
    print(f"📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print(f"✅ Пройдено тестов: {tests_passed}/{total_tests}")
    print(f"📨 Всего получено сообщений: {tester.message_count}")
    print(f"❌ Всего ошибок: {tester.error_count}")

    if tests_passed == total_tests:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! WebSocket работает корректно.")
        return 0
    elif tests_passed > 0:
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ. Требуется доработка.")
        return 1
    else:
        print("💥 ВСЕ ТЕСТЫ ПРОВАЛЕНЫ. WebSocket не работает.")
        return 2


async def test_stream_manager(self):
    """Тест StreamManager."""
    print("\n🔄 Тестируем StreamManager...")

    try:
        from services.websocket.stream_manager import StreamManager

        # Создаем менеджер потоков
        manager = StreamManager(data_processor=self.message_handler)

        # Запускаем менеджер
        await manager.start()

        if not manager.is_running():
            print("❌ StreamManager не запущен")
            return False

        print("✅ StreamManager запущен")

        # Подписываем тестового пользователя
        user_id = 12345
        symbol = "BTCUSDT"
        timeframes = ["1m", "5m"]

        print(f"📡 Подписываем пользователя {user_id} на {symbol} ({timeframes})")

        results = await manager.subscribe_user_to_pair(user_id, symbol, timeframes)

        if not all(results.values()):
            print(f"❌ Не удалось подписать пользователя: {results}")
            return False

        print("✅ Пользователь подписан")

        # Ждем сообщения
        print("👂 Слушаем сообщения 15 секунд...")
        await asyncio.sleep(15)

        # Получаем статистику
        stats = await manager.get_statistics()
        print(f"📊 Статистика: {stats['total_messages_processed']} сообщений")

        # Отписываем пользователя
        await manager.remove_user_completely(user_id)
        print("✅ Пользователь отписан")

        # Останавливаем менеджер
        await manager.stop()
        print("✅ StreamManager остановлен")

        return stats['total_messages_processed'] > 0

    except Exception as e:
        print(f"❌ Ошибка при тестировании StreamManager: {e}")
        return False


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)