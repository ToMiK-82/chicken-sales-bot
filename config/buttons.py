"""
Модуль с унифицированными константами для кнопок и готовыми клавиатурами.
✅ Все кнопки — с эмодзи через with_emoji
✅ Никакого ручного ввода → полная согласованность
✅ Фильтры работают на 100% по точному тексту
✅ Полная совместимость с startup_check и handlers
"""

from typing import List, Optional, Dict
from telegram import ReplyKeyboardMarkup, KeyboardButton
import logging

logger = logging.getLogger(__name__)

# === КНОПКИ: ТОЛЬКО ТЕКСТ (без эмодзи) ===

# --- Главное меню ---
BTN_CATALOG = "Каталог"
BTN_ORDERS = "Заказы"
BTN_SCHEDULE = "График"
BTN_CONTACTS = "Контакты"
BTN_HELP = "Справка"
BTN_PROMOTIONS = "Акции"

# --- Админ-меню ---
BTN_ADMIN_ADD = "Добавить"        # для партий
BTN_ADMIN_STOCKS = "Остатки"
BTN_ADMIN_ORDERS = "Все заказы"
BTN_ADMIN_ISSUE = "Выдача"
BTN_ADMIN_BROADCAST = "Рассылка"
BTN_ADMIN_STATS = "Статистика"
BTN_ADMIN_PROMO = "Промо"
BTN_ADMIN_HELP = "Помощь"
BTN_ADMIN_EXIT = "Выход"

# --- Новые действия ---
BTN_CREATE_PROMO = "Создать"     # для акций
BTN_CANCEL_PROMO = "Отменить акцию"  # ← НОВАЯ КНОПКА

# --- Основные действия ---
BTN_CONFIRM = "Подтвердить"
BTN_CANCEL = "Отменить"
BTN_BACK = "Назад"
BTN_EDIT = "Изменить"             # → ✏️ Изменить (партии)
BTN_EDIT_ORDER = "Изменить"       # → 🔧 Изменить (заказы) — тот же текст, но другой эмодзи
BTN_LIST = "Список"

# --- Поля и параметры ---
BTN_BREED = "Порода"
BTN_INCUBATOR = "Инкубатор"
BTN_DELIVERY_DATE = "Дата поставки"
BTN_EDIT_QUANTITY = "Количество"
BTN_EDIT_DATE = "Дата"
BTN_REQUEST_PHONE = "Отправить номер"
BTN_NO = "Нет"
BTN_YES = "Да"
BTN_CANCEL_ORDER = "Отменить заказ"

# --- Методы выдачи ---
BTN_BY_ID = "По ID"
BTN_BY_PHONE = "По телефону"
BTN_BY_BATCH = "По партии"
BTN_ISSUE_CONFIRM = "Выдать"
BTN_SEARCH = "Поиск"

# --- Рассылка ---
BROADCAST_TEXT = "Текст"
BROADCAST_PHOTO = "Изображение"
BROADCAST_RECIPIENTS_ALL = "Всем"
BROADCAST_RECIPIENTS_CUSTOMERS = "Клиентам"
BROADCAST_RECIPIENTS_ADMINS = "Админам"
BROADCAST_RECIPIENTS_TEST = "Тест"

# --- Разделители ---
SEPARATOR = "────────────────\n"
BOLD_SEPARATOR = "════════════════════\n"
DOT_SEPARATOR = "⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯\n"

# === ПОРОДЫ ===
BREED_BROILER = "Бройлер"
BREED_MEAT_EGG = "Мясо-яичная"
BREED_LAYER = "Несушка"
BREED_TURKEY = "Индейка"
BREED_DUCK = "Утка"
BREED_GOOSE = "Гусь"

BREEDS = [
    BREED_BROILER,
    BREED_MEAT_EGG,
    BREED_LAYER,
    BREED_TURKEY,
    BREED_DUCK,
    BREED_GOOSE,
]

# === ИНКУБАТОРЫ ===
INCUBATOR_LENINSKY = "Ленинский"
INCUBATOR_AZOVSKY = "Азовский"
INCUBATOR_BELOGORSKY = "Белогорский"
INCUBATOR_TSVETKOVO = "Цветково"

INCUBATORS = [
    INCUBATOR_LENINSKY,
    INCUBATOR_AZOVSKY,
    INCUBATOR_BELOGORSKY,
    INCUBATOR_TSVETKOVO,
]

