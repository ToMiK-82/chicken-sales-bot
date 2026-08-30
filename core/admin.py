"""
Админ-панель для MAX-канала (компактная версия Telegram-админки).

Функции:
- /admin → меню администратора (доступ: MAX_ADMIN_IDS из .env)
- 📦 Добавить партию (порода → дата → количество → цена → инкубатор → подтверждение)
- 📊 Остатки (активные партии)
- 📋 Заказы (все pending/active)
- 🐣 Выдача (по номеру заказа, только active → issued)
- 🚪 Выход → клиентское меню

Формат ответов — как в core/handlers: {"text", "buttons", "format"}.
"""
import logging
import os
from datetime import datetime
from html import escape

from database.repository import db
from core.session import get_session

logger = logging.getLogger(__name__)

# === Доступ ===
def is_max_admin(user_id: str) -> bool:
    """Проверка: MAX user_id в списке администраторов (MAX_ADMIN_IDS)."""
    try:
        raw = os.getenv("MAX_ADMIN_IDS", "").strip()
        if not raw:
            return False
        return str(user_id) in {x.strip() for x in raw.split(",") if x.strip()}
    except Exception:
        return False


# === Константы ===
BREEDS = ["Бройлер", "Мясо-яичная", "Несушка", "Индейка", "Утка", "Гусь"]
INCUBATORS = ["Ленинский", "Азовский", "Белогорский", "Цветково"]

BREED_EMOJI = {"Бройлер": "🍗", "Мясо-яичная": "🥚", "Несушка": "🐣", "Индейка": "🦃", "Утка": "🦆", "Гусь": "🦢"}
INCUBATOR_EMOJI = {"Ленинский": "🏭", "Азовский": "📍", "Белогорский": "🏡", "Цветково": "🥚"}
SEPARATOR = "────────────────"

# === Payload ===
PAYLOAD_ADMIN_MENU = "admin_menu"
PAYLOAD_ADMIN_ADD = "admin_add"
PAYLOAD_ADMIN_STOCKS = "admin_stocks"
PAYLOAD_ADMIN_ORDERS = "admin_orders"
PAYLOAD_ADMIN_ISSUE = "admin_issue"
PAYLOAD_ADMIN_EXIT = "admin_exit"
PAYLOAD_ADMIN_BACK = "admin_back"
PAYLOAD_ADMIN_ADD_BREED = "admin_add_breed_"
PAYLOAD_ADMIN_ADD_INCUBATOR = "admin_add_incubator_"
PAYLOAD_ADMIN_CONFIRM_ADD = "admin_confirm_add"
PAYLOAD_ADMIN_ISSUE_PREFIX = "admin_issue_"
PAYLOAD_ADMIN_ISSUE_CONFIRM = "admin_issue_confirm_"
PAYLOAD_ADMIN_CANCEL_ISSUE = "admin_cancel_issue"

# === Состояния ===
S_ADMIN_ADD_BREED = "admin_add_breed"
S_ADMIN_ADD_DATE = "admin_add_date"
S_ADMIN_ADD_QUANTITY = "admin_add_quantity"
S_ADMIN_ADD_PRICE = "admin_add_price"
S_ADMIN_ADD_INCUBATOR = "admin_add_incubator"
S_ADMIN_ADD_CONFIRM = "admin_add_confirm"
S_ADMIN_ISSUE_ORDER = "admin_issue_order"
S_ADMIN_ISSUE_CONFIRM = "admin_issue_confirm"


def _back_btn():
    return [[{"type": "message", "text": "⬅️ Назад", "payload": PAYLOAD_ADMIN_BACK}]]


def _cancel_btn():
    return [[{"type": "message", "text": "❌ Отмена", "payload": PAYLOAD_ADMIN_BACK}]]


