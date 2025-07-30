"""
Путь: src/bot/handlers/add_pair/add_pair_formatters.py
Описание: Форматирование сообщений для добавления торговых пар
Автор: Crypto Bot Team
Дата создания: 2025-07-28
"""

from config.bot_config import get_bot_config


def create_add_pair_instruction() -> str:
    """
    Создать текст инструкции для добавления пары.

    Returns:
        str: Текст инструкции
    """
    return """➕ <b>Добавление новой торговой пары</b>

Введите символ криптовалюты или полное название торговой пары:

<b>Примеры:</b>
• <code>BTC</code> - для BTC/USDT
• <code>ETH</code> - для ETH/USDT
• <code>SOL</code> - для SOL/USDT
• <code>ADAUSDT</code> - для полного символа

<b>Поддерживаемые котируемые валюты:</b>
USDT, BTC, ETH, BNB

<i>После ввода я проверю доступность пары на Binance и предложу подтвердить добавление.</i>"""


def create_pair_confirmation_text(symbol_info: dict) -> str:
    """
    Создать текст подтверждения добавления пары.

    Args:
        symbol_info: Информация о паре

    Returns:
        str: Текст подтверждения
    """
    config = get_bot_config()

    # Безопасно извлекаем данные из symbol_info
    display_name = symbol_info.get('display_name', 'Неизвестно')
    symbol = symbol_info.get('symbol', 'Неизвестно')
    base_asset = symbol_info.get('base_asset', 'Неизвестно')
    quote_asset = symbol_info.get('quote_asset', 'Неизвестно')
    is_new_pair = symbol_info.get('is_new_pair', False)

    # Экранируем HTML символы для безопасности
    display_name_safe = str(display_name).replace('<', '&lt;').replace('>', '&gt;')
    symbol_safe = str(symbol).replace('<', '&lt;').replace('>', '&gt;')
    base_asset_safe = str(base_asset).replace('<', '&lt;').replace('>', '&gt;')
    quote_asset_safe = str(quote_asset).replace('<', '&lt;').replace('>', '&gt;')

    timeframes_text = ', '.join(config.default_timeframes)

    return f"""✅ <b>Торговая пара найдена!</b>

<b>Пара:</b> {display_name_safe}
<b>Символ:</b> {symbol_safe}
<b>Базовая валюта:</b> {base_asset_safe}
<b>Котируемая валюта:</b> {quote_asset_safe}

<b>Настройки по умолчанию:</b>
- Все таймфреймы включены: {timeframes_text}
- Уведомления включены
- RSI зоны: перепроданность &lt;30, перекупленность &gt;70

<i>📊 {'Будут загружены исторические данные для расчета индикаторов' if is_new_pair else 'Исторические данные уже доступны'}</i>

<b>Добавить эту пару в отслеживание?</b>"""

def create_pair_error_text(error_type: str, symbol_input: str) -> str:
    """
    Создать текст ошибки при валидации пары.

    Args:
        error_type: Тип ошибки
        symbol_input: Введенный символ

    Returns:
        str: Текст ошибки
    """
    error_messages = {
        "invalid_format": f"""❌ <b>Неверный формат символа</b>

Символ '{symbol_input}' не соответствует формату торговых пар Binance.

<b>Правильные примеры:</b>
• BTC (для BTC/USDT)
• ETHUSDT (полный символ)
• SOL (для SOL/USDT)

Попробуйте еще раз или вернитесь в главное меню.""",

        "already_exists": f"""ℹ️ <b>Пара уже добавлена</b>

Торговая пара {symbol_input.upper()} уже находится в вашем отслеживании.

<b>Что можно сделать:</b>
• Управлять этой парой через "📈 Мои пары"
• Добавить другую торговую пару
• Вернуться в главное меню""",

        "not_found": f"""❌ <b>Пара не найдена</b>

Торговая пара '{symbol_input}' не найдена на бирже Binance.

<b>Возможные причины:</b>
• Неправильное написание символа
• Пара не торгуется на Binance
• Пара была делистирована

Проверьте символ и попробуйте еще раз.""",

        "processing_error": f"""⚠️ <b>Ошибка обработки</b>

Произошла ошибка при обработке символа '{symbol_input}'.

<b>Что можно сделать:</b>
• Попробовать еще раз
• Проверить интернет-соединение
• Обратиться к администратору

Попробуйте добавить пару позже."""
    }

    return error_messages.get(error_type, f"""❌ <b>Неизвестная ошибка</b>

Произошла неизвестная ошибка при обработке символа '{symbol_input}'.

Попробуйте еще раз или обратитесь к администратору.""")


def create_pair_added_text(result: dict) -> str:
    """
    Создать текст успешного добавления пары.

    Args:
        result: Результат добавления пары

    Returns:
        str: Текст успеха
    """
    pair_info = result.get("pair")
    historical_candles = result.get("historical_candles", 0)
    timeframes = result.get("timeframes", [])

    text = f"""✅ <b>Пара успешно добавлена!</b>

<b>Торговая пара:</b> {result['display_name']}
<b>Символ:</b> {result['symbol']}

<b>Настройки:</b>
• Активные таймфреймы: {len(timeframes)}
• Список: {', '.join(timeframes)}
• Уведомления: включены

<b>Данные:</b>"""

    if historical_candles > 0:
        text += f"\n• Загружено исторических свечей: {historical_candles}"
        text += f"\n• Индикаторы готовы к расчету"
    else:
        text += f"\n• Исторические данные будут загружены в фоне"
        text += f"\n• Индикаторы станут доступны через 1-2 минуты"

    text += f"""

<b>Что дальше?</b>
• Просматривать RSI через "📈 Мои пары"
• Настраивать таймфреймы
• Получать торговые сигналы

<i>🎉 Поздравляем! Теперь вы будете получать сигналы по этой паре.</i>"""

    return text


def create_add_error_text(error: str) -> str:
    """
    Создать текст ошибки добавления пары.

    Args:
        error: Описание ошибки

    Returns:
        str: Текст ошибки
    """
    return f"""❌ <b>Ошибка добавления пары</b>

{error}

<b>Что можно сделать:</b>
• Попробовать добавить пару еще раз
• Проверить правильность символа
• Обратиться к администратору

Вы можете вернуться в главное меню и попробовать позже."""


def create_validation_loading_text(symbol: str) -> str:
    """
    Создать текст загрузки валидации.

    Args:
        symbol: Символ пары

    Returns:
        str: Текст загрузки
    """
    return f"""🔍 <b>Проверяем пару {symbol.upper()}...</b>

Выполняется валидация через Binance API:
• Проверка существования пары
• Получение информации о символе
• Проверка статуса торговли

<i>Пожалуйста, подождите...</i>"""


def create_execution_loading_text() -> str:
    """
    Создать текст загрузки выполнения.

    Returns:
        str: Текст загрузки
    """
    return """⏳ <b>Добавляем торговую пару...</b>

Выполняется настройка отслеживания:
• Создание записи в базе данных
• Настройка таймфреймов по умолчанию
• Загрузка исторических данных
• Инициализация индикаторов

<i>Это может занять несколько секунд...</i>"""