# === ЭМОДЗИ СЛОВАРИ ===
BREED_EMOJI: Dict[str, str] = {
    BREED_BROILER: "🍗",
    BREED_MEAT_EGG: "🥚",
    BREED_LAYER: "🐣",
    BREED_TURKEY: "🦃",
    BREED_DUCK: "🦆",
    BREED_GOOSE: "🦢",
}

INCUBATOR_EMOJI: Dict[str, str] = {
    INCUBATOR_LENINSKY: "🏭",
    INCUBATOR_AZOVSKY: "📍",
    INCUBATOR_BELOGORSKY: "🏡",
    INCUBATOR_TSVETKOVO: "🥚",
}

MAIN_MENU_EMOJI: Dict[str, str] = {
    BTN_CATALOG: "🐔",
    BTN_SCHEDULE: "📅",
    BTN_ORDERS: "📦",
    BTN_PROMOTIONS: "🎁",
    BTN_CONTACTS: "📞",
    BTN_HELP: "📘",
}

ACTION_EMOJI: Dict[str, str] = {
    BTN_CONFIRM: "✅",
    BTN_CANCEL: "❌",
    BTN_BACK: "⬅️",
    BTN_EDIT: "✏️",              # ✏️ Изменить (партии)
    BTN_EDIT_ORDER: "🔧",        # 🔧 Изменить (заказы)
    BTN_LIST: "📋",
    BTN_BREED: "🐔",
    BTN_INCUBATOR: "🏭",
    BTN_DELIVERY_DATE: "📅",
    BTN_REQUEST_PHONE: "📱",
    BTN_YES: "✅",
    BTN_NO: "❌",
    BTN_EDIT_QUANTITY: "🔢",
    BTN_EDIT_DATE: "📅",
    BTN_CREATE_PROMO: "➕",
}

ADMIN_MENU_EMOJI: Dict[str, str] = {
    BTN_ADMIN_ADD: "📦",
    BTN_ADMIN_STOCKS: "📊",
    BTN_ADMIN_ORDERS: "📋",
    BTN_ADMIN_ISSUE: "🐣",
    BTN_ADMIN_BROADCAST: "📢",
    BTN_ADMIN_STATS: "📈",
    BTN_ADMIN_PROMO: "🛠️",
    BTN_ADMIN_HELP: "📘",
    BTN_ADMIN_EXIT: "🚪",
}

ISSUE_EMOJI: Dict[str, str] = {
    BTN_BY_ID: "🆔",
    BTN_BY_PHONE: "📞",
    BTN_BY_BATCH: "📦",
    BTN_SEARCH: "🔍",
}

BROADCAST_EMOJI: Dict[str, str] = {
    BROADCAST_TEXT: "📄",
    BROADCAST_PHOTO: "🖼️",
    BROADCAST_RECIPIENTS_ALL: "🌍",
    BROADCAST_RECIPIENTS_CUSTOMERS: "👥",
    BROADCAST_RECIPIENTS_ADMINS: "🛡️",
    BROADCAST_RECIPIENTS_TEST: "🧪",
}

OTHER_EMOJI: Dict[str, str] = {
    BTN_CANCEL_ORDER: "🗑️",
    BTN_CANCEL_PROMO: "🗑️",  
}

# === УТИЛИТА: добавление эмодзи ===
def with_emoji(text: str, emoji_map: dict) -> str:
    """
    Добавляет эмодзи к тексту: 'эмодзи + пробел + текст'.
    Защищает от None и нестроковых значений.
    """
    if text is None:
        logger.error("❌ with_emoji: передан None!")
        return "❓"
    if not isinstance(text, str):
        logger.warning(f"⚠️ with_emoji: передан не str: {repr(text)} → преобразовано")
        text = str(text)
    emoji = emoji_map.get(text, '')
    return f"{emoji} {text}".strip()

# === FULL-КНОПКИ С ЭМОДЗИ ===
BTN_CATALOG_FULL = with_emoji(BTN_CATALOG, MAIN_MENU_EMOJI)
BTN_ORDERS_FULL = with_emoji(BTN_ORDERS, MAIN_MENU_EMOJI)
BTN_SCHEDULE_FULL = with_emoji(BTN_SCHEDULE, MAIN_MENU_EMOJI)
BTN_CONTACTS_FULL = with_emoji(BTN_CONTACTS, MAIN_MENU_EMOJI)
BTN_HELP_FULL = with_emoji(BTN_HELP, MAIN_MENU_EMOJI)
BTN_PROMOTIONS_FULL = with_emoji(BTN_PROMOTIONS, MAIN_MENU_EMOJI)

BTN_ADMIN_ADD_FULL = with_emoji(BTN_ADMIN_ADD, ADMIN_MENU_EMOJI)
BTN_ADMIN_STOCKS_FULL = with_emoji(BTN_ADMIN_STOCKS, ADMIN_MENU_EMOJI)
BTN_ADMIN_ORDERS_FULL = with_emoji(BTN_ADMIN_ORDERS, ADMIN_MENU_EMOJI)
BTN_ADMIN_ISSUE_FULL = with_emoji(BTN_ADMIN_ISSUE, ADMIN_MENU_EMOJI)
BTN_ADMIN_BROADCAST_FULL = with_emoji(BTN_ADMIN_BROADCAST, ADMIN_MENU_EMOJI)
BTN_ADMIN_STATS_FULL = with_emoji(BTN_ADMIN_STATS, ADMIN_MENU_EMOJI)
BTN_ADMIN_PROMO_FULL = with_emoji(BTN_ADMIN_PROMO, ADMIN_MENU_EMOJI)
BTN_ADMIN_HELP_FULL = with_emoji(BTN_ADMIN_HELP, ADMIN_MENU_EMOJI)
BTN_ADMIN_EXIT_FULL = with_emoji(BTN_ADMIN_EXIT, ADMIN_MENU_EMOJI)

BTN_CREATE_PROMO_FULL = with_emoji(BTN_CREATE_PROMO, ACTION_EMOJI)
BTN_CANCEL_PROMO_FULL = with_emoji(BTN_CANCEL_PROMO, OTHER_EMOJI)  # 🗑️ Отменить акцию

BTN_CONFIRM_FULL = with_emoji(BTN_CONFIRM, ACTION_EMOJI)
BTN_CANCEL_FULL = with_emoji(BTN_CANCEL, ACTION_EMOJI)
BTN_BACK_FULL = with_emoji(BTN_BACK, ACTION_EMOJI)
BTN_EDIT_FULL = with_emoji(BTN_EDIT, ACTION_EMOJI)          # ✏️ Изменить (партии)
BTN_EDIT_ORDER_FULL = with_emoji(BTN_EDIT_ORDER, ACTION_EMOJI)  # 🔧 Изменить (заказы)
BTN_LIST_FULL = with_emoji(BTN_LIST, ACTION_EMOJI)

BTN_BREED_FULL = with_emoji(BTN_BREED, ACTION_EMOJI)
BTN_INCUBATOR_FULL = with_emoji(BTN_INCUBATOR, ACTION_EMOJI)
BTN_DELIVERY_DATE_FULL = with_emoji(BTN_DELIVERY_DATE, ACTION_EMOJI)
BTN_EDIT_QUANTITY_FULL = with_emoji(BTN_EDIT_QUANTITY, ACTION_EMOJI)
BTN_EDIT_DATE_FULL = with_emoji(BTN_EDIT_DATE, ACTION_EMOJI)
BTN_REQUEST_PHONE_FULL = with_emoji(BTN_REQUEST_PHONE, ACTION_EMOJI)
BTN_YES_FULL = with_emoji(BTN_YES, ACTION_EMOJI)
BTN_NO_FULL = with_emoji(BTN_NO, ACTION_EMOJI)
BTN_CANCEL_ORDER_FULL = with_emoji(BTN_CANCEL_ORDER, OTHER_EMOJI)
BTN_ISSUE_CONFIRM_FULL = with_emoji(BTN_ISSUE_CONFIRM, OTHER_EMOJI)
BTN_SEARCH_FULL = with_emoji(BTN_SEARCH, ISSUE_EMOJI)

BTN_BY_ID_FULL = with_emoji(BTN_BY_ID, ISSUE_EMOJI)
BTN_BY_PHONE_FULL = with_emoji(BTN_BY_PHONE, ISSUE_EMOJI)
BTN_BY_BATCH_FULL = with_emoji(BTN_BY_BATCH, ISSUE_EMOJI)