# === Меню админа ===
def admin_menu_response() -> dict:
    return {
        "text": (
            "🔐 <b>Админ-панель</b> | Готов к работе ✅\n\n"
            "📋 Воспользуйтесь меню:"
        ),
        "buttons": [
            [{"type": "message", "text": "📦 Добавить партию", "payload": PAYLOAD_ADMIN_ADD}],
            [
                {"type": "message", "text": "📊 Остатки", "payload": PAYLOAD_ADMIN_STOCKS},
                {"type": "message", "text": "📋 Заказы", "payload": PAYLOAD_ADMIN_ORDERS},
            ],
            [
                {"type": "message", "text": "🐣 Выдача", "payload": PAYLOAD_ADMIN_ISSUE},
                {"type": "message", "text": "🚪 Выход", "payload": PAYLOAD_ADMIN_EXIT},
            ],
        ],
        "format": "html",
    }


def _client_menu_response(user_name: str = "") -> dict:
    """Выход из админки → клиентское меню (копия главного меню)."""
    name = escape(user_name.strip()) if user_name and user_name.strip() else "Друг"
    return {
        "text": (
            f"👋 Привет, <b>{name}</b>!\n"
            "Добро пожаловать в сервис <b>Chicken_sales_bot</b>! 🐔\n\n"
            "Мы осуществляем продажу суточных цыплят сельскохозяйственных пород.\n"
            "Выберите нужный раздел 👇"
        ),
        "buttons": [
            [
                {"type": "message", "text": "🐔 Каталог", "payload": "catalog"},
                {"type": "message", "text": "📅 График", "payload": "schedule"},
                {"type": "message", "text": "📦 Мои заказы", "payload": "orders"},
            ],
            [
                {"type": "message", "text": "🎁 Акции", "payload": "promotions"},
                {"type": "message", "text": "📞 Контакты", "payload": "contacts"},
                {"type": "message", "text": "ℹ️ Справка", "payload": "help"},
            ],
        ],
        "format": "html",
    }


# === 1. Добавление партии ===
async def start_add_stock(user_id: str) -> dict:
    session = get_session(user_id)
    session.state = S_ADMIN_ADD_BREED
    session.data.clear()
    session.data["admin_mode"] = True

    buttons = [[{"type": "message", "text": f"{BREED_EMOJI.get(b, '🐔')} {b}", "payload": f"{PAYLOAD_ADMIN_ADD_BREED}{b}"}]
               for b in BREEDS]
    buttons += _cancel_btn()
    return {"text": "🐔 <b>Выберите породу:</b>", "buttons": buttons, "format": "html"}


async def handle_add_breed(user_id: str, breed: str) -> dict:
    session = get_session(user_id)
    if breed not in BREEDS:
        return {"text": "❌ Выберите породу из списка.", "buttons": _cancel_btn()}

    session.data["breed"] = breed
    session.state = S_ADMIN_ADD_DATE
    return {"text": "📅 Введите дату поставки в формате: <b>ГГГГ-ММ-ДД</b>", "buttons": _back_btn(), "format": "html"}


async def handle_add_date(user_id: str, text: str) -> dict:
    session = get_session(user_id)
    text = text.strip()
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return {"text": "❌ Неверный формат даты.\nИспользуйте: <b>ГГГГ-ММ-ДД</b>", "buttons": _back_btn(), "format": "html"}
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return {"text": "❌ Неверная дата.", "buttons": _back_btn()}

    session.data["date"] = text
    session.state = S_ADMIN_ADD_QUANTITY
    return {"text": "🔢 Введите количество цыплят (целое число):", "buttons": _back_btn()}


async def handle_add_quantity(user_id: str, text: str) -> dict:
    session = get_session(user_id)
    text = text.strip()
    if not text.isdigit() or int(text) <= 0:
        return {"text": "❌ Введите корректное количество (целое положительное число).", "buttons": _back_btn()}

    session.data["quantity"] = int(text)
    session.state = S_ADMIN_ADD_PRICE
    return {"text": "💰 Введите цену за одного цыплёнка (можно с копейками):", "buttons": _back_btn()}


async def handle_add_price(user_id: str, text: str) -> dict:
    session = get_session(user_id)
    text = text.strip()
    try:
        price = float(text.replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        return {"text": "❌ Введите корректную цену (положительное число).", "buttons": _back_btn()}

    session.data["price"] = round(price, 2)
    session.state = S_ADMIN_ADD_INCUBATOR

    buttons = [[{"type": "message", "text": f"{INCUBATOR_EMOJI.get(i, '🏭')} {i}", "payload": f"{PAYLOAD_ADMIN_ADD_INCUBATOR}{i}"}]
               for i in INCUBATORS]
    buttons += _cancel_btn()
    return {"text": "📍 Выберите инкубатор:", "buttons": buttons, "format": "html"}


async def handle_add_incubator(user_id: str, incubator: str) -> dict:
    session = get_session(user_id)
    if incubator not in INCUBATORS:
        return {"text": "❌ Выберите инкубатор из списка.", "buttons": _cancel_btn()}

    session.data["incubator"] = incubator
    session.state = S_ADMIN_ADD_CONFIRM

    d = session.data
    text = (
        "✅ <b>Проверьте данные:</b>\n\n"
        f"🐔 <b>{escape(d['breed'])}</b>\n"
        f"🏢 <b>{escape(d['incubator'])}</b>\n"
        f"📅 <b>{d['date']}</b>\n"
        f"📦 <b>{d['quantity']}</b> шт.\n"
        f"💰 <b>{d['price']:.2f}</b> руб.\n\n"
        "Нажмите <b>✅ Подтвердить</b>, чтобы добавить партию."
    )
    return {
        "text": text,
        "buttons": [
            [
                {"type": "message", "text": "✅ Подтвердить", "payload": PAYLOAD_ADMIN_CONFIRM_ADD},
                {"type": "message", "text": "⬅️ Назад", "payload": PAYLOAD_ADMIN_BACK},
            ]
        ],
        "format": "html",
    }


async def confirm_add_stock(user_id: str) -> dict:
    session = get_session(user_id)
    d = session.data
    required = ("breed", "incubator", "date", "quantity", "price")
    if not all(k in d for k in required):
        session.state = "idle"
        return admin_menu_response()

    try:
        await db.execute_write(
            """
            INSERT INTO stocks (breed, incubator, date, quantity, available_quantity, price, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (d["breed"], d["incubator"], d["date"], d["quantity"], d["quantity"], d["price"])
        )
        logger.info(f"✅ [MAX] Партия добавлена админом {user_id}: {d['breed']} {d['date']}")
        session.state = "idle"
        session.data.clear()
        return {
            "text": f"✅ Партия «<b>{escape(d['breed'])}</b>» добавлена: <b>{d['quantity']}</b> шт.",
            "buttons": admin_menu_response()["buttons"],
            "format": "html",
        }
    except Exception as e:
        logger.error(f"❌ [MAX] Ошибка добавления партии: {e}", exc_info=True)
        session.state = "idle"
        return {"text": "❌ Не удалось добавить партию.", "buttons": admin_menu_response()["buttons"]}


# === 2. Остатки ===
async def stocks_response() -> dict:
    rows = await db.execute_read(
        "SELECT id, breed, incubator, date, quantity, available_quantity, price FROM stocks WHERE status = 'active' ORDER BY date, breed"
    )
    if not rows:
        return {"text": "📭 Нет активных партий.", "buttons": admin_menu_response()["buttons"]}

    lines = ["📊 <b>Активные партии:</b>\n"]
    for r in rows:
        try:
            dt = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            dt = r["date"]
        lines.append(
            f"🏷️<code>{r['id']}</code> {BREED_EMOJI.get(r['breed'], '🐔')} <b>{escape(r['breed'])}</b> | {escape(r['incubator'])}\n"
            f"📅 {dt} | 📦 {r['available_quantity']}/{r['quantity']} шт. | 💰 {int(r['price'])} руб.\n"
            f"{SEPARATOR}"
        )
    return {"text": "\n".join(lines), "buttons": admin_menu_response()["buttons"], "format": "html"}


# === 3. Заказы ===
async def orders_response() -> dict:
    rows = await db.execute_read(
        "SELECT id, user_id, breed, date, incubator, quantity, price, status, phone FROM orders WHERE status IN ('pending','active') ORDER BY created_at DESC"
    )
    if not rows:
        return {"text": "📭 Нет активных заказов.", "buttons": admin_menu_response()["buttons"]}

    lines = ["📋 <b>Все заказы:</b>\n"]
    for r in rows:
        try:
            dt = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            dt = r["date"]
        status_emoji = "🟡" if r["status"] == "pending" else "🟢"
        lines.append(
            f"{status_emoji} №<code>{r['id']}</code> | 🐔 <b>{escape(r['breed'])}</b> | {dt}\n"
            f"📦 {r['quantity']} шт. × {int(r['price'])} руб. = <b>{int(r['quantity'])*int(r['price'])} руб.</b>\n"
            f"📞 {escape(r['phone'])} | 👤 {r['user_id']}\n"
            f"{SEPARATOR}"
        )
    return {"text": "\n".join(lines), "buttons": admin_menu_response()["buttons"], "format": "html"}


# === 4. Выдача ===
async def start_issue(user_id: str) -> dict:
    session = get_session(user_id)
    session.state = S_ADMIN_ISSUE_ORDER

    rows = await db.execute_read(
        "SELECT id, breed, date, quantity, price, phone FROM orders WHERE status = 'active' ORDER BY date"
    )
    if not rows:
        session.state = "idle"
        return {"text": "📭 Нет подтверждённых заказов для выдачи.", "buttons": admin_menu_response()["buttons"]}

    lines = ["🐣 <b>Выдача. Подтверждённые заказы:</b>\n"]
    buttons = []
    for r in rows:
        try:
            dt = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            dt = r["date"]
        lines.append(
            f"№<code>{r['id']}</code> | 🐔 <b>{escape(r['breed'])}</b> | {dt}\n"
            f"📦 {r['quantity']} шт. | 📞 {escape(r['phone'])}\n"
            f"{SEPARATOR}"
        )
        buttons.append([{"type": "message", "text": f"№{r['id']} — {r['breed']} ({r['quantity']} шт.)", "payload": f"{PAYLOAD_ADMIN_ISSUE_PREFIX}{r['id']}"}])

    lines.append("\nВыберите заказ или введите его номер:")
    buttons += _back_btn()
    return {"text": "\n".join(lines), "buttons": buttons, "format": "html"}


async def issue_select(user_id: str, order_id: int) -> dict:
    session = get_session(user_id)
    rows = await db.execute_read(
        "SELECT id, breed, date, quantity, price, phone, status FROM orders WHERE id = ?", (order_id,)
    )
    if not rows or rows[0]["status"] != "active":
        return {"text": "❌ Заказ не найден или не готов к выдаче.", "buttons": _back_btn()}

    r = rows[0]
    try:
        dt = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        dt = r["date"]
    session.data["issue_order_id"] = order_id
    session.state = S_ADMIN_ISSUE_CONFIRM

    text = (
        "🐣 <b>Выдать этот заказ?</b>\n\n"
        f"№<code>{r['id']}</code> | 🐔 <b>{escape(r['breed'])}</b>\n"
        f"📅 Поставка: <b>{dt}</b>\n"
        f"📦 <b>{r['quantity']}</b> шт.\n"
        f"📞 <b>{escape(r['phone'])}</b>"
    )
    return {
        "text": text,
        "buttons": [
            [
                {"type": "message", "text": "✅ Выдать", "payload": f"{PAYLOAD_ADMIN_ISSUE_CONFIRM}{order_id}"},
                {"type": "message", "text": "❌ Отмена", "payload": PAYLOAD_ADMIN_CANCEL_ISSUE},
            ]
        ],
        "format": "html",
    }


async def confirm_issue(user_id: str, order_id: int) -> dict:
    session = get_session(user_id)
    current = await db.execute_read("SELECT status FROM orders WHERE id = ?", (order_id,))
    if not current or current[0]["status"] != "active":
        session.state = "idle"
        return {"text": "❌ Заказ уже выдан или изменился.", "buttons": admin_menu_response()["buttons"]}

    ok = await db.execute_write(
        "UPDATE orders SET status = 'issued', issued_at = datetime('now') WHERE id = ?", (order_id,)
    )
    session.state = "idle"
    session.data.clear()
    if ok:
        return {
            "text": f"✅ Заказ №{order_id} выдан.",
            "buttons": admin_menu_response()["buttons"],
            "format": "html",
        }
    return {"text": "❌ Не удалось выдать заказ.", "buttons": admin_menu_response()["buttons"]}


# === Маршрутизация админки ===
async def handle_admin_message(messenger: str, user_id: str, text: str, chat_id: str, bot, user_name: str = "") -> dict:
    session = get_session(user_id)
    raw = (text or "").strip()

    if not is_max_admin(user_id):
        session.state = "idle"
        session.data.clear()
        return {"text": "❌ Доступ запрещён.", "buttons": _client_menu_response(user_name)["buttons"], "format": "html"}

    # Выход из админки
    if raw == PAYLOAD_ADMIN_EXIT:
        session.state = "idle"
        session.data.clear()
        return _client_menu_response(user_name)

    # /admin и "админ" — вход в панель
    if raw in ("/admin", "админ", "🔐 Админ-панель"):
        session.state = "idle"
        session.data.clear()
        return admin_menu_response()

    # Вернуться в меню админки
    if raw == PAYLOAD_ADMIN_MENU or raw == PAYLOAD_ADMIN_BACK:
        session.state = "idle"
        session.data.clear()
        return admin_menu_response()

    # --- Добавление партии ---
    if raw == PAYLOAD_ADMIN_ADD:
        return await start_add_stock(user_id)
    if raw.startswith(PAYLOAD_ADMIN_ADD_BREED):
        return await handle_add_breed(user_id, raw[len(PAYLOAD_ADMIN_ADD_BREED):])
    if raw.startswith(PAYLOAD_ADMIN_ADD_INCUBATOR):
        return await handle_add_incubator(user_id, raw[len(PAYLOAD_ADMIN_ADD_INCUBATOR):])
    if raw == PAYLOAD_ADMIN_CONFIRM_ADD:
        return await confirm_add_stock(user_id)

    # --- Остатки / Заказы ---
    if raw == PAYLOAD_ADMIN_STOCKS:
        return await stocks_response()
    if raw == PAYLOAD_ADMIN_ORDERS:
        return await orders_response()

    # --- Выдача ---
    if raw == PAYLOAD_ADMIN_ISSUE:
        return await start_issue(user_id)
    if raw.startswith(PAYLOAD_ADMIN_ISSUE_CONFIRM):
        try:
            return await confirm_issue(user_id, int(raw[len(PAYLOAD_ADMIN_ISSUE_CONFIRM):]))
        except ValueError:
            return admin_menu_response()
    if raw.startswith(PAYLOAD_ADMIN_ISSUE_PREFIX):
        try:
            return await issue_select(user_id, int(raw[len(PAYLOAD_ADMIN_ISSUE_PREFIX):]))
        except ValueError:
            return admin_menu_response()
    if raw == PAYLOAD_ADMIN_CANCEL_ISSUE:
        session.state = "idle"
        return admin_menu_response()

    # --- Свободный ввод (дата/количество/цена/номер заказа) ---
    if session.state == S_ADMIN_ADD_DATE:
        return await handle_add_date(user_id, raw)
    if session.state == S_ADMIN_ADD_QUANTITY:
        return await handle_add_quantity(user_id, raw)
    if session.state == S_ADMIN_ADD_PRICE:
        return await handle_add_price(user_id, raw)
    if session.state == S_ADMIN_ISSUE_ORDER:
        if raw.isdigit():
            try:
                return await issue_select(user_id, int(raw))
            except ValueError:
                pass
        return {"text": "❌ Введите номер заказа.", "buttons": _back_btn()}

    # Неизвестная админ-команда
    return admin_menu_response()
