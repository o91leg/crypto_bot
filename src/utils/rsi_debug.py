"""
Путь: src/utils/rsi_debug.py
Описание: Утилиты для отладки и валидации расчета RSI
Автор: Crypto Bot Team
Дата создания: 2025-07-30
"""

from typing import List
from decimal import Decimal

def debug_rsi_calculation(prices: List[float], period: int = 14) -> dict:
    """
    Детальная отладка расчета RSI с пошаговым логированием.
    
    Args:
        prices: Список цен закрытия
        period: Период RSI
        
    Returns:
        dict: Детальная информация о расчете
    """
    if len(prices) < period + 1:
        return {"error": f"Недостаточно данных: нужно {period + 1}, есть {len(prices)}"}
    
    # Последние цены для расчета
    recent_prices = prices[-(period + 5):]  # Берем чуть больше для контекста
    
    # Вычисляем изменения
    changes = []
    for i in range(1, len(recent_prices)):
        change = recent_prices[i] - recent_prices[i-1]
        changes.append(change)
    
    # Разделяем прибыли и убытки
    gains = [max(change, 0) for change in changes]
    losses = [abs(min(change, 0)) for change in changes]
    
    # Первое среднее
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rs = avg_gain / avg_loss if avg_loss > 0 else float('inf')
    rsi = 100 - (100 / (1 + rs)) if rs != float('inf') else 100
    
    return {
        "prices_used": recent_prices,
        "price_changes": changes,
        "gains": gains,
        "losses": losses,
        "avg_gain": round(avg_gain, 6),
        "avg_loss": round(avg_loss, 6),
        "rs": round(rs, 6) if rs != float('inf') else "infinity",
        "rsi": round(rsi, 2),
        "period": period,
        "data_points": len(prices)
    }

def compare_with_manual_rsi(symbol: str, expected_rsi: float, calculated_rsi: float) -> str:
    """
    Сравнить рассчитанный RSI с ожидаемым значением.
    
    Args:
        symbol: Символ пары
        expected_rsi: Ожидаемое значение (например, с TradingView)
        calculated_rsi: Наше рассчитанное значение
        
    Returns:
        str: Результат сравнения
    """
    difference = abs(expected_rsi - calculated_rsi)
    
    if difference <= 1:
        status = "✅ ТОЧНО"
    elif difference <= 3:
        status = "⚠️ БЛИЗКО"
    else:
        status = "❌ НЕТОЧНО"
    
    return f"""
🔍 Сравнение RSI для {symbol}:
{status}
Ожидаемый: {expected_rsi}
Наш расчет: {calculated_rsi}
Разница: {difference:.2f}
Допустимо: разница до 1-2 пунктов
"""