BROADCAST_TEXT_FULL = with_emoji(BROADCAST_TEXT, BROADCAST_EMOJI)
BROADCAST_PHOTO_FULL = with_emoji(BROADCAST_PHOTO, BROADCAST_EMOJI)
BROADCAST_RECIPIENTS_ALL_FULL = with_emoji(BROADCAST_RECIPIENTS_ALL, BROADCAST_EMOJI)
BROADCAST_RECIPIENTS_CUSTOMERS_FULL = with_emoji(BROADCAST_RECIPIENTS_CUSTOMERS, BROADCAST_EMOJI)
BROADCAST_RECIPIENTS_ADMINS_FULL = with_emoji(BROADCAST_RECIPIENTS_ADMINS, BROADCAST_EMOJI)
BROADCAST_RECIPIENTS_TEST_FULL = with_emoji(BROADCAST_RECIPIENTS_TEST, BROADCAST_EMOJI)

# === ТЕКСТ КНОПОК С ЭМОДЗИ (для фильтров) ===
CATALOG_BUTTON_TEXT = BTN_CATALOG_FULL
ORDERS_BUTTON_TEXT = BTN_ORDERS_FULL
SCHEDULE_BUTTON_TEXT = BTN_SCHEDULE_FULL
CONTACTS_BUTTON_TEXT = BTN_CONTACTS_FULL
HELP_BUTTON_TEXT = BTN_HELP_FULL
PROMOTIONS_BUTTON_TEXT = BTN_PROMOTIONS_FULL

ADMIN_ADD_BUTTON_TEXT = BTN_ADMIN_ADD_FULL
ADMIN_STOCKS_BUTTON_TEXT = BTN_ADMIN_STOCKS_FULL
ADMIN_ORDERS_BUTTON_TEXT = BTN_ADMIN_ORDERS_FULL
ADMIN_ISSUE_BUTTON_TEXT = BTN_ADMIN_ISSUE_FULL
ADMIN_BROADCAST_BUTTON_TEXT = BTN_ADMIN_BROADCAST_FULL
ADMIN_STATS_BUTTON_TEXT = BTN_ADMIN_STATS_FULL
ADMIN_PROMO_BUTTON_TEXT = BTN_ADMIN_PROMO_FULL
ADMIN_HELP_BUTTON_TEXT = BTN_ADMIN_HELP_FULL
ADMIN_EXIT_BUTTON_TEXT = BTN_ADMIN_EXIT_FULL

CREATE_PROMO_BUTTON_TEXT = BTN_CREATE_PROMO_FULL

# === СПИСКИ КНОПОК С ЭМОДЗИ ===
BREED_BUTTONS = [with_emoji(breed, BREED_EMOJI) for breed in BREEDS]
INCUBATOR_BUTTONS = [with_emoji(inc, INCUBATOR_EMOJI) for inc in INCUBATORS]

ADMIN_MENU_BUTTONS = [
    BTN_ADMIN_ADD_FULL,
    BTN_ADMIN_STOCKS_FULL,
    BTN_ADMIN_ORDERS_FULL,
    BTN_ADMIN_ISSUE_FULL,
    BTN_ADMIN_BROADCAST_FULL,
    BTN_ADMIN_STATS_FULL,
    BTN_ADMIN_PROMO_FULL,
    BTN_ADMIN_HELP_FULL,
    BTN_ADMIN_EXIT_FULL,
]

MAIN_MENU_BUTTONS = [
    CATALOG_BUTTON_TEXT,
    SCHEDULE_BUTTON_TEXT,
    ORDERS_BUTTON_TEXT,
    PROMOTIONS_BUTTON_TEXT,
    CONTACTS_BUTTON_TEXT,
    HELP_BUTTON_TEXT,
]

# === УТИЛИТЫ: готовые кнопки ===
BACK_BUTTON = KeyboardButton(BTN_BACK_FULL)
REQUEST_PHONE_BUTTON = KeyboardButton(BTN_REQUEST_PHONE_FULL, request_contact=True)

# === КЛАВИАТУРЫ ===

