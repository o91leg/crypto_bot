"""
Путь: test_simple.py
Описание: Простой тест WebSocket подключения
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent / "src"))


async def quick_test():
    """Быстрый тест подключения."""
    try:
        print("🔄 Импортируем классы...")
        from services.websocket.binance_websocket import BinanceWebSocketClient
        from services.websocket.stream_manager import StreamManager

        print("✅ Импорт успешен!")

        print("🔗 Тестируем создание WebSocket клиента...")
        client = BinanceWebSocketClient()
        print(f"✅ WebSocket клиент создан: {client.is_connected()}")

        print("📡 Тестируем создание StreamManager...")
        manager = StreamManager()
        print("✅ StreamManager создан!")

        print("🚀 Пробуем подключиться...")
        try:
            await client.connect()
            print("✅ Подключение установлено!")

            print("📊 Статистика подключения:")
            stats = await client.get_connection_stats()
            print(f"   Состояние: {stats['state']}")
            print(f"   ID соединения: {stats['connection_id']}")
            print(f"   Время работы: {stats['uptime_seconds']}s")

            await client.disconnect()
            print("✅ Отключение выполнено!")

        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

        return True

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


async def main():
    """Главная функция."""
    print("🚀 Быстрый тест WebSocket системы")
    print("=" * 40)

    success = await quick_test()

    if success:
        print("\n🎉 ТЕСТ ПРОЙДЕН! WebSocket система работает.")
        return 0
    else:
        print("\n💥 ТЕСТ ПРОВАЛЕН! Есть проблемы с системой.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Тест прерван")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)