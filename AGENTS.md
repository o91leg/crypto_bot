# AGENT.MD - Детальная карта всех файлов проекта крипто-бота

> **Версия:** 2.0 ДЕТАЛЬНАЯ  
> **Дата создания:** 2025-07-30  
> **Назначение:** Полная детализация каждого файла со всеми функциями и методами для идеальной навигации кодекса Claude

## 📋 СОДЕРЖАНИЕ

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Главные файлы](#главные-файлы)
3. [Bot Layer - Telegram интерфейс](#bot-layer---telegram-интерфейс)
4. [Data Layer - Работа с данными](#data-layer---работа-с-данными)
5. [Services Layer - Бизнес логика](#services-layer---бизнес-логика)
6. [Utils Layer - Утилиты](#utils-layer---утилиты)
7. [Config Layer - Конфигурация](#config-layer---конфигурация)
8. [Вспомогательные файлы](#вспомогательные-файлы)
9. [Быстрый поиск по функциям](#быстрый-поиск-по-функциям)

---

## 🏗️ ОБЗОР АРХИТЕКТУРЫ

**Структура проекта:**
```
crypto_bot/
├── src/main.py                 # 🚀 Точка входа
├── .env/.env.example          # 🔧 Переменные окружения
├── docker-compose.yml         # 🐳 Docker конфигурация
├── requirements.txt           # 📦 Python зависимости
├── scripts/                   # 📜 Скрипты
└── src/                       # 💻 Исходный код
    ├── bot/                   # 🤖 Telegram бот
    ├── config/                # ⚙️ Конфигурация
    ├── data/                  # 🗄️ Модели и БД
    ├── services/              # 🔧 Бизнес логика
    └── utils/                 # 🛠️ Утилиты
```

---

# 📁 ДЕТАЛЬНАЯ КАРТА ВСЕХ ФАЙЛОВ

## 🚀 ГЛАВНЫЕ ФАЙЛЫ

### 📄 `src/main.py`
**Назначение:** Главная точка входа приложения - запуск и инициализация всех сервисов

**Глобальные переменные:**
- `bot: Optional[Bot]` - Экземпляр Telegram бота
- `dp: Optional[Dispatcher]` - Диспетчер aiogram
- `stream_manager: Optional[StreamManager]` - Менеджер WebSocket потоков
- `telegram_sender: Optional[TelegramSender]` - Отправщик уведомлений
- `logger` - Структурированный логгер

**Все функции:**
```python
async def create_bot() -> Bot
    """Создать и настроить экземпляр Telegram бота"""

async def setup_dispatcher() -> Dispatcher
    """Настроить диспетчер и зарегистрировать все обработчики"""

def validate_application_config() -> None
    """Валидировать конфигурацию всего приложения"""

def setup_signal_handlers() -> None
    """Настроить обработчики системных сигналов (SIGINT, SIGTERM)"""

async def init_services() -> None
    """Инициализировать все сервисы: БД, Redis, WebSocket, уведомления"""

async def shutdown_services() -> None
    """Корректно завершить работу всех сервисов"""

async def check_connections() -> bool
    """Проверить подключения к БД и Redis"""

async def main() -> None
    """Главная функция запуска приложения"""
```

---

## 🤖 BOT LAYER - TELEGRAM ИНТЕРФЕЙС

### 📂 `src/bot/handlers/`

#### 📄 `src/bot/handlers/start_handler.py`
**Назначение:** Обработка команды /start и регистрация новых пользователей

**Функции:**
```python
@start_router.message(CommandStart())
async def handle_start_command(message: Message, session: AsyncSession, state: FSMContext)
    """Обработчик команды /start с регистрацией пользователя"""

async def get_or_create_user(session: AsyncSession, telegram_user: Any) -> User
    """Получить существующего или создать нового пользователя"""

async def setup_default_pair_for_user(session: AsyncSession, user_id: int) -> bool
    """Создать дефолтную пару BTCUSDT для нового пользователя"""

def create_welcome_message(display_name: str) -> str
    """Создать приветственное сообщение для нового пользователя"""

def create_welcome_back_message(display_name: str) -> str
    """Создать сообщение для возвращающегося пользователя"""

def register_start_handlers(dp: Dispatcher) -> None
    """Зарегистрировать обработчики команды /start в диспетчере"""
```

**Роутер:** `start_router = Router()`

---

#### 📄 `src/bot/handlers/remove_pair_handler.py`
**Назначение:** Обработка удаления торговых пар из отслеживания

**FSM состояния:**
```python
class RemovePairStates(StatesGroup):
    selecting_pair = State()      # Выбор пары для удаления
    confirming_removal = State()  # Подтверждение удаления
```

**Функции:**
```python
@remove_pair_router.callback_query(F.data == "remove_pair")
async def handle_remove_pair_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Начать процесс удаления торговой пары"""

@remove_pair_router.callback_query(RemovePairStates.selecting_pair)
async def handle_pair_selection_for_removal(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Обработать выбор пары для удаления"""

@remove_pair_router.callback_query(RemovePairStates.confirming_removal)
async def handle_removal_confirmation(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Обработать подтверждение удаления пары"""

async def get_user_pairs_for_removal(session: AsyncSession, user_id: int) -> List[UserPair]
    """Получить список пар пользователя для удаления"""

def create_pairs_removal_keyboard(user_pairs: List[UserPair]) -> InlineKeyboardMarkup
    """Создать клавиатуру выбора пары для удаления"""

def create_removal_confirmation_message(pair: Pair) -> str
    """Создать сообщение подтверждения удаления пары"""

async def execute_pair_removal(session: AsyncSession, user_id: int, pair_id: int) -> bool
    """Выполнить удаление пары из отслеживания пользователя"""

def register_remove_pair_handlers(dp: Dispatcher) -> None
    """Зарегистрировать обработчики удаления пар"""
```

**Роутер:** `remove_pair_router = Router()`

---

### 📂 `src/bot/handlers/add_pair/` (Модуль)

#### 📄 `src/bot/handlers/add_pair/add_pair_handler.py`
**Назначение:** Основные FSM обработчики для добавления торговых пар

**FSM состояния:**
```python
class AddPairStates(StatesGroup):
    waiting_for_symbol = State()  # Ожидание ввода символа пары
    confirming_pair = State()     # Подтверждение добавления пары
```

**Функции:**
```python
@add_pair_router.callback_query(F.data == "add_pair")
async def handle_add_pair_start(callback: CallbackQuery, state: FSMContext)
    """Начать процесс добавления новой торговой пары"""

@add_pair_router.message(AddPairStates.waiting_for_symbol)
async def handle_pair_symbol_input(message: Message, session: AsyncSession, state: FSMContext)
    """Обработать ввод символа торговой пары пользователем"""

@add_pair_router.callback_query(AddPairStates.confirming_pair, F.data == "confirm_add_pair")
async def handle_pair_confirmation(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Обработать подтверждение добавления пары"""

@add_pair_router.callback_query(F.data == "cancel_add_pair")
async def handle_cancel_add_pair(callback: CallbackQuery, state: FSMContext)
    """Отменить процесс добавления пары"""

def register_add_pair_handlers(dp: Dispatcher) -> None
    """Зарегистрировать обработчики добавления пар в диспетчере"""
```

**Роутер:** `add_pair_router = Router()`

#### 📄 `src/bot/handlers/add_pair/add_pair_logic.py`
**Назначение:** Бизнес-логика добавления пар

**Функции:**
```python
async def process_symbol_input(session: AsyncSession, symbol: str) -> Dict[str, Any]
    """Обработать и валидировать введенный символ торговой пары"""

async def validate_pair_on_binance(symbol: str) -> Dict[str, Any]
    """Валидировать существование пары на Binance через API"""

async def execute_add_pair(session: AsyncSession, user_id: int, symbol: str) -> Dict[str, Any]
    """Выполнить добавление пары в БД и настройки пользователя"""

async def setup_pair_timeframes(session: AsyncSession, user_id: int, pair_id: int) -> Dict[str, bool]
    """Настроить дефолтные таймфреймы для добавленной пары"""

async def fetch_initial_candle_data(symbol: str) -> bool
    """Загрузить начальные исторические данные для новой пары"""
```

#### 📄 `src/bot/handlers/add_pair/add_pair_formatters.py`
**Назначение:** Форматирование сообщений для добавления пар

**Функции:**
```python
def create_add_pair_instruction() -> str
    """Создать инструкцию для пользователя о вводе символа пары"""

def create_pair_confirmation_text(symbol: str, pair_info: Dict[str, Any]) -> str
    """Создать текст подтверждения с информацией о паре"""

def create_pair_error_text(error_type: str, symbol: str = None) -> str
    """Создать сообщение об ошибке при добавлении пары"""

def create_pair_added_text(symbol: str, timeframes_count: int) -> str
    """Создать сообщение об успешном добавлении пары"""

def create_add_error_text(error_message: str) -> str
    """Создать сообщение об общей ошибке при добавлении"""

def format_pair_info_display(pair_info: Dict[str, Any]) -> str
    """Форматировать информацию о паре для отображения"""
```

---

### 📂 `src/bot/handlers/my_pairs/` (Модуль)

#### 📄 `src/bot/handlers/my_pairs/my_pairs_handler.py`
**Назначение:** Основные обработчики FSM для управления торговыми парами пользователя

**FSM состояния:**
```python
class MyPairsStates(StatesGroup):
    viewing_pairs = State()        # Просмотр списка пар
    managing_timeframes = State()  # Управление таймфреймами
    viewing_rsi = State()          # Просмотр RSI значений
```

**Функции:**
```python
@my_pairs_router.callback_query(F.data == "my_pairs")
async def handle_my_pairs_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Показать список пар пользователя"""

@my_pairs_router.callback_query(MyPairsStates.viewing_pairs)
async def handle_pair_management(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Обработать выбор пары для управления"""

@my_pairs_router.callback_query(MyPairsStates.managing_timeframes)
async def handle_timeframe_toggle(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Переключить состояние таймфрейма для пары"""

@my_pairs_router.callback_query(MyPairsStates.viewing_rsi)
async def handle_rsi_view(callback: CallbackQuery, session: AsyncSession, state: FSMContext)
    """Показать текущие значения RSI для пары"""

async def get_user_pairs_with_stats(session: AsyncSession, user_id: int) -> List[Dict[str, Any]]
    """Получить пары пользователя со статистикой сигналов"""

def register_my_pairs_handlers(dp: Dispatcher) -> None
    """Зарегистрировать обработчики управления парами"""
```

**Роутер:** `my_pairs_router = Router()`

#### 📄 `src/bot/handlers/my_pairs/my_pairs_formatters.py`
**Назначение:** Форматирование сообщений для управления парами

**Функции:**
```python
def create_no_pairs_message() -> str
    """Создать сообщение когда у пользователя нет пар"""

def create_pairs_list_message(user_pairs: List[Dict[str, Any]]) -> str
    """Форматировать сообщение со списком пар пользователя"""

def create_pair_management_message(pair: Pair, user_pair: UserPair) -> str
    """Создать сообщение управления конкретной парой"""

def create_rsi_display_message(symbol: str, rsi_data: Dict[str, float]) -> str
    """Создать сообщение с отображением RSI значений"""

def create_rsi_error_message(symbol: str, error: str) -> str
    """Создать сообщение об ошибке получения RSI"""

def format_timeframes_status(timeframes: Dict[str, bool]) -> str
    """Форматировать статус включенных/выключенных таймфреймов"""

def format_pair_statistics(signals_count: int, last_signal: Optional[datetime]) -> str
    """Форматировать статистику по паре (сигналы, последний сигнал)"""
```

#### 📄 `src/bot/handlers/my_pairs/my_pairs_keyboards.py`
**Назначение:** Клавиатуры для управления парами

**Функции:**
```python
def create_no_pairs_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру когда у пользователя нет пар"""

def create_pairs_list_keyboard(user_pairs: List[Dict[str, Any]]) -> InlineKeyboardMarkup
    """Создать клавиатуру со списком пар для выбора"""

def create_pair_management_keyboard(pair_id: int, user_pair: UserPair) -> InlineKeyboardMarkup
    """Создать клавиатуру управления конкретной парой"""

def create_timeframes_keyboard(pair_id: int, timeframes: Dict[str, bool]) -> InlineKeyboardMarkup
    """Создать клавиатуру переключения таймфреймов"""

def create_rsi_display_keyboard(pair_id: int) -> InlineKeyboardMarkup
    """Создать клавиатуру для просмотра RSI значений"""

def get_back_to_management_keyboard(pair_id: int) -> InlineKeyboardMarkup
    """Создать клавиатуру возврата к управлению парой"""
```

#### 📄 `src/bot/handlers/my_pairs/my_pairs_logic.py`
**Назначение:** Бизнес-логика управления парами

**Функции:**
```python
async def calculate_rsi_for_pair(session: AsyncSession, symbol: str, timeframes: List[str]) -> Dict[str, float]
    """Рассчитать текущие значения RSI для пары по всем таймфреймам"""

async def toggle_timeframe(session: AsyncSession, user_id: int, pair_id: int, timeframe: str) -> bool
    """Переключить состояние таймфрейма (включен/выключен)"""

async def get_pair_signal_statistics(session: AsyncSession, user_id: int, pair_id: int) -> Dict[str, Any]
    """Получить статистику сигналов по паре для пользователя"""

async def update_timeframes_config(session: AsyncSession, user_id: int, pair_id: int, new_config: Dict[str, bool]) -> bool
    """Обновить конфигурацию таймфреймов для пары"""

async def validate_timeframe_change(current_config: Dict[str, bool], timeframe: str, new_state: bool) -> bool
    """Валидировать изменение таймфрейма (минимум один должен быть включен)"""
```

---

### 📂 `src/bot/keyboards/`

#### 📄 `src/bot/keyboards/main_menu_kb.py`
**Назначение:** Все клавиатуры для навигации по боту

**Функции:**
```python
def get_main_menu_keyboard() -> InlineKeyboardMarkup
    """Создать главное меню бота с основными функциями"""

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру с кнопкой возврата в главное меню"""

def get_confirmation_keyboard(action: str, item_id: str = None) -> InlineKeyboardMarkup
    """Создать клавиатуру подтверждения действия (Да/Нет)"""

def get_loading_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру с индикатором загрузки"""

def get_menu_with_notification_button(show_notification_controls: bool = True) -> InlineKeyboardMarkup
    """Создать расширенное меню с управлением уведомлениями"""

def get_navigation_keyboard(back_callback: str = "main_menu", additional_buttons: list = None) -> InlineKeyboardMarkup
    """Создать универсальную навигационную клавиатуру"""

def get_error_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру для сообщений об ошибках"""

def get_settings_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру настроек бота"""

def get_help_keyboard() -> InlineKeyboardMarkup
    """Создать клавиатуру раздела помощи"""
```

---

### 📂 `src/bot/middlewares/`

#### 📄 `src/bot/middlewares/database_mw.py`
**Назначение:** Middleware для автоматического создания сессий БД

**Классы и функции:**
```python
class DatabaseMiddleware(BaseMiddleware):
    """Middleware для предоставления сессии БД в обработчики"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Основной метод middleware - создание и управление сессией БД"""

    async def _handle_database_error(
        self,
        event: TelegramObject,
        error: Exception,
        user_id: Optional[int] = None
    ) -> None:
        """Обработать ошибку базы данных и отправить сообщение пользователю"""

    def _extract_user_id(self, event: TelegramObject) -> Optional[int]
        """Извлечь ID пользователя из события"""

    def _create_error_message(self, error: Exception) -> str
        """Создать пользовательское сообщение об ошибке"""
```

---

## 🗄️ DATA LAYER - РАБОТА С ДАННЫМИ

### 📂 `src/data/models/`

#### 📄 `src/data/models/base_model.py`
**Назначение:** Базовая модель для всех таблиц

**Классы:**
```python
class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy моделей"""
    
    # Автоматические поля для всех моделей
    created_at: Mapped[datetime]  # Время создания
    updated_at: Mapped[datetime]  # Время обновления
```

#### 📄 `src/data/models/user_model.py`
**Назначение:** Модель пользователя Telegram

**Модель:**
```python
class User(Base):
    """Модель пользователя Telegram"""
    
    # Поля таблицы
    id: BigInteger                      # Telegram user ID (PK)
    username: String(50)                # @username
    first_name: String(100)             # Имя
    last_name: String(100)              # Фамилия  
    language_code: String(10)           # Код языка
    notifications_enabled: Boolean      # Включены ли уведомления
    is_active: Boolean                  # Активен ли пользователь
    is_blocked: Boolean                 # Заблокирован ли бот
    total_signals_received: Integer     # Всего получено сигналов
    
    # Связи
    user_pairs: relationship("UserPair")
    signal_history: relationship("SignalHistory")
```

**Методы:**
```python
@property
def display_name(self) -> str
    """Получить отображаемое имя пользователя"""

def update_from_telegram(self, telegram_user) -> None
    """Обновить данные пользователя из Telegram"""

def increment_signals_count(self) -> None
    """Увеличить счетчик полученных сигналов"""

def toggle_notifications(self) -> bool
    """Переключить состояние уведомлений"""

def mark_as_blocked(self) -> None
    """Отметить пользователя как заблокировавшего бота"""

def mark_as_active(self) -> None
    """Отметить пользователя как активного"""

def to_dict(self) -> Dict[str, Any]
    """Преобразовать модель в словарь"""
```

#### 📄 `src/data/models/pair_model.py`
**Назначение:** Модель криптовалютной торговой пары

**Модель:**
```python
class Pair(Base):
    """Модель торговой пары"""
    
    # Поля таблицы
    id: Integer                    # ID пары (PK)
    symbol: String(20)             # Символ пары (BTCUSDT)
    base_asset: String(10)         # Базовая валюта (BTC)
    quote_asset: String(10)        # Котируемая валюта (USDT)
    is_active: Boolean             # Активна ли пара
    is_tracked: Boolean            # Отслеживается ли WebSocket
    price_precision: Integer       # Точность цены
    quantity_precision: Integer    # Точность количества
    users_count: Integer           # Количество пользователей
    signals_count: Integer         # Количество сигналов
    last_price: Numeric(18,8)      # Последняя цена
    
    # Связи
    user_pairs: relationship("UserPair")
    candles: relationship("Candle")
    signal_history: relationship("SignalHistory")
```

**Методы:**
```python
@property
def display_name(self) -> str
    """Получить отображаемое название пары"""

def increment_users_count(self) -> None
    """Увеличить счетчик пользователей"""

def decrement_users_count(self) -> None
    """Уменьшить счетчик пользователей"""

def increment_signals_count(self) -> None
    """Увеличить счетчик сигналов"""

def update_last_price(self, price: Decimal) -> None
    """Обновить последнюю цену"""

def activate(self) -> None
    """Активировать пару"""

def deactivate(self) -> None
    """Деактивировать пару"""

def start_tracking(self) -> None
    """Начать отслеживание через WebSocket"""

def stop_tracking(self) -> None
    """Остановить отслеживание"""

@classmethod
async def from_symbol(cls, session: AsyncSession, symbol: str) -> "Pair"
    """Создать пару из символа с валидацией"""

def to_dict(self) -> Dict[str, Any]
    """Преобразовать модель в словарь"""
```

#### 📄 `src/data/models/user_pair_model.py`
**Назначение:** Связь между пользователем и торговой парой

**Модель:**
```python
class UserPair(Base):
    """Модель связи пользователь-пара"""
    
    # Составной первичный ключ
    user_id: BigInteger              # ID пользователя (PK)
    pair_id: Integer                 # ID пары (PK)
    
    # Настройки
    timeframes: JSON                 # {timeframe: enabled}
    custom_settings: JSON            # Дополнительные настройки
    signals_received: Integer        # Количество сигналов
    
    # Связи
    user: relationship("User")
    pair: relationship("Pair")
```

**Методы:**
```python
def __init__(self, user_id: int, pair_id: int, timeframes: Optional[Dict[str, bool]] = None)
    """Инициализация с дефолтными таймфреймами"""

def get_enabled_timeframes(self) -> List[str]
    """Получить список включенных таймфреймов"""

def enable_timeframe(self, timeframe: str) -> bool
    """Включить таймфрейм"""

def disable_timeframe(self, timeframe: str) -> bool
    """Выключить таймфрейм (с проверкой минимума)"""

def is_timeframe_enabled(self, timeframe: str) -> bool
    """Проверить включен ли таймфрейм"""

def update_timeframes(self, new_timeframes: Dict[str, bool]) -> bool
    """Обновить настройки таймфреймов"""

def increment_signals_count(self) -> None
    """Увеличить счетчик сигналов"""

@classmethod
async def get_users_for_timeframe(cls, session: AsyncSession, pair_id: int, timeframe: str) -> List["UserPair"]
    """Получить пользователей с включенным таймфреймом"""

@classmethod
async def create_user_pair(cls, session: AsyncSession, user_id: int, pair_id: int, timeframes: Optional[Dict[str, bool]] = None) -> "UserPair"
    """Создать связь пользователь-пара"""

def to_dict(self, include_pair_info: bool = False) -> Dict[str, Any]
    """Преобразовать в словарь"""
```

#### 📄 `src/data/models/candle_model.py`
**Назначение:** Модель свечи (OHLCV данные)

**Модель:**
```python
class Candle(Base):
    """Модель свечи для хранения OHLCV данных"""
    
    # Поля таблицы
    id: Integer                      # ID свечи (PK)
    pair_id: Integer                 # ID пары (FK)
    timeframe: String(5)             # Таймфрейм
    open_time: BigInteger            # Время открытия (timestamp ms)
    close_time: BigInteger           # Время закрытия (timestamp ms)
    open_price: Numeric(18,8)        # Цена открытия
    high_price: Numeric(18,8)        # Максимальная цена
    low_price: Numeric(18,8)         # Минимальная цена
    close_price: Numeric(18,8)       # Цена закрытия
    volume: Numeric(18,8)            # Объем торгов
    quote_volume: Numeric(18,8)      # Объем в котируемой валюте
    trades_count: Integer            # Количество сделок
    is_closed: Boolean               # Завершена ли свеча
    
    # Связи
    pair: relationship("Pair")
```

**Методы:**
```python
@property
def open_datetime(self) -> datetime
    """Получить время открытия как datetime"""

@property
def close_datetime(self) -> datetime
    """Получить время закрытия как datetime"""

@property
def price_change(self) -> Decimal
    """Рассчитать изменение цены"""

@property
def price_change_percent(self) -> float
    """Рассчитать изменение цены в процентах"""

def update_from_websocket(self, kline_data: Dict[str, Any]) -> None
    """Обновить свечу из WebSocket данных"""

def close_candle(self) -> None
    """Закрыть свечу"""

@classmethod
async def create_from_binance_kline(cls, session: AsyncSession, pair_id: int, kline_data: Dict[str, Any]) -> "Candle"
    """Создать свечу из данных Binance kline"""

@classmethod
async def get_latest_candles(cls, session: AsyncSession, pair_id: int, timeframe: str, limit: int = 100) -> List["Candle"]
    """Получить последние свечи"""

def to_dict(self) -> Dict[str, Any]
    """Преобразовать в словарь"""

def to_ohlcv_tuple(self) -> Tuple[float, float, float, float, float]
    """Преобразовать в OHLCV кортеж"""
```

#### 📄 `src/data/models/signal_history_model.py`
**Назначение:** История отправленных сигналов

**Модель:**
```python
class SignalHistory(Base):
    """Модель истории сигналов"""
    
    # Поля таблицы
    id: Integer                    # ID записи (PK)
    user_id: BigInteger            # ID пользователя (FK)
    pair_id: Integer               # ID пары (FK)
    timeframe: String(5)           # Таймфрейм
    signal_type: String(50)        # Тип сигнала
    signal_value: Numeric(10,4)    # Значение индикатора
    price: Numeric(18,8)           # Цена на момент сигнала
    additional_data: JSON          # Дополнительные данные
    sent_at: DateTime              # Время отправки
    
    # Связи
    user: relationship("User")
    pair: relationship("Pair")
```

**Методы:**
```python
@property
def signal_display_name(self) -> str
    """Получить отображаемое название сигнала"""

@classmethod
async def create_signal_record(
    cls, session: AsyncSession, user_id: int, pair_id: int, 
    timeframe: str, signal_type: str, signal_value: Optional[float],
    price: float, additional_data: Optional[Dict[str, Any]] = None
) -> "SignalHistory"
    """Создать запись о сигнале"""

@classmethod
async def get_user_recent_signals(cls, session: AsyncSession, user_id: int, limit: int = 50) -> List["SignalHistory"]
    """Получить последние сигналы пользователя"""

@classmethod
async def get_last_signal_time(cls, session: AsyncSession, user_id: int, pair_id: int, timeframe: str, signal_type: str) -> Optional[datetime]
    """Получить время последнего сигнала конкретного типа"""

@classmethod
async def count_user_signals(cls, session: AsyncSession, user_id: int, since: Optional[datetime] = None) -> int
    """Подсчитать количество сигналов пользователя"""

def to_dict(self) -> Dict[str, Any]
    """Преобразовать в словарь"""
```

---

### 📂 `src/data/repositories/`

#### 📄 `src/data/repositories/base_repository.py`
**Назначение:** Базовый репозиторий с CRUD операциями

**Класс:**
```python
class BaseRepository[ModelType]:
    """Базовый репозиторий для всех моделей"""
    
    def __init__(self, model: Type[ModelType])
        """Инициализация с типом модели"""
```

**Методы:**
```python
async def create(self, session: AsyncSession, **kwargs) -> ModelType
    """Создать новую запись"""

async def get_by_id(self, session: AsyncSession, record_id: Any, load_relations: bool = False) -> Optional[ModelType]
    """Получить запись по ID"""

async def get_by_field(self, session: AsyncSession, field_name: str, field_value: Any, load_relations: bool = False) -> Optional[ModelType]
    """Получить запись по полю"""

async def get_all(self, session: AsyncSession, limit: Optional[int] = None, offset: Optional[int] = None, load_relations: bool = False) -> List[ModelType]
    """Получить все записи"""

async def update(self, session: AsyncSession, record_id: Any, **kwargs) -> Optional[ModelType]
    """Обновить запись по ID"""

async def delete(self, session: AsyncSession, record_id: Any) -> bool
    """Удалить запись по ID"""

async def count(self, session: AsyncSession, filters: Optional[Dict[str, Any]] = None) -> int
    """Подсчитать количество записей"""

async def exists(self, session: AsyncSession, **kwargs) -> bool
    """Проверить существование записи"""

async def search(self, session: AsyncSession, search_term: str, search_fields: List[str], limit: int = 10) -> List[ModelType]
    """Поиск записей по полям"""

async def get_paginated(self, session: AsyncSession, page: int, page_size: int, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
    """Получить записи с пагинацией"""

def _add_relationship_loading(self, stmt) -> Any
    """Добавить загрузку связанных объектов"""

def _apply_filters(self, stmt, filters: Dict[str, Any]) -> Any
    """Применить фильтры к запросу"""
```

#### 📄 `src/data/repositories/user_repository.py`
**Назначение:** Репозиторий для работы с пользователями

**Класс:**
```python
class UserRepository(BaseRepository[User]):
    """Репозиторий пользователей"""
```

**Методы:**
```python
async def create_user_from_telegram(self, session: AsyncSession, telegram_user: Any) -> User
    """Создать пользователя из данных Telegram"""

async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> Optional[User]
    """Получить пользователя по Telegram ID"""

async def update_user_settings(self, session: AsyncSession, user_id: int, **settings) -> Optional[User]
    """Обновить настройки пользователя"""

async def toggle_notifications(self, session: AsyncSession, user_id: int) -> bool
    """Переключить уведомления пользователя"""

async def mark_user_blocked(self, session: AsyncSession, user_id: int) -> bool
    """Отметить пользователя как заблокировавшего бота"""

async def mark_user_active(self, session: AsyncSession, user_id: int) -> bool
    """Отметить пользователя как активного"""

async def get_active_users(self, session: AsyncSession, with_notifications: bool = True) -> List[User]
    """Получить активных пользователей"""

async def get_users_with_pairs(self, session: AsyncSession, symbol: Optional[str] = None) -> List[User]
    """Получить пользователей с торговыми парами"""

async def get_user_statistics(self, session: AsyncSession, user_id: int) -> Dict[str, Any]
    """Получить статистику пользователя"""

async def increment_user_signals_count(self, session: AsyncSession, user_id: int) -> bool
    """Увеличить счетчик сигналов пользователя"""

async def get_users_summary(self, session: AsyncSession) -> Dict[str, Any]
    """Получить сводную статистику пользователей"""
```

#### 📄 `src/data/repositories/pair_repository.py`
**Назначение:** Репозиторий для работы с торговыми парами

**Класс:**
```python
class PairRepository(BaseRepository[Pair]):
    """Репозиторий торговых пар"""
```

**Методы:**
```python
async def create_pair_from_symbol(self, session: AsyncSession, symbol: str, price_precision: Optional[int] = None, quantity_precision: Optional[int] = None, is_active: bool = True) -> Pair
    """Создать торговую пару из символа"""

async def get_by_symbol(self, session: AsyncSession, symbol: str) -> Optional[Pair]
    """Получить пару по символу"""

async def get_or_create_pair(self, session: AsyncSession, symbol: str) -> Tuple[Pair, bool]
    """Получить существующую или создать новую пару"""

async def add_user_to_pair(self, session: AsyncSession, user_id: int, symbol: str, timeframes: Optional[Dict[str, bool]] = None) -> UserPair
    """Добавить пользователя к паре"""

async def remove_user_from_pair(self, session: AsyncSession, user_id: int, pair_id: int) -> bool
    """Удалить пользователя от пары"""

async def get_user_pairs(self, session: AsyncSession, user_id: int, load_pair_info: bool = True) -> List[UserPair]
    """Получить пары пользователя"""

async def get_tracked_pairs(self, session: AsyncSession) -> List[Pair]
    """Получить отслеживаемые пары для WebSocket"""

async def get_popular_pairs(self, session: AsyncSession, limit: int = 10) -> List[Pair]
    """Получить популярные пары"""

async def search_pairs_by_base_asset(self, session: AsyncSession, base_asset: str, limit: int = 10) -> List[Pair]
    """Найти пары по базовой валюте"""

async def increment_users_count(self, session: AsyncSession, pair_id: int) -> bool
    """Увеличить счетчик пользователей пары"""

async def decrement_users_count(self, session: AsyncSession, pair_id: int) -> bool
    """Уменьшить счетчик пользователей пары"""

async def increment_signals_count(self, session: AsyncSession, pair_id: int) -> bool
    """Увеличить счетчик сигналов пары"""

async def update_last_price(self, session: AsyncSession, pair_id: int, price: Decimal) -> bool
    """Обновить последнюю цену пары"""

async def get_pairs_summary(self, session: AsyncSession) -> Dict[str, Any]
    """Получить сводную статистику пар"""

async def cleanup_unused_pairs(self, session: AsyncSession, dry_run: bool = True) -> Dict[str, Any]
    """Очистка неиспользуемых пар"""
```

---

### 📂 `src/data/`

#### 📄 `src/data/database.py`
**Назначение:** Управление подключением к PostgreSQL

**Глобальные переменные:**
```python
engine: Optional[AsyncEngine] = None    # SQLAlchemy движок
SessionLocal: Optional[AsyncSessionmaker] = None  # Фабрика сессий
```

**Функции:**
```python
async def init_database() -> None
    """Инициализировать подключение к базе данных"""

async def close_database() -> None
    """Закрыть подключение к базе данных"""

async def check_database_connection() -> bool
    """Проверить подключение к базе данных"""

async def get_session() -> AsyncContextManager[AsyncSession]
    """Получить сессию базы данных (контекстный менеджер)"""

async def create_tables() -> None
    """Создать все таблицы в базе данных"""

async def drop_tables() -> None
    """Удалить все таблицы из базы данных"""

async def reset_database() -> None
    """Сбросить базу данных (удалить и создать заново)"""

def get_engine() -> Optional[AsyncEngine]
    """Получить текущий движок базы данных"""

async def execute_raw_query(query: str, params: Optional[Dict[str, Any]] = None) -> Any
    """Выполнить сырой SQL запрос"""
```

#### 📄 `src/data/redis_client.py`
**Назначение:** Управление подключением к Redis

**Глобальные переменные:**
```python
redis_client: Optional[Redis] = None    # Клиент Redis
```

**Функции:**
```python
async def init_redis() -> None
    """Инициализировать подключение к Redis"""

async def close_redis() -> None
    """Закрыть подключение к Redis"""

async def check_redis_connection() -> bool
    """Проверить подключение к Redis"""

async def get_redis() -> Optional[Redis]
    """Получить экземпляр Redis клиента"""

async def flush_redis() -> bool
    """Очистить все данные в Redis"""

async def get_redis_info() -> Dict[str, Any]
    """Получить информацию о Redis сервере"""

async def ping_redis() -> bool
    """Проверить доступность Redis через ping"""
```

---

## 🔧 SERVICES LAYER - БИЗНЕС ЛОГИКА

### 📂 `src/services/websocket/`

#### 📄 `src/services/websocket/binance_websocket.py`
**Назначение:** WebSocket клиент для Binance API

**Перечисления:**
```python
class ConnectionState(Enum):
    """Состояния WebSocket соединения"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"
```

**Класс:**
```python
class BinanceWebSocketClient(LoggerMixin):
    """WebSocket клиент для Binance"""
```

**Методы:**
```python
def __init__(self, message_handler: Optional[Callable] = None, error_handler: Optional[Callable] = None)
    """Инициализация клиента"""

async def connect(self) -> bool
    """Подключиться к WebSocket серверу"""

async def disconnect(self) -> None
    """Отключиться от WebSocket сервера"""

async def subscribe_to_streams(self, streams: List[str]) -> bool
    """Подписаться на потоки данных"""

async def unsubscribe_from_streams(self, streams: List[str]) -> bool
    """Отписаться от потоков данных"""

async def send_ping(self) -> bool
    """Отправить ping сообщение"""

async def handle_message(self, message: str) -> None
    """Обработать входящее сообщение"""

async def handle_error(self, error: Exception) -> None
    """Обработать ошибку подключения"""

async def reconnect(self) -> bool
    """Переподключиться при разрыве соединения"""

async def start_ping_task(self) -> None
    """Запустить задачу отправки ping"""

async def stop_ping_task(self) -> None
    """Остановить задачу отправки ping"""

def get_connection_state(self) -> ConnectionState
    """Получить текущее состояние подключения"""

def is_connected(self) -> bool
    """Проверить подключен ли клиент"""

async def close(self) -> None
    """Закрыть соединение и очистить ресурсы"""
```

#### 📄 `src/services/websocket/stream_manager.py`
**Назначение:** Управление потоками WebSocket данных

**Вспомогательные функции:**
```python
def get_kline_stream_name(symbol: str, timeframe: str) -> str
    """Получить имя потока для kline данных"""

def get_ticker_stream_name(symbol: str) -> str
    """Получить имя потока для ticker данных"""

def get_depth_stream_name(symbol: str, level: str = "5") -> str
    """Получить имя потока для depth данных"""

def parse_stream_name(stream_name: str) -> dict
    """Разобрать имя потока на компоненты"""
```

**Класс:**
```python
class StreamManager:
    """Менеджер WebSocket потоков"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация менеджера потоков"""

async def start(self) -> bool
    """Запустить менеджер потоков"""

async def stop(self) -> None
    """Остановить менеджер потоков"""

async def add_symbol_stream(self, symbol: str, timeframes: List[str]) -> bool
    """Добавить потоки для символа"""

async def remove_symbol_stream(self, symbol: str) -> bool
    """Удалить потоки для символа"""

async def update_subscriptions(self) -> bool
    """Обновить подписки на основе активных пользователей"""

async def get_active_streams(self) -> List[str]
    """Получить список активных потоков"""

async def get_required_streams(self) -> List[str]
    """Получить список необходимых потоков из БД"""

async def handle_websocket_message(self, message: Dict[str, Any]) -> None
    """Обработать сообщение от WebSocket"""

async def handle_websocket_error(self, error: Exception) -> None
    """Обработать ошибку WebSocket"""

def get_stream_statistics(self) -> Dict[str, Any]
    """Получить статистику потоков"""

def is_running(self) -> bool
    """Проверить работает ли менеджер"""
```

#### 📄 `src/services/websocket/binance_data_processor.py`
**Назначение:** Обработка данных от Binance WebSocket

**Класс:**
```python
class BinanceDataProcessor:
    """Обработчик данных от Binance WebSocket"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация обработчика"""

async def process_websocket_message(self, message: Dict[str, Any]) -> None
    """Обработать сообщение от WebSocket"""

async def _process_kline_message(self, stream_name: str, data: Dict[str, Any]) -> None
    """Обработать kline сообщение"""

async def _process_ticker_message(self, stream_name: str, data: Dict[str, Any]) -> None
    """Обработать ticker сообщение"""

async def _extract_symbol_timeframe(self, stream_name: str) -> Tuple[str, str]
    """Извлечь символ и таймфрейм из имени потока"""

async def _validate_kline_data(self, data: Dict[str, Any]) -> bool
    """Валидировать kline данные"""

async def _convert_kline_to_candle(self, data: Dict[str, Any]) -> Dict[str, Any]
    """Конвертировать kline данные в формат свечи"""

async def _process_candle_data(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]) -> None
    """Обработать данные свечи через систему сигналов"""

def get_processing_stats(self) -> Dict[str, Any]
    """Получить статистику обработки"""

def reset_stats(self) -> None
    """Сбросить статистику доставки"""
```

#### 📄 `src/services/notifications/message_formatter.py`
**Назначение:** Форматирование уведомлений и сообщений

**Класс:**
```python
class MessageFormatter:
    """Сервис форматирования сообщений"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация форматировщика"""

def format_signal_message(self, symbol: str, timeframe: str, price: float, price_change_percent: Optional[float] = None, rsi_value: Optional[float] = None, rsi_signal_type: Optional[str] = None, volume_change_percent: Optional[float] = None, ema_trend: Optional[str] = None, signal_type: str = "rsi_signal") -> str
    """Форматировать сообщение о сигнале"""

def format_rsi_signal(self, symbol: str, timeframe: str, rsi_value: float, signal_type: str, price: float, volume_change: Optional[float] = None) -> str
    """Форматировать RSI сигнал"""

def format_ema_signal(self, symbol: str, timeframe: str, ema_data: Dict[str, Any], price: float) -> str
    """Форматировать EMA сигнал"""

def format_price(self, price: float, precision: int = 8) -> str
    """Форматировать цену"""

def format_percentage(self, percentage: float, precision: int = 2) -> str
    """Форматировать процентное значение"""

def format_volume_change(self, volume_change: float) -> str
    """Форматировать изменение объема"""

def get_signal_emoji(self, signal_type: str) -> str
    """Получить эмодзи для типа сигнала"""

def get_trend_emoji(self, trend: str) -> str
    """Получить эмодзи для тренда"""

def get_timeframe_display(self, timeframe: str) -> str
    """Получить отображаемое название таймфрейма"""

def create_signal_header(self, signal_type: str, symbol: str, timeframe: str) -> str
    """Создать заголовок сигнала"""

def create_price_section(self, price: float, price_change: Optional[float] = None) -> str
    """Создать секцию с ценой"""

def create_indicator_section(self, rsi_value: Optional[float] = None, ema_data: Optional[Dict] = None) -> str
    """Создать секцию с индикаторами"""

def create_volume_section(self, volume_change: Optional[float] = None) -> str
    """Создать секцию с объемом"""

def create_footer_section(self) -> str
    """Создать подвал сообщения"""
```

**Глобальная функция:**
```python
def format_signal_message(symbol: str, timeframe: str, signal_data: Dict[str, Any]) -> str
    """Глобальная функция форматирования сигнала"""
```

#### 📄 `src/services/notifications/notification_queue.py`
**Назначение:** Очередь уведомлений для асинхронной отправки

**Класс:**
```python
class NotificationQueue:
    """Очередь уведомлений"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация очереди"""

async def start_processing(self) -> None
    """Запустить обработку очереди"""

async def stop_processing(self) -> None
    """Остановить обработку очереди"""

async def add_notification(self, user_id: int, message: str, reply_markup: Optional[InlineKeyboardMarkup] = None, priority: int = 0) -> None
    """Добавить уведомление в очередь"""

async def add_signal_notification(self, user_id: int, signal_data: Dict[str, Any]) -> None
    """Добавить уведомление о сигнале"""

async def process_notifications(self) -> None
    """Обработать уведомления из очереди"""

async def _process_single_notification(self, notification: Dict[str, Any]) -> bool
    """Обработать одно уведомление"""

async def _handle_processing_error(self, notification: Dict[str, Any], error: Exception) -> None
    """Обработать ошибку при отправке"""

def get_queue_stats(self) -> Dict[str, Any]
    """Получить статистику очереди"""

def get_queue_size(self) -> int
    """Получить размер очереди"""

def is_processing(self) -> bool
    """Проверить обрабатывается ли очередь"""

async def clear_queue(self) -> int
    """Очистить очередь"""

async def retry_failed_notifications(self) -> int
    """Повторить неудачные уведомления"""
```

**Глобальный экземпляр:** `notification_queue = NotificationQueue()`

---

### 📂 `src/services/cache/`

#### 📄 `src/services/cache/candle_cache.py`
**Назначение:** Кеш для свечных данных в Redis

**Класс:**
```python
class CandleCache:
    """Кеш свечных данных в Redis"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация кеша свечей"""

async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]
    """Получить свечи из кеша"""

async def add_new_candle(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]) -> bool
    """Добавить новую свечу в кеш"""

async def update_last_candle(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]) -> bool
    """Обновить последнюю (текущую) свечу"""

async def cache_historical_data(self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]) -> bool
    """Кешировать исторические данные"""

async def clear_cache(self, symbol: str, timeframe: Optional[str] = None) -> bool
    """Очистить кеш для символа"""

async def get_last_candle(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]
    """Получить последнюю свечу"""

async def get_candles_count(self, symbol: str, timeframe: str) -> int
    """Получить количество свечей в кеше"""

def _get_cache_key(self, symbol: str, timeframe: str) -> str
    """Получить ключ кеша для свечей"""

def _serialize_candle(self, candle_data: Dict[str, Any]) -> str
    """Сериализовать свечу для Redis"""

def _deserialize_candle(self, candle_str: str) -> Dict[str, Any]
    """Десериализовать свечу из Redis"""

async def _trim_cache(self, cache_key: str, max_size: int = 500) -> None
    """Обрезать кеш до максимального размера"""

async def get_cache_stats(self) -> Dict[str, Any]
    """Получить статистику кеша"""

async def warm_up_cache(self, symbols: List[str], timeframes: List[str]) -> Dict[str, bool]
    """Прогреть кеш для символов и таймфреймов"""
```

**Глобальный экземпляр:** `candle_cache = CandleCache()`

#### 📄 `src/services/cache/indicator_cache.py`
**Назначение:** Кеш для значений индикаторов

**Класс:**
```python
class IndicatorCache:
    """Кеш индикаторов в Redis"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация кеша индикаторов"""

async def get_rsi(self, symbol: str, timeframe: str, period: int = 14) -> Optional[float]
    """Получить значение RSI из кеша"""

async def set_rsi(self, symbol: str, timeframe: str, period: int, value: float, ttl: int = 300) -> bool
    """Сохранить значение RSI в кеш"""

async def get_ema(self, symbol: str, timeframe: str, period: int) -> Optional[float]
    """Получить значение EMA из кеша"""

async def set_ema(self, symbol: str, timeframe: str, period: int, value: float, ttl: int = 300) -> bool
    """Сохранить значение EMA в кеш"""

async def get_volume_change(self, symbol: str, timeframe: str) -> Optional[float]
    """Получить изменение объема из кеша"""

async def set_volume_change(self, symbol: str, timeframe: str, value: float, ttl: int = 120) -> bool
    """Сохранить изменение объема в кеш"""

async def get_all_indicators(self, symbol: str, timeframe: str) -> Dict[str, Any]
    """Получить все индикаторы для символа и таймфрейма"""

async def invalidate_indicators(self, symbol: str, timeframe: Optional[str] = None) -> bool
    """Инвалидировать кеш индикаторов"""

def _get_rsi_key(self, symbol: str, timeframe: str, period: int) -> str
    """Получить ключ для RSI"""

def _get_ema_key(self, symbol: str, timeframe: str, period: int) -> str
    """Получить ключ для EMA"""

def _get_volume_key(self, symbol: str, timeframe: str) -> str
    """Получить ключ для изменения объема"""

async def get_cache_stats(self) -> Dict[str, Any]
    """Получить статистику кеша индикаторов"""

async def cleanup_expired_indicators(self) -> int
    """Очистить просроченные индикаторы"""
```

**Глобальный экземпляр:** `indicator_cache = IndicatorCache()`

---

### 📂 `src/services/data_fetchers/`

#### 📄 `src/services/data_fetchers/pair_validator.py`
**Назначение:** Валидация торговых пар через Binance API

**Класс:**
```python
class PairValidator:
    """Валидатор торговых пар"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация валидатора"""

async def validate_pair(self, symbol: str) -> Dict[str, Any]
    """Валидировать торговую пару через Binance API"""

async def get_pair_info(self, symbol: str) -> Optional[Dict[str, Any]]
    """Получить информацию о паре"""

async def check_pair_exists(self, symbol: str) -> bool
    """Проверить существование пары на Binance"""

async def get_trading_rules(self, symbol: str) -> Optional[Dict[str, Any]]
    """Получить правила торговли для пары"""

async def get_all_trading_pairs(self) -> List[str]
    """Получить все доступные торговые пары"""

async def search_pairs(self, query: str, limit: int = 10) -> List[str]
    """Поиск пар по запросу"""

def _normalize_symbol(self, symbol: str) -> str
    """Нормализовать символ пары"""

async def _fetch_exchange_info(self) -> Dict[str, Any]
    """Получить информацию о бирже"""

def _extract_pair_info(self, symbol_info: Dict[str, Any]) -> Dict[str, Any]
    """Извлечь информацию о паре из ответа API"""

async def _cache_exchange_info(self, exchange_info: Dict[str, Any]) -> None
    """Кешировать информацию о бирже"""
```

---

### 📂 `src/services/data_fetchers/historical/`

#### 📄 `src/services/data_fetchers/historical/historical_fetcher.py`
**Назначение:** Загрузчик исторических данных

**Класс:**
```python
class HistoricalDataFetcher:
    """Загрузчик исторических данных"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация загрузчика"""

async def fetch_historical_candles(self, symbol: str, timeframe: str, limit: int = 500, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]
    """Загрузить исторические свечи"""

async def fetch_for_all_timeframes(self, symbol: str, timeframes: List[str], limit: int = 500) -> Dict[str, List[Dict[str, Any]]]
    """Загрузить данные для всех таймфреймов"""

async def fetch_and_cache(self, symbol: str, timeframe: str, limit: int = 500) -> bool
    """Загрузить и кешировать исторические данные"""

async def update_latest_candles(self, symbol: str, timeframes: List[str]) -> Dict[str, bool]
    """Обновить последние свечи"""

def _calculate_start_time(self, timeframe: str, limit: int) -> int
    """Рассчитать время начала для загрузки"""

async def _validate_fetched_data(self, data: List[Dict[str, Any]]) -> bool
    """Валидировать загруженные данные"""

async def _save_to_database(self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]) -> bool
    """Сохранить данные в базу данных"""
```

#### 📄 `src/services/data_fetchers/historical/historical_api_client.py`
**Назначение:** API клиент для исторических данных

**Класс:**
```python
class HistoricalAPIClient:
    """API клиент для получения исторических данных"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация API клиента"""

async def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List[Any]]
    """Получить klines через REST API"""

async def get_24hr_ticker(self, symbol: str) -> Dict[str, Any]
    """Получить 24-часовую статистику"""

async def get_exchange_info(self) -> Dict[str, Any]
    """Получить информацию о бирже"""

async def ping(self) -> bool
    """Проверить доступность API"""

def _build_klines_url(self, symbol: str, interval: str, limit: int, start_time: Optional[int], end_time: Optional[int]) -> str
    """Построить URL для klines запроса"""

async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
    """Выполнить HTTP запрос"""

def _handle_api_error(self, response: Dict[str, Any]) -> None
    """Обработать ошибку API"""

async def _rate_limit_handler(self) -> None
    """Обработчик ограничений по частоте запросов"""
```

#### 📄 `src/services/data_fetchers/historical/historical_data_processor.py`
**Назначение:** Обработчик исторических данных

**Класс:**
```python
class HistoricalDataProcessor:
    """Обработчик исторических данных"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация обработчика"""

async def process_and_save(self, symbol: str, timeframe: str, raw_data: List[List[Any]]) -> bool
    """Обработать и сохранить сырые данные"""

def convert_kline_to_candle(self, kline_data: List[Any]) -> Dict[str, Any]
    """Конвертировать kline в формат свечи"""

async def validate_data_integrity(self, candles: List[Dict[str, Any]], timeframe: str) -> bool
    """Валидировать целостность данных"""

def fill_missing_candles(self, candles: List[Dict[str, Any]], timeframe: str) -> List[Dict[str, Any]]
    """Заполнить пропущенные свечи"""

async def save_to_database(self, pair_id: int, timeframe: str, candles: List[Dict[str, Any]]) -> int
    """Сохранить свечи в базу данных"""

async def save_to_cache(self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]) -> bool
    """Сохранить свечи в кеш"""

def _sort_candles_by_time(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Отсортировать свечи по времени"""

def _remove_duplicates(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Удалить дублирующиеся свечи"""

def _validate_candle_data(self, candle: Dict[str, Any]) -> bool
    """Валидировать данные одной свечи"""
```

---

## 🛠️ UTILS LAYER - УТИЛИТЫ

### 📄 `src/utils/constants.py`
**Назначение:** Все константы приложения

**Основные константы:**
```python
# Информация о приложении
APP_NAME: str = "CryptoBot"
APP_VERSION: str = "1.0.0"

# Binance константы
BINANCE_TIMEFRAMES: List[str] = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
TIMEFRAME_TO_MS: Dict[str, int] = {...}  # Конвертация в миллисекунды
TIMEFRAME_NAMES: Dict[str, str] = {...}  # Человекочитаемые названия

# Индикаторы
RSI_PERIODS: List[int] = [14, 21, 30]
EMA_PERIODS: List[int] = [20, 50, 100, 200]

# Эмодзи
EMOJI: Dict[str, str] = {...}
SIGNAL_EMOJIS: Dict[str, str] = {...}
TREND_EMOJIS: Dict[str, str] = {...}

# Валюты
CURRENCY_SYMBOLS: Dict[str, str] = {...}
QUOTE_ASSETS: List[str] = ["USDT", "BUSD", "BTC", "ETH", "BNB"]

# Интервалы повтора сигналов
SIGNAL_REPEAT_INTERVALS: Dict[str, int] = {...}

# Регулярные выражения
REGEX_PATTERNS: Dict[str, str] = {...}

# Лимиты
MIN_SYMBOL_LENGTH: int = 3
MAX_SYMBOL_LENGTH: int = 20
MAX_PAIRS_PER_USER: int = 50
```

**Функции:**
```python
def get_timeframe_ms(timeframe: str) -> int
    """Получить количество миллисекунд для таймфрейма"""

def get_signal_emoji(signal_type: str) -> str
    """Получить эмодзи для типа сигнала"""

def get_currency_symbol(currency: str) -> str
    """Получить символ валюты"""

def is_valid_timeframe(timeframe: str) -> bool
    """Проверить валидность таймфрейма"""

def get_repeat_interval(signal_type: str) -> int
    """Получить интервал повторения для типа сигнала"""
```

### 📄 `src/utils/exceptions.py`
**Назначение:** Кастомные исключения

**Базовое исключение:**
```python
class CryptoBotError(Exception):
    """Базовое исключение для крипто-бота"""
```

**Исключения конфигурации:**
```python
class ConfigurationError(CryptoBotError):
    """Ошибки конфигурации"""

class InvalidConfigValueError(ConfigurationError):
    """Неверное значение конфигурации"""

class MissingConfigError(ConfigurationError):
    """Отсутствующая конфигурация"""
```

**Исключения базы данных:**
```python
class DatabaseError(CryptoBotError):
    """Ошибки базы данных"""

class ConnectionError(DatabaseError):
    """Ошибка подключения к БД"""

class RecordNotFoundError(DatabaseError):
    """Запись не найдена"""

class RecordAlreadyExistsError(DatabaseError):
    """Запись уже существует"""

class ValidationError(DatabaseError):
    """Ошибка валидации данных"""
```

**Исключения Redis:**
```python
class RedisError(CryptoBotError):
    """Ошибки Redis"""

class RedisConnectionError(RedisError):
    """Ошибка подключения к Redis"""

class CacheError(RedisError):
    """Ошибка кеширования"""
```

**Исключения WebSocket:**
```python
class WebSocketConnectionError(CryptoBotError):
    """Ошибка WebSocket подключения"""

class WebSocketReconnectError(WebSocketConnectionError):
    """Ошибка переподключения WebSocket"""

class StreamError(WebSocketConnectionError):
    """Ошибка потока данных"""
```

**Исключения Binance API:**
```python
class BinanceAPIError(CryptoBotError):
    """Ошибки Binance API"""

class BinanceDataError(BinanceAPIError):
    """Ошибка данных от Binance"""

class RateLimitError(BinanceAPIError):
    """Превышен лимит запросов"""

class InvalidSymbolError(BinanceAPIError):
    """Неверный символ торговой пары"""
```

**Исключения сигналов:**
```python
class SignalError(CryptoBotError):
    """Ошибки генерации сигналов"""

class IndicatorCalculationError(SignalError):
    """Ошибка расчета индикатора"""

class NotificationError(SignalError):
    """Ошибка отправки уведомления"""
```

### 📄 `src/utils/validators.py`
**Назначение:** Валидаторы входных данных

**Функции валидации символов:**
```python
def validate_trading_pair_symbol(symbol: str) -> tuple[bool, Optional[str]]
    """Валидировать символ торговой пары"""

def extract_base_quote_assets(symbol: str) -> Optional[Tuple[str, str]]
    """Извлечь базовую и котируемую валюты из символа"""

def normalize_trading_symbol(symbol: str) -> str
    """Нормализовать символ торговой пары"""
```

**Функции валидации таймфреймов:**
```python
def validate_timeframe(timeframe: str) -> tuple[bool, Optional[str]]
    """Валидировать таймфрейм"""

def validate_timeframes_config(timeframes_config: dict) -> tuple[bool, Optional[str]]
    """Валидировать конфигурацию таймфреймов пользователя"""
```

**Функции валидации цен и объемов:**
```python
def validate_price(price: Union[str, float, Decimal]) -> tuple[bool, Optional[str]]
    """Валидировать цену"""

def validate_volume(volume: Union[str, float, Decimal]) -> tuple[bool, Optional[str]]
    """Валидировать объем торгов"""

def validate_percentage(percentage: Union[str, float]) -> tuple[bool, Optional[str]]
    """Валидировать процентное значение"""
```

**Функции валидации пользователей:**
```python
def validate_user_id(user_id: Union[str, int]) -> tuple[bool, Optional[str]]
    """Валидировать ID пользователя Telegram"""

def validate_username(username: str) -> tuple[bool, Optional[str]]
    """Валидировать имя пользователя"""
```

**Функции валидации индикаторов:**
```python
def validate_rsi_value(rsi: Union[str, float]) -> tuple[bool, Optional[str]]
    """Валидировать значение RSI"""

def validate_ema_period(period: Union[str, int]) -> tuple[bool, Optional[str]]
    """Валидировать период EMA"""

def validate_signal_type(signal_type: str) -> tuple[bool, Optional[str]]
    """Валидировать тип сигнала"""
```

**Функции валидации данных Binance:**
```python
def validate_binance_kline_data(kline_data: Dict[str, Any]) -> tuple[bool, str]
    """Валидировать данные kline от Binance"""

def validate_binance_kline_data_detailed(kline_data: Dict[str, Any]) -> tuple[bool, str]
    """Детальная валидация данных kline от Binance"""

def validate_websocket_message(message: Dict[str, Any]) -> tuple[bool, str]
    """Валидировать сообщение WebSocket"""
```

### 📄 `src/utils/time_helpers.py`
**Назначение:** Функции для работы со временем

**Функции временных меток:**
```python
def get_current_timestamp() -> int
    """Получить текущую временную метку в миллисекундах"""

def get_current_timestamp_seconds() -> int
    """Получить текущий Unix timestamp в секундах"""

def timestamp_to_datetime(timestamp: int, in_milliseconds: bool = True) -> datetime
    """Преобразовать Unix timestamp в datetime объект"""

def datetime_to_timestamp(dt: datetime, in_milliseconds: bool = True) -> int
    """Преобразовать datetime в Unix timestamp"""
```

**Функции таймфреймов:**
```python
def timeframe_to_milliseconds(timeframe: str) -> Optional[int]
    """Получить количество миллисекунд для таймфрейма"""

def timeframe_to_seconds(timeframe: str) -> Optional[int]
    """Получить количество секунд для таймфрейма"""

def get_timeframe_display_name(timeframe: str) -> str
    """Получить человекочитаемое название таймфрейма"""

def align_timestamp_to_timeframe(timestamp: int, timeframe: str) -> int
    """Выровнять timestamp по границе таймфрейма"""

def calculate_time_until_next_candle(timeframe: str, current_time: Optional[int] = None) -> int
    """Рассчитать время до следующей свечи"""

def get_candle_open_time(timestamp: int, timeframe: str) -> int
    """Получить время открытия свечи для timestamp"""

def get_candle_close_time(timestamp: int, timeframe: str) -> int
    """Получить время закрытия свечи для timestamp"""
```

**Функции работы с диапазонами времени:**
```python
def get_time_range_for_candles(timeframe: str, count: int, end_time: Optional[int] = None) -> Tuple[int, int]
    """Получить диапазон времени для определенного количества свечей"""

def split_time_range(start_time: int, end_time: int, timeframe: str, max_candles: int = 1000) -> List[Tuple[int, int]]
    """Разбить большой диапазон времени на части"""

def format_duration(seconds: int) -> str
    """Форматировать продолжительность в читаемый вид"""

def parse_duration_string(duration_str: str) -> int
    """Разобрать строку продолжительности в секунды"""
```

### 📄 `src/utils/math_helpers.py`
**Назначение:** Математические функции для расчетов

**Базовые математические функции:**
```python
def safe_divide(dividend: Union[float, Decimal], divisor: Union[float, Decimal]) -> float
    """Безопасное деление с обработкой деления на ноль"""

def calculate_percentage_change(old_value: float, new_value: float) -> float
    """Рассчитать процентное изменение между двумя значениями"""

def round_to_precision(value: Union[float, Decimal], precision: int) -> float
    """Округлить значение до указанной точности"""

def clamp_value(value: float, min_value: float, max_value: float) -> float
    """Ограничить значение диапазоном"""

def normalize_to_range(value: float, from_min: float, from_max: float, to_min: float, to_max: float) -> float
    """Нормализовать значение к новому диапазону"""
```

**Функции скользящих средних:**
```python
def calculate_simple_moving_average(values: List[float], period: int) -> Optional[float]
    """Рассчитать простое скользящее среднее (SMA)"""

def calculate_exponential_moving_average(values: List[float], period: int, previous_ema: Optional[float] = None) -> Optional[float]
    """Рассчитать экспоненциальное скользящее среднее (EMA)"""

def calculate_weighted_moving_average(values: List[float], period: int) -> Optional[float]
    """Рассчитать взвешенное скользящее среднее (WMA)"""
```

**Функции для индикаторов:**
```python
def calculate_rsi_basic(prices: List[float], period: int = 14) -> Optional[float]
    """Базовый алгоритм расчета RSI"""

def calculate_true_range(high: float, low: float, previous_close: float) -> float
    """Рассчитать истинный диапазон (True Range)"""

def calculate_average_true_range(true_ranges: List[float], period: int = 14) -> Optional[float]
    """Рассчитать средний истинный диапазон (ATR)"""

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[Tuple[float, float, float]]
    """Рассчитать полосы Боллинджера"""
```

**Статистические функции:**
```python
def calculate_standard_deviation(values: List[float]) -> float
    """Рассчитать стандартное отклонение"""

def calculate_variance(values: List[float]) -> float
    """Рассчитать дисперсию"""

def calculate_correlation(x_values: List[float], y_values: List[float]) -> float
    """Рассчитать корреляцию между двумя рядами"""

def find_peaks(values: List[float], min_height: Optional[float] = None) -> List[int]
    """Найти пики в ряду значений"""

def find_troughs(values: List[float], max_height: Optional[float] = None) -> List[int]
    """Найти впадины в ряду значений"""
```

### 📄 `src/utils/logger.py`
**Назначение:** Система логирования

**Функции настройки:**
```python
def setup_logging(log_level: Optional[str] = None, json_logs: bool = False, log_file: Optional[str] = None) -> None
    """Настроить систему логирования"""

def get_logger(name: str) -> Any
    """Получить логгер для модуля"""

def configure_structlog() -> None
    """Настроить структурированное логирование"""

def setup_file_logging(log_file: str) -> None
    """Настроить логирование в файл"""

def setup_console_logging() -> None
    """Настроить консольное логирование"""
```

**Функции логирования событий:**
```python
def log_user_action(action: str, user_id: int, **kwargs) -> None
    """Логировать действие пользователя"""

def log_database_operation(operation: str, table: str, **kwargs) -> None
    """Логировать операцию с базой данных"""

def log_websocket_event(event: str, **kwargs) -> None
    """Логировать WebSocket событие"""

def log_signal_generated(signal_type: str, symbol: str, timeframe: str, **kwargs) -> None
    """Логировать генерацию сигнала"""

def log_notification_sent(user_id: int, notification_type: str, success: bool, **kwargs) -> None
    """Логировать отправку уведомления"""

def log_api_request(endpoint: str, method: str, status_code: int, **kwargs) -> None
    """Логировать API запрос"""

def log_cache_operation(operation: str, key: str, hit: bool = None, **kwargs) -> None
    """Логировать операцию с кешем"""
```

**Классы:**
```python
class LoggerMixin:
    """Миксин для добавления логирования в классы"""
    
    @property
    def logger(self) -> Any
        """Получить логгер для класса"""
    
    def log_info(self, message: str, **kwargs) -> None
        """Логировать информационное сообщение"""
    
    def log_error(self, message: str, error: Optional[Exception] = None, **kwargs) -> None
        """Логировать ошибку"""
    
    def log_warning(self, message: str, **kwargs) -> None
        """Логировать предупреждение"""
    
    def log_debug(self, message: str, **kwargs) -> None
        """Логировать отладочное сообщение"""
```

---

## ⚙️ CONFIG LAYER - КОНФИГУРАЦИЯ

### 📄 `src/config/bot_config.py`
**Назначение:** Конфигурация Telegram бота

**Класс конфигурации:**
```python
class BotConfig(BaseSettings):
    """Конфигурация Telegram бота"""
    
    # Основные настройки
    bot_token: str                              # Токен бота
    debug: bool                                 # Режим отладки
    log_level: str                              # Уровень логирования
    max_connections: int                        # Максимум подключений
    request_timeout: int                        # Таймаут запросов
    
    # Настройки уведомлений
    notification_rate_limit: int               # Лимит уведомлений
    signal_check_interval: int                 # Интервал проверки сигналов
    
    # Дефолтные настройки
    default_timeframes: List[str]              # Дефолтные таймфреймы
    default_pair: str                          # Дефолтная пара
    rsi_period: int                            # Период RSI
    ema_periods: List[int]                     # Периоды EMA
    
    # Зоны RSI
    rsi_oversold_strong: float                 # Сильная перепроданность
    rsi_oversold_medium: float                 # Средняя перепроданность
    rsi_oversold_normal: float                 # Обычная перепроданность
    rsi_overbought_normal: float               # Обычная перекупленность
    rsi_overbought_medium: float               # Средняя перекупленность
    rsi_overbought_strong: float               # Сильная перекупленность
    
    # Интервалы повтора сигналов
    signal_repeat_interval: int                # Интервал повтора
```

**Функции:**
```python
def get_bot_config() -> BotConfig
    """Получить конфигурацию бота"""

def is_debug_mode() -> bool
    """Проверить включен ли режим отладки"""

def get_rsi_zones() -> Dict[str, float]
    """Получить зоны RSI для генерации сигналов"""

def validate_config() -> None
    """Валидировать конфигурацию бота"""

def get_default_timeframes() -> List[str]
    """Получить дефолтные таймфреймы"""

def get_notification_settings() -> Dict[str, Any]
    """Получить настройки уведомлений"""
```

### 📄 `src/config/database_config.py`
**Назначение:** Конфигурация PostgreSQL

**Класс конфигурации:**
```python
class DatabaseConfig(BaseSettings):
    """Конфигурация базы данных"""
    
    # Подключение
    database_url: str                          # URL подключения
    host: str                                  # Хост БД
    port: int                                  # Порт БД
    name: str                                  # Имя БД
    user: str                                  # Пользователь БД
    password: str                              # Пароль БД
    
    # Настройки пула соединений
    pool_size: int                             # Размер пула
    max_overflow: int                          # Максимальное переполнение
    pool_timeout: int                          # Таймаут пула
    pool_recycle: int                          # Время переиспользования
    
    # Настройки подключения
    connect_timeout: int                       # Таймаут подключения
    command_timeout: int                       # Таймаут команды
    
    # SSL настройки
    ssl_mode: str                              # Режим SSL
    ssl_cert: Optional[str]                    # SSL сертификат
    ssl_key: Optional[str]                     # SSL ключ
    
    # Настройки логирования SQL
    echo_sql: bool                             # Логировать SQL запросы
    echo_pool: bool                            # Логировать пул соединений
```

**Функции:**
```python
def get_database_config() -> DatabaseConfig
    """Получить конфигурацию базы данных"""

def get_database_url(test_mode: bool = False) -> str
    """Получить URL подключения к БД"""

def get_sqlalchemy_engine_args() -> Dict[str, Any]
    """Получить аргументы для SQLAlchemy engine"""

def validate_database_config() -> None
    """Валидировать конфигурацию БД"""

def get_connection_pool_settings() -> Dict[str, Any]
    """Получить настройки пула соединений"""
```

### 📄 `src/config/redis_config.py`
**Назначение:** Конфигурация Redis

**Класс конфигурации:**
```python
class RedisConfig(BaseSettings):
    """Конфигурация Redis"""
    
    # Подключение
    redis_url: Optional[str]                   # URL подключения
    host: str                                  # Хост Redis
    port: int                                  # Порт Redis
    db: int                                    # Номер БД
    password: Optional[str]                    # Пароль Redis
    
    # Настройки подключения
    socket_timeout: int                        # Таймаут сокета
    socket_connect_timeout: int                # Таймаут подключения
    socket_keepalive: bool                     # Keep-alive
    socket_keepalive_options: Dict[str, int]   # Опции keep-alive
    
    # Настройки пула
    max_connections: int                       # Максимум подключений
    retry_on_timeout: bool                     # Повтор при таймауте
    
    # Настройки кодирования
    encoding: str                              # Кодировка
    decode_responses: bool                     # Декодировать ответы
    
    # Настройки кеша
    key_prefix: str                            # Префикс ключей
    default_ttl: int                           # TTL по умолчанию
```

**Тестовая конфигурация:**
```python
class TestRedisConfig(RedisConfig):
    """Конфигурация тестового Redis"""
    
    db: int                                    # Используем другую БД для тестов
    key_prefix: str                            # Тестовый префикс
```

**Функции:**
```python
def get_redis_config() -> RedisConfig
    """Получить конфигурацию основного Redis"""

def get_test_redis_config() -> TestRedisConfig
    """Получить конфигурацию тестового Redis"""

def get_redis_url(test_mode: bool = False) -> str
    """Получить URL подключения к Redis"""

def get_redis_connection_params(test_mode: bool = False) -> dict
    """Получить параметры подключения к Redis"""

def get_cache_key(key_type: str, *args, test_mode: bool = False) -> str
    """Сгенерировать ключ для кеша с префиксом"""

def validate_redis_config() -> None
    """Валидировать конфигурацию Redis"""
```

### 📄 `src/config/binance_config.py`
**Назначение:** Конфигурация Binance API

**Класс конфигурации:**
```python
class BinanceConfig(BaseSettings):
    """Конфигурация Binance API"""
    
    # URL endpoints
    websocket_url: str                         # WebSocket URL
    rest_api_url: str                          # REST API URL
    
    # Настройки WebSocket
    reconnect_interval: int                    # Интервал переподключения
    ping_interval: int                         # Интервал ping
    connection_timeout: int                    # Таймаут подключения
    max_reconnect_attempts: int                # Максимум попыток переподключения
    
    # Настройки REST API
    request_timeout: int                       # Таймаут запроса
    rate_limit_per_minute: int                 # Лимит запросов в минуту
    
    # Настройки данных
    max_klines_per_request: int                # Максимум klines за запрос
    historical_data_batch_size: int           # Размер батча исторических данных
```

**Функции:**
```python
def get_binance_config() -> BinanceConfig
    """Получить конфигурацию Binance"""

def get_websocket_url() -> str
    """Получить URL WebSocket"""

def get_rest_api_url() -> str
    """Получить URL REST API"""

def validate_binance_config() -> None
    """Валидировать конфигурацию Binance"""

def get_connection_settings() -> Dict[str, Any]
    """Получить настройки подключения"""

def get_rate_limit_settings() -> Dict[str, Any]
    """Получить настройки лимитов"""
```

### 📄 `src/config/logging_config.py`
**Назначение:** Конфигурация логирования

**Функции:**
```python
def get_logging_config() -> Dict[str, Any]
    """Получить конфигурацию логирования"""

def setup_structlog() -> None
    """Настроить структурированное логирование"""

def configure_file_logging(log_file: str, log_level: str = "INFO") -> None
    """Настроить логирование в файлы"""

def configure_console_logging(log_level: str = "INFO") -> None
    """Настроить консольное логирование"""

def get_log_formatters() -> Dict[str, Any]
    """Получить форматировщики логов"""

def setup_rotating_file_handler(log_file: str, max_bytes: int = 10485760, backup_count: int = 5) -> None
    """Настроить ротацию лог файлов"""
```

---

## 📁 ВСПОМОГАТЕЛЬНЫЕ ФАЙЛЫ

### 📄 `.env.example`
**Назначение:** Пример файла переменных окружения

**Переменные:**
```bash
# Telegram Bot Configuration
BOT_TOKEN=7826210826:AAGUqh1MgxC8M0_gj-u6k6fmRjRMKqJbFLg

# Database Configuration  
DATABASE_URL=postgresql://crypto_user:crypto_pass@postgres:5432/crypto_bot
DB_HOST=postgres
DB_PORT=5432
DB_NAME=crypto_bot
DB_USER=crypto_user
DB_PASSWORD=crypto_pass

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Binance API Configuration
BINANCE_BASE_URL=wss://stream.binance.com:9443/ws
BINANCE_REST_URL=https://api.binance.com

# Application Settings
DEBUG=True
LOG_LEVEL=INFO
MAX_CONNECTIONS=100

# Rate Limiting
NOTIFICATION_RATE_LIMIT=10
SIGNAL_CHECK_INTERVAL=60

# Default Settings
DEFAULT_RSI_PERIOD=14
DEFAULT_EMA_PERIODS=20,50,100,200
DEFAULT_TIMEFRAMES=1m,5m,15m,1h,2h,4h,1d,1w
```

### 📄 `docker-compose.yml`
**Назначение:** Конфигурация Docker контейнеров

### 📄 `Dockerfile` 
**Назначение:** Образ Docker для приложения

### 📄 `requirements.txt`
**Назначение:** Python зависимости проекта

### 📄 `scripts/init.sql`
**Назначение:** SQL скрипт инициализации базы данных

### 📄 `scripts/test_websocket.py`
**Назначение:** Скрипт тестирования WebSocket подключения

---

## 🔍 БЫСТРЫЙ ПОИСК ПО ФУНКЦИЯМ

### 🤖 **Telegram Bot операции:**
- **Запуск бота:** `src/main.py → main()`
- **Регистрация пользователя:** `src/bot/handlers/start_handler.py → handle_start_command()`
- **Добавление пары:** `src/bot/handlers/add_pair/add_pair_handler.py → handle_add_pair_start()`
- **Удаление пары:** `src/bot/handlers/remove_pair_handler.py → handle_remove_pair_start()`
- **Просмотр пар:** `src/bot/handlers/my_pairs/my_pairs_handler.py → handle_my_pairs_start()`
- **Управление таймфреймами:** `src/bot/handlers/my_pairs/my_pairs_handler.py → handle_timeframe_toggle()`

### 📊 **Расчет индикаторов:**
- **RSI расчет:** `src/services/indicators/rsi_calculator.py → calculate_rsi()`
- **EMA расчет:** `src/services/indicators/ema_calculator.py → calculate_ema()`
- **Множественные EMA:** `src/services/indicators/ema_calculator.py → calculate_multiple_ema()`
- **Изменение объема:** `src/services/signals/signal_aggregator.py → _calculate_volume_change()`

### 🚨 **Генерация сигналов:**
- **RSI сигналы:** `src/services/signals/rsi_signals.py → check_rsi_signals()`
- **Обработка RSI:** `src/services/signals/rsi_signals.py → process_rsi_update()`
- **Агрегация сигналов:** `src/services/signals/signal_aggregator.py → process_candle_update()`
- **Определение типа сигнала:** `src/services/signals/rsi_signals.py → _determine_rsi_signal_type()`

### 📱 **Уведомления:**
- **Отправка в Telegram:** `src/services/notifications/telegram_sender.py → send_signal_notification()`
- **Форматирование сообщений:** `src/services/notifications/message_formatter.py → format_signal_message()`
- **Очередь уведомлений:** `src/services/notifications/notification_queue.py → add_notification()`
- **Массовые уведомления:** `src/services/notifications/telegram_sender.py → send_bulk_notifications()`

### 🗄️ **База данных:**
- **Создание пользователя:** `src/data/repositories/user_repository.py → create_user_from_telegram()`
- **Поиск пользователя:** `src/data/repositories/user_repository.py → get_by_telegram_id()`
- **Работа с парами:** `src/data/repositories/pair_repository.py → get_or_create_pair()`
- **Добавление пары пользователю:** `src/data/repositories/pair_repository.py → add_user_to_pair()`
- **История сигналов:** `src/data/models/signal_history_model.py → create_signal_record()`

### 📡 **WebSocket:**
- **Подключение к Binance:** `src/services/websocket/binance_websocket.py → connect()`
- **Управление потоками:** `src/services/websocket/stream_manager.py → add_symbol_stream()`
- **Обработка сообщений:** `src/services/websocket/binance_data_processor.py → process_websocket_message()`
- **Переподключение:** `src/services/websocket/binance_websocket.py → reconnect()`

### 💾 **Кеширование:**
- **Кеш свечей:** `src/services/cache/candle_cache.py → add_new_candle()`
- **Кеш индикаторов:** `src/services/cache/indicator_cache.py → set_rsi()`
- **Получение из кеша:** `src/services/cache/candle_cache.py → get_candles()`
- **Очистка кеша:** `src/services/cache/candle_cache.py → clear_cache()`

### ✅ **Валидация:**
- **Валидация символа:** `src/utils/validators.py → validate_trading_pair_symbol()`
- **Валидация RSI:** `src/utils/validators.py → validate_rsi_value()`
- **Валидация таймфрейма:** `src/utils/validators.py → validate_timeframe()`
- **Валидация Binance данных:** `src/utils/validators.py → validate_binance_kline_data_detailed()`

### 🛠️ **Утилиты:**
- **Работа со временем:** `src/utils/time_helpers.py → timestamp_to_datetime()`
- **Математические функции:** `src/utils/math_helpers.py → calculate_percentage_change()`
- **Логирование:** `src/utils/logger.py → log_user_action()`
- **Константы:** `src/utils/constants.py → get_timeframe_ms()`

### ⚙️ **Конфигурация:**
- **Настройки бота:** `src/config/bot_config.py → get_bot_config()`
- **Настройки БД:** `src/config/database_config.py → get_database_config()`
- **Настройки Redis:** `src/config/redis_config.py → get_redis_config()`
- **Настройки Binance:** `src/config/binance_config.py → get_binance_config()`

---

## 📝 ЗАКЛЮЧЕНИЕ

Эта детальная документация содержит **ПОЛНУЮ КАРТУ** всех файлов проекта с **КАЖДОЙ ФУНКЦИЕЙ** и **КАЖДЫМ МЕТОДОМ**. 

**Для навигации используйте:**
- **Ctrl+F** для поиска по тексту
- **Названия файлов** для быстрого перехода к нужному модулю
- **Названия функций** для поиска конкретной логики
- **Разделы по слоям** для понимания архитектуры

**Каждый файл документирован с:**
- ✅ Назначением и описанием
- ✅ Всеми классами и их методами  
- ✅ Всеми функциями с их параметрами
- ✅ Глобальными переменными и константами
- ✅ Связями с другими модулями

**Этого руководства достаточно для:**
- 🎯 Идеальной навигации по проекту
- 🔧 Понимания любой части кодовой базы
- 📝 Модификации существующего функционала
- ➕ Добавления новых возможностей
- 🐛 Отладки и исправления ошибок

---

*Документация обновлена: 2025-07-30*  
*Детализированная версия для максимально эффективной работы кодекса*
    """Сбросить статистику"""
```

---

### 📂 `src/services/indicators/`

#### 📄 `src/services/indicators/rsi_calculator.py`
**Назначение:** Калькулятор RSI индикатора

**Класс:**
```python
class RSICalculator:
    """Калькулятор RSI (Relative Strength Index)"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация калькулятора RSI"""

async def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]
    """Рассчитать RSI для массива цен"""

async def calculate_real_time_rsi(self, symbol: str, timeframe: str, period: int = 14) -> Optional[float]
    """Рассчитать RSI в реальном времени из кеша"""

def _calculate_rsi_basic(self, prices: List[float], period: int) -> Optional[float]
    """Базовый алгоритм расчета RSI"""

def _calculate_gains_losses(self, prices: List[float]) -> Tuple[List[float], List[float]]
    """Рассчитать прибыли и убытки между ценами"""

def _smooth_values(self, values: List[float], period: int) -> List[float]
    """Сгладить значения используя EMA"""

def _calculate_rs(self, avg_gain: float, avg_loss: float) -> float
    """Рассчитать Relative Strength (RS)"""

def _calculate_rsi_from_rs(self, rs: float) -> float
    """Рассчитать RSI из RS"""

async def calculate_rsi_for_multiple_periods(self, prices: List[float], periods: List[int]) -> Dict[int, float]
    """Рассчитать RSI для нескольких периодов"""

def validate_rsi_inputs(self, prices: List[float], period: int) -> bool
    """Валидировать входные данные для RSI"""

def get_rsi_signal_strength(self, rsi_value: float) -> str
    """Определить силу сигнала RSI"""
```

#### 📄 `src/services/indicators/ema_calculator.py`
**Назначение:** Калькулятор EMA индикатора

**Класс:**
```python
class EMACalculator:
    """Калькулятор EMA (Exponential Moving Average)"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация калькулятора EMA"""

async def calculate_ema(self, prices: List[float], period: int) -> Optional[float]
    """Рассчитать EMA для массива цен"""

async def calculate_multiple_ema(self, prices: List[float], periods: List[int]) -> Dict[int, float]
    """Рассчитать EMA для нескольких периодов одновременно"""

def _calculate_ema_basic(self, prices: List[float], period: int) -> Optional[float]
    """Базовый алгоритм расчета EMA"""

def _calculate_smoothing_factor(self, period: int) -> float
    """Рассчитать коэффициент сглаживания (альфа)"""

def _calculate_initial_sma(self, prices: List[float], period: int) -> float
    """Рассчитать начальное SMA для EMA"""

async def calculate_ema_real_time(self, symbol: str, timeframe: str, period: int) -> Optional[float]
    """Рассчитать EMA в реальном времени"""

def detect_ema_crossover(self, ema_short: float, ema_long: float, prev_ema_short: float, prev_ema_long: float) -> Optional[str]
    """Определить пересечение EMA (bullish/bearish)"""

def calculate_ema_slope(self, current_ema: float, previous_ema: float) -> float
    """Рассчитать наклон EMA"""

def validate_ema_inputs(self, prices: List[float], period: int) -> bool
    """Валидировать входные данные для EMA"""
```

---

### 📂 `src/services/signals/`

#### 📄 `src/services/signals/rsi_signals.py`
**Назначение:** Генератор RSI сигналов

**Класс:**
```python
class RSISignalGenerator:
    """Генератор RSI сигналов"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация генератора RSI сигналов"""

async def process_rsi_update(self, session: AsyncSession, symbol: str, timeframe: str, rsi_value: float, price: float, volume_change_percent: Optional[float] = None) -> int
    """Обработать обновление RSI и сгенерировать сигналы"""

async def check_rsi_signals(self, session: AsyncSession, symbol: str, timeframe: str, current_rsi: float, current_price: float, volume_change_percent: Optional[float] = None) -> List[Dict[str, Any]]
    """Проверить условия RSI сигналов"""

async def generate_notifications(self, signals: List[Dict[str, Any]]) -> int
    """Сгенерировать уведомления для RSI сигналов"""

def _determine_rsi_signal_type(self, rsi_value: float) -> Optional[str]
    """Определить тип RSI сигнала по значению"""

async def _get_users_for_notification(self, session: AsyncSession, symbol: str, timeframe: str) -> List[int]
    """Получить пользователей для уведомления"""

async def _can_send_signal(self, session: AsyncSession, user_id: int, symbol: str, timeframe: str, signal_type: str) -> bool
    """Проверить можно ли отправить сигнал (антиспам)"""

async def _save_signal_history(self, session: AsyncSession, signals: List[Dict[str, Any]]) -> None
    """Сохранить историю сигналов в БД"""

def _get_signal_interval(self, signal_type: str) -> int
    """Получить интервал между сигналами для типа"""

def _format_signal_message(self, signal_data: Dict[str, Any]) -> str
    """Форматировать сообщение сигнала"""

async def get_signal_statistics(self) -> Dict[str, Any]
    """Получить статистику генерации сигналов"""
```

**Глобальный экземпляр:** `rsi_signal_generator = RSISignalGenerator()`

#### 📄 `src/services/signals/signal_aggregator.py`
**Назначение:** Агрегатор всех типов сигналов

**Класс:**
```python
class SignalAggregator:
    """Агрегатор всех типов сигналов"""
```

**Методы:**
```python
def __init__(self)
    """Инициализация агрегатора сигналов"""

async def process_candle_update(self, session: AsyncSession, symbol: str, timeframe: str, candle_data: Dict[str, Any], is_closed: bool = True) -> Dict[str, int]
    """Обработать обновление свечи и сгенерировать сигналы"""

async def _calculate_indicators(self, symbol: str, timeframe: str, candle_data: Dict[str, Any], is_closed: bool) -> Dict[str, Any]
    """Рассчитать все индикаторы для свечи"""

async def _calculate_volume_change(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]) -> Optional[float]
    """Рассчитать изменение объема"""

async def _process_rsi_signals(self, session: AsyncSession, symbol: str, timeframe: str, rsi_value: float, price: float, volume_change_percent: Optional[float]) -> int
    """Обработать RSI сигналы"""

async def _process_ema_signals(self, session: AsyncSession, symbol: str, timeframe: str, ema_values: Dict[int, float], price: float) -> int
    """Обработать EMA сигналы"""

def get_processing_stats(self) -> Dict[str, Any]
    """Получить статистику обработки"""

def reset_stats(self) -> None
    """Сбросить статистику"""
```

**Глобальный экземпляр:** `signal_aggregator = SignalAggregator()`

---

### 📂 `src/services/notifications/`

#### 📄 `src/services/notifications/telegram_sender.py`
**Назначение:** Отправка уведомлений в Telegram

**Класс:**
```python
class TelegramSender:
    """Сервис отправки сообщений в Telegram"""
```

**Методы:**
```python
def __init__(self, bot: Bot)
    """Инициализация с экземпляром бота"""

async def send_signal_notification(self, user_id: int, signal_data: Dict[str, Any]) -> bool
    """Отправить уведомление о сигнале"""

async def send_message_to_user(self, user_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool
    """Отправить сообщение пользователю"""

async def send_message_with_retry(self, user_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, max_retries: int = 3) -> bool
    """Отправить сообщение с повторными попытками"""

async def handle_blocked_user(self, user_id: int) -> None
    """Обработать заблокированного пользователя"""

async def handle_user_deactivated(self, user_id: int) -> None
    """Обработать деактивированного пользователя"""

async def send_bulk_notifications(self, notifications: List[Tuple[int, str, Optional[InlineKeyboardMarkup]]]) -> Dict[str, int]
    """Отправить массовые уведомления"""

def _create_signal_keyboard(self) -> InlineKeyboardMarkup
    """Создать клавиатуру для сигнала"""

async def _log_delivery_status(self, user_id: int, success: bool, error: Optional[str] = None) -> None
    """Логировать статус доставки"""

def get_delivery_stats(self) -> Dict[str, int]
    """Получить статистику доставки"""

def reset_stats(self) -> None