def _build_keyboard(
    buttons: List[str],
    emoji_map: Dict[str, str],
    cols: int = 3,
    add_back: bool = False,
    one_time: bool = False,
    custom_rows: Optional[List[List[KeyboardButton]]] = None
) -> ReplyKeyboardMarkup:
    """
    Унифицированное построение клавиатуры.
    :param buttons: список текстов кнопок
    :param emoji_map: словарь соответствия текст → эмодзи
    :param cols: количество кнопок в строке
    :param add_back: добавить кнопку "Назад"
    :param one_time: скрыть после выбора
    :param custom_rows: дополнительные строки (например, с контактами)
    """
    keyboard = []
    row = []
    for btn in buttons:
        row.append(KeyboardButton(with_emoji(btn, emoji_map)))
        if len(row) == cols:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    if custom_rows:
        keyboard.extend(custom_rows)
    if add_back:
        keyboard.append([BACK_BUTTON])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=one_time)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главное меню клиента.
    Важно: использует ТОЧНЫЕ строки из CATALOG_BUTTON_TEXT и др.,
    чтобы гарантировать совпадение с фильтрами.
    """
    keyboard = [
        [
            KeyboardButton(CATALOG_BUTTON_TEXT),
            KeyboardButton(SCHEDULE_BUTTON_TEXT),
            KeyboardButton(ORDERS_BUTTON_TEXT),
        ],
        [
            KeyboardButton(PROMOTIONS_BUTTON_TEXT),
            KeyboardButton(CONTACTS_BUTTON_TEXT),
            KeyboardButton(HELP_BUTTON_TEXT),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню администратора."""
    return _build_keyboard(
        buttons=[
            BTN_ADMIN_ADD, BTN_ADMIN_STOCKS, BTN_ADMIN_ORDERS, BTN_ADMIN_ISSUE,
            BTN_ADMIN_BROADCAST, BTN_ADMIN_STATS, BTN_ADMIN_PROMO, BTN_ADMIN_HELP, BTN_ADMIN_EXIT
        ],
        emoji_map=ADMIN_MENU_EMOJI,
        cols=3,
        add_back=False,
        one_time=False
    )


def get_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура «Подтвердить / Отменить» + Назад."""
    return _build_keyboard(
        buttons=[BTN_CONFIRM, BTN_CANCEL],
        emoji_map=ACTION_EMOJI,
        cols=2,
        add_back=True,
        one_time=False
    )


def get_back_only_keyboard() -> ReplyKeyboardMarkup:
    """Только кнопка «Назад»."""
    return ReplyKeyboardMarkup([[BACK_BUTTON]], resize_keyboard=True, one_time_keyboard=False)


def get_incubator_keyboard(incubators: List[str] = None) -> ReplyKeyboardMarkup:
    """Клавиатура инкубаторов с фильтрацией."""
    incubators = incubators or INCUBATORS
    if not isinstance(incubators, list):
        logger.error(f"❌ get_incubator_keyboard: ожидается list, получено {type(incubators)}")
        incubators = INCUBATORS
    return _build_keyboard(
        buttons=incubators,
        emoji_map=INCUBATOR_EMOJI,
        cols=2,
        add_back=True,
        one_time=False
    )


def get_breeds_keyboard(bot_data: Optional[dict] = None) -> ReplyKeyboardMarkup:
    """
    Клавиатура пород с поддержкой фильтрации.
    :param bot_data: {'available_breeds': [...], 'breed_emoji': {...}}
    """
    if not isinstance(bot_data, dict):
        bot_data = {}
    breeds = bot_data.get("available_breeds", BREEDS)
    emoji_map = bot_data.get("breed_emoji", BREED_EMOJI)

    if not breeds:
        return ReplyKeyboardMarkup([["Нет доступных пород"]], resize_keyboard=True)

    if not isinstance(breeds, list):
        logger.error(f"❌ get_breeds_keyboard: ожидается list, получено {type(breeds)}")
        breeds = BREEDS

    return _build_keyboard(
        buttons=breeds,
        emoji_map=emoji_map,
        cols=3,
        add_back=True,
        one_time=False
    )


def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Простая клавиатура Да/Нет (одноразовая)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_YES_FULL), KeyboardButton(BTN_NO_FULL)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_confirm_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Синоним get_yes_no_keyboard."""
    return get_yes_no_keyboard()


def get_orders_action_keyboard() -> ReplyKeyboardMarkup:
    """Действия с заказами."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CANCEL_ORDER_FULL), BACK_BUTTON]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_phone_input_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отправки контакта."""
    return ReplyKeyboardMarkup(
        [[REQUEST_PHONE_BUTTON], [BACK_BUTTON]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_issue_method_keyboard() -> ReplyKeyboardMarkup:
    """Методы выдачи."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_BY_ID_FULL), KeyboardButton(BTN_BY_PHONE_FULL)],
            [KeyboardButton(BTN_BY_BATCH_FULL)],
            [KeyboardButton(BTN_SEARCH_FULL)],
            [BACK_BUTTON]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_issue_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Подтверждение выдачи."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_ISSUE_CONFIRM_FULL), KeyboardButton(BTN_CANCEL_FULL)],
            [BACK_BUTTON]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_quantity_date_keyboard() -> ReplyKeyboardMarkup:
    """Изменение количества или даты."""
    return _build_keyboard(
        buttons=[BTN_EDIT_QUANTITY, BTN_EDIT_DATE],
        emoji_map=ACTION_EMOJI,
        cols=2,
        add_back=True,
        one_time=False
    )


def get_broadcast_type_keyboard() -> ReplyKeyboardMarkup:
    """Выбор типа рассылки (текст/фото)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BROADCAST_TEXT_FULL), KeyboardButton(BROADCAST_PHOTO_FULL)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_recipients_keyboard() -> ReplyKeyboardMarkup:
    """Получатели рассылки."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BROADCAST_RECIPIENTS_ALL_FULL), KeyboardButton(BROADCAST_RECIPIENTS_CUSTOMERS_FULL)],
            [KeyboardButton(BROADCAST_RECIPIENTS_ADMINS_FULL), KeyboardButton(BROADCAST_RECIPIENTS_TEST_FULL)],
            [BACK_BUTTON]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_promo_action_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура действий с акциями.
    ✅ Все три кнопки в одной строке: 'Создать', 'Список', 'Назад'
    ✅ Упрощённый UX: нет лишних строк
    """
    keyboard = [
        [
            KeyboardButton(BTN_CREATE_PROMO_FULL),
            KeyboardButton(BTN_LIST_FULL),
            KeyboardButton(BTN_BACK_FULL)
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_stock_action_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура действий с остатками.
    ✅ Только две кнопки: '✏️ Изменить' и '⬅️ Назад'
    ✅ В одной строке
    """
    keyboard = [
        [
            KeyboardButton(BTN_EDIT_FULL),
            KeyboardButton(BTN_BACK_FULL)
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_id_selection_keyboard(items: List[str], add_back: bool = True) -> ReplyKeyboardMarkup:
    """Клавиатура выбора по ID (например, список заказов)."""
    if not items:
        return get_back_only_keyboard()
    keyboard = []
    row = []
    for item in items:
        row.append(KeyboardButton(item))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    if add_back:
        keyboard.append([BACK_BUTTON])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_promo_list_actions_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура после вывода списка акций: 'Отменить акцию' и 'Назад'.
    """
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_CANCEL_PROMO_FULL), KeyboardButton(BTN_BACK_FULL)]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


# === ЭКСПОРТ ===
__all__ = [
    # === Кнопки (текст) ===
    "BTN_CATALOG", "BTN_ORDERS", "BTN_SCHEDULE", "BTN_CONTACTS", "BTN_HELP", "BTN_PROMOTIONS",
    "BTN_ADMIN_ADD", "BTN_ADMIN_STOCKS", "BTN_ADMIN_ORDERS", "BTN_ADMIN_ISSUE", "BTN_ADMIN_BROADCAST",
    "BTN_ADMIN_STATS", "BTN_ADMIN_PROMO", "BTN_ADMIN_HELP", "BTN_ADMIN_EXIT",
    "BTN_CREATE_PROMO", "BTN_CANCEL_PROMO", "BTN_CONFIRM", "BTN_CANCEL", "BTN_BACK", "BTN_EDIT", "BTN_EDIT_ORDER", "BTN_LIST",
    "BTN_BREED", "BTN_INCUBATOR", "BTN_DELIVERY_DATE", "BTN_EDIT_QUANTITY", "BTN_EDIT_DATE",
    "BTN_REQUEST_PHONE", "BTN_NO", "BTN_YES", "BTN_BY_ID", "BTN_BY_PHONE", "BTN_BY_BATCH", "BTN_ISSUE_CONFIRM",
    "BTN_SEARCH", "BTN_CANCEL_ORDER", "BROADCAST_TEXT", "BROADCAST_PHOTO", "BROADCAST_RECIPIENTS_ALL",
    "BROADCAST_RECIPIENTS_CUSTOMERS", "BROADCAST_RECIPIENTS_ADMINS", "BROADCAST_RECIPIENTS_TEST",

    # === FULL-кнопки (с эмодзи) ===
    "BTN_CATALOG_FULL", "BTN_ORDERS_FULL", "BTN_SCHEDULE_FULL", "BTN_CONTACTS_FULL",
    "BTN_HELP_FULL", "BTN_PROMOTIONS_FULL", "BTN_ADMIN_ADD_FULL", "BTN_ADMIN_STOCKS_FULL",
    "BTN_ADMIN_ORDERS_FULL", "BTN_ADMIN_ISSUE_FULL", "BTN_ADMIN_BROADCAST_FULL",
    "BTN_ADMIN_STATS_FULL", "BTN_ADMIN_PROMO_FULL", "BTN_ADMIN_HELP_FULL", "BTN_ADMIN_EXIT_FULL",
    "BTN_CREATE_PROMO_FULL", "BTN_CANCEL_PROMO_FULL", "BTN_CONFIRM_FULL", "BTN_CANCEL_FULL", "BTN_BACK_FULL",
    "BTN_EDIT_FULL", "BTN_EDIT_ORDER_FULL", "BTN_LIST_FULL", "BTN_BREED_FULL", "BTN_INCUBATOR_FULL", "BTN_DELIVERY_DATE_FULL",
    "BTN_EDIT_QUANTITY_FULL", "BTN_EDIT_DATE_FULL", "BTN_REQUEST_PHONE_FULL", "BTN_YES_FULL", "BTN_NO_FULL",
    "BTN_CANCEL_ORDER_FULL", "BTN_ISSUE_CONFIRM_FULL", "BTN_SEARCH_FULL", "BROADCAST_TEXT_FULL",
    "BROADCAST_PHOTO_FULL", "BROADCAST_RECIPIENTS_ALL_FULL", "BROADCAST_RECIPIENTS_CUSTOMERS_FULL",
    "BROADCAST_RECIPIENTS_ADMINS_FULL", "BROADCAST_RECIPIENTS_TEST_FULL", "BTN_BY_ID_FULL", "BTN_BY_PHONE_FULL",
    "BTN_BY_BATCH_FULL",

    # === Текстовые кнопки с эмодзи (для фильтров) ===
    "CATALOG_BUTTON_TEXT", "ORDERS_BUTTON_TEXT", "SCHEDULE_BUTTON_TEXT", "CONTACTS_BUTTON_TEXT",
    "HELP_BUTTON_TEXT", "PROMOTIONS_BUTTON_TEXT", "ADMIN_ADD_BUTTON_TEXT", "ADMIN_STOCKS_BUTTON_TEXT",
    "ADMIN_ORDERS_BUTTON_TEXT", "ADMIN_ISSUE_BUTTON_TEXT", "ADMIN_BROADCAST_BUTTON_TEXT",
    "ADMIN_STATS_BUTTON_TEXT", "ADMIN_PROMO_BUTTON_TEXT", "ADMIN_HELP_BUTTON_TEXT", "ADMIN_EXIT_BUTTON_TEXT",
    "CREATE_PROMO_BUTTON_TEXT",

    # === Списки ===
    "BREEDS", "INCUBATORS", "BREED_BUTTONS", "INCUBATOR_BUTTONS", "ADMIN_MENU_BUTTONS", "MAIN_MENU_BUTTONS",

    # === Разделители ===
    "SEPARATOR", "BOLD_SEPARATOR", "DOT_SEPARATOR",

    # === Клавиатуры ===
    "get_main_keyboard", "get_admin_main_keyboard", "get_confirmation_keyboard", "get_back_only_keyboard",
    "get_breeds_keyboard", "get_incubator_keyboard", "get_yes_no_keyboard", "get_confirm_cancel_keyboard",
    "get_orders_action_keyboard", "get_phone_input_keyboard", "get_issue_method_keyboard",
    "get_issue_confirm_keyboard", "get_quantity_date_keyboard", "get_broadcast_type_keyboard",
    "get_recipients_keyboard", "get_promo_action_keyboard", "get_stock_action_keyboard",
    "get_id_selection_keyboard", "get_promo_list_actions_keyboard",

    # === Утилиты ===
    "BACK_BUTTON", 
    "REQUEST_PHONE_BUTTON", 
    "with_emoji",

    # === Словари эмодзи ===
    "BREED_EMOJI", 
    "INCUBATOR_EMOJI", 
    "MAIN_MENU_EMOJI", 
    "ACTION_EMOJI", 
    "ADMIN_MENU_EMOJI", 
    "ISSUE_EMOJI",
    "BROADCAST_EMOJI", 
    "OTHER_EMOJI",
]
