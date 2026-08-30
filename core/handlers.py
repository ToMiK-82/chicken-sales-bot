"""
Единая точка входа для Telegram и MAX.
Полная поддержка:
- /start
- График поставок
- Акции (с фото)
- Справка (3 сообщения)
- Каталог с заказом (пошагово)
- Контакты
- Мои заказы + отмена
"""
import logging
import os
from typing import Tuple
from typing import Dict, Any, List
from html import escape
from datetime import date, datetime

# ✅ Глобальный импорт db
from database.repository import db
from core.session import get_session

logger = logging.getLogger(__name__)

# === Константы ===
CONTACTS_BUTTON_TEXT = "📞 Контакты"
ORDERS_BUTTON_TEXT = "📦 Мои заказы"
IMAGE_PATH = "images/zootopia.jpg"
WEBSITE_URL = "https://zootopia.ru"
# Версия бота (для MAX-адаптера, где нет Telegram-контекста; в Telegram берётся из bot_data)
BOT_VERSION = os.getenv("BOT_VERSION", "v4.9.9")

# === Payload кнопок (единые для Telegram и MAX) ===
# Маршрутизатор матчит именно эти строки — они же кладутся в payload кнопок.
PAYLOAD_START = "/start"
PAYLOAD_SCHEDULE = "schedule"
PAYLOAD_PROMOTIONS = "promotions"
PAYLOAD_CATALOG = "catalog"
PAYLOAD_CONTACTS = "contacts"
PAYLOAD_ORDERS = "orders"
PAYLOAD_HELP = "help"
PAYLOAD_BACK = "back"
PAYLOAD_CONFIRM_ORDER = "confirm_order"
PAYLOAD_CANCEL_ORDER = "cancel_order"

PAYLOAD_CATALOG_BREED = "catalog_breed_"      # + порода
PAYLOAD_CATALOG_INCUBATOR = "catalog_incubator_"  # + инкубатор
PAYLOAD_CATALOG_DATE = "catalog_date_"        # + дата
PAYLOAD_CANCEL_ORDER_PREFIX = "cancel_order_" # + id заказа


def make_tel_link(phone: str) -> str:
    cleaned = phone.replace(" ", "").replace("-", "")
    return f"tel:{cleaned}"


def _format_date(date_str: str) -> str:
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str.split()[0] if date_str else "—"


# === Состояния ===
SELECTING_BREED = "selecting_breed"
SELECTING_INCUBATOR = "selecting_incubator"
SELECTING_DATE = "selecting_date"
CHOOSE_QUANTITY = "choose_quantity"
ENTER_PHONE = "enter_phone"
CONFIRM_ORDER = "confirm_order"


# === Вспомогательные функции ===
SEPARATOR = "────────────────"


def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")


def main_menu_buttons():
    """Кнопки главного меню (аналог get_main_keyboard в Telegram)."""
    return [
        [
            {"type": "message", "text": "🐔 Каталог", "payload": PAYLOAD_CATALOG},
            {"type": "message", "text": "📅 График", "payload": PAYLOAD_SCHEDULE},
            {"type": "message", "text": ORDERS_BUTTON_TEXT, "payload": PAYLOAD_ORDERS},
        ],
        [
            {"type": "message", "text": "🎁 Акции", "payload": PAYLOAD_PROMOTIONS},
            {"type": "message", "text": "📞 Контакты", "payload": PAYLOAD_CONTACTS},
            {"type": "message", "text": "ℹ️ Справка", "payload": PAYLOAD_HELP},
        ],
    ]


def _back_button():
    """Стандартная кнопка «Назад» для ответов."""
    return [[{"type": "message", "text": "⬅️ Назад", "payload": PAYLOAD_BACK}]]


def _reset_session(session) -> None:
    """Полная очистка сессии пользователя."""
    session.state = "idle"
    session.data.clear()


async def get_available_breeds_from_db():
    try:
        result = await db.execute_read(
            "SELECT DISTINCT breed FROM stocks WHERE available_quantity > 0 AND status = 'active' AND date >= ?",
            (get_today_str(),)
        )
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пород: {e}")
        return []


# === 1. Форматирование графика поставок ===
async def format_schedule_message() -> str:
    try:
        today = date.today().isoformat()
        result = await db.execute_read(
            """
            SELECT breed, incubator, date, available_quantity, quantity, price 
            FROM stocks 
            WHERE quantity > 0 AND status = 'active' AND date >= ?
            ORDER BY date
            """,
            (today,)
        )

        if not result:
            return "📅 Нет активных поставок на ближайшее время."

        message_lines = ["📦 <b>График поставок:</b>", SEPARATOR]
        for record in result:
            breed, incubator, raw_date, avail_qty, total_qty, price = record
            try:
                avail = max(int(avail_qty or 0), 0)
                total = max(int(total_qty or 0), 1)
                percent = (avail / total) * 100
            except (ValueError, TypeError):
                continue

            icon = "🟢" if percent >= 50 else "🟡" if percent >= 10 else "🔴"

            try:
                price_value = int(float(price or 0))
            except (ValueError, TypeError):
                price_value = 0

            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d")
                formatted_date = dt.strftime("%d-%m-%Y")
            except ValueError:
                formatted_date = raw_date

            breed_safe = escape(breed)
            incubator_safe = escape(incubator) if incubator else "Не указан"

            message_lines.append(
                f"🐔 <b>Порода:</b> {breed_safe}\n"
                f"🏢 <b>Инкубатор:</b> {incubator_safe}\n"
                f"📅 <b>Поставка:</b> {formatted_date}\n"
                f"{icon} <b>Доступно:</b> {avail} шт.\n"
                f"💰 <b>Цена:</b> {price_value} руб."
            )
            message_lines.append(SEPARATOR)

        if message_lines and message_lines[-1] == SEPARATOR:
            message_lines.pop()

        return "\n".join(message_lines).strip()

    except Exception as e:
        logger.error(f"❌ Ошибка формирования графика: {e}", exc_info=True)
        return "⚠️ Ошибка при загрузке графика."


# === 2. Получение акций ===
async def get_formatted_promotions() -> List[Dict[str, Any]]:
    try:
        promotions = await db.get_active_promotions()
        if not promotions:
            return [{"text": "📭 Нет активных акций.", "buttons": main_menu_buttons(), "format": "html"}]

        result = []
        for promo in promotions:
            try:
                title = escape(str(promo['title']))
                desc = escape(str(promo['description']))
                image_url = str(promo['image_url']).strip() if promo['image_url'] else None
                start_date = promo['start_date']
                end_date = promo['end_date']

                start_str = f"📅 Начало: {start_date}\n" if start_date else ""
                end_str = f"🔚 Окончание: {end_date}\n" if end_date else "🔚 Окончание: бессрочно\n"
                text = f"🎁 <b>{title}</b>\n\n{start_str}{end_str}{desc}"

                result.append({
                    "text": text,
                    "image_url": image_url,
                    "format": "html",
                })
            except Exception as e:
                logger.error(f"❌ Ошибка формирования акции: {e}", exc_info=True)

        # Итоговое сообщение с кнопками главного меню (как в Telegram)
        result.append({
            "text": "🚀 Следите за новыми предложениями!",
            "buttons": main_menu_buttons(),
            "format": "html",
        })

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки акций: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка загрузки акций.", "buttons": main_menu_buttons(), "format": "html"}]


# === 3. Справка — много сообщений ===
async def get_help_response(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        # bot может быть None (MAX-адаптер) — не падаем, подставляем метку канала
        bot = context.get("bot") if context else None
        bot_version = BOT_VERSION
        if bot is not None:
            try:
                bot_version = bot.application.bot_data.get("BOT_VERSION", BOT_VERSION)
            except Exception:
                bot_version = BOT_VERSION

        main_text = (
            "📘 <b>Справка: как пользоваться ботом?</b>\n\n"
            "Этот бот поможет вам быстро и удобно заказать <b>суточных цыплят</b> нужной породы.\n\n"
            "📌 <b>Доступные действия:</b>\n\n"
            "🔹 <b>Главное меню</b>\n"
            "Используйте кнопки внизу для навигации:\n"
            "• 🐔 <b>Каталог</b> — выбрать и оформить заказ\n"
            "• 📅 <b>График</b> — посмотреть все поставки\n"
            "• 🎯 <b>Акции</b> — скидки и спецпредложения\n"
            "• 📦 <b>Мои заказы</b> — отслеживать и отменять\n"
            "• 📞 <b>Контакты</b> — связь с менеджером\n"
            "• ℹ️ <b>Справка</b> — эта страница\n\n"
            "📌 <b>Как сделать заказ:</b>\n"
            "1. Нажмите «🐔 Каталог»\n"
            "2. Выберите породу → инкубатор → дату → количество\n"
            "3. Введите номер телефона\n"
            "4. Подтвердите заказ\n"
            "Готово! Вы получите уведомление перед поставкой.\n\n"
            "🔔 <b>Совет:</b>\n"
            "При любом затруднении нажмите /back или /start — вы вернётесь в главное меню.\n\n"
            "Если остались вопросы — напишите менеджеру через «📞 Контакты». Мы всегда на связи! 🙏"
        )

        commands_text = (
            "⌨️ <b>Полезные команды (нажмите, чтобы использовать):</b>\n\n"
            "/start — перезапустить бот\n"
            "/back — вернуться в меню\n"
            "/help — показать эту справку"
        )

        contact_text = (
            f"🔧 <b>Техническая информация:</b>\n"
            f"• Версия: <code>{bot_version}</code>\n"
            f"• Поддержка: <a href='tel:+79787292469'>+7 978 7292469</a>"
        )

        return [
            {"text": main_text, "buttons": main_menu_buttons(), "format": "html"},
            {"text": commands_text, "format": "html"},
            {"text": contact_text, "format": "html"},
        ]

    except Exception as e:
        logger.error(f"❌ Ошибка при формировании справки: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка загрузки справки.", "buttons": main_menu_buttons(), "format": "html"}]


# === 4. Контакты — как в Telegram (полная информация) ===
async def get_contacts_response() -> List[Dict[str, Any]]:
    message = (
        "Наша компания предлагает широкий ассортимент товаров для сельскохозяйственных животных и домашних питомцев,\n"
        "включая корма, аксессуары, игрушки и товары для рыбалки 😊.\n\n"
        "📩 Чтобы связаться с менеджером:\n"
        "🌍 Крым\n"
        f"- Лилия 📞 {make_tel_link('+7 978 061 25 52')}\n"
        "  Региональный склад, Красногвардейский район, с. Полтавка, ул. Строителей, 15;\n"
        f"- Анастасия 📞 {make_tel_link('+7 978 589 93 07')}\n"
        "  Сакский, Черноморский, Раздольненский, Первомайский, Красноперекопский и Джанкойский районы;\n"
        f"- Павел 📞 {make_tel_link('+7 978 589 93 15')}\n"
        "  Красногвардейский, Нижнегорский, Советский, Кировский, Белогорский и Ленинский районы;\n"
        f"- Денис 📞 {make_tel_link('+7 978 697 43 09')}\n"
        "  Симферопольский и Бахчисарайский районы, г. Севастополь и ЮБК.\n\n"
        "🌍 Херсонская область\n"
        f"- Андрей 📞 {make_tel_link('+7 978 589 91 67')}\n\n"
        "🌍 Запорожская область\n"
        f"- Павел 📞 {make_tel_link('+7 990 144 36 63')}\n"
        "  Региональный склад, Запорожская область, г. Мелитополь, Каховское шоссе, 24/2;\n"
        f"- Вадим 📞 {make_tel_link('+7 990 144 70 03')}\n\n"
        "📞 Если нужна помощь с выбором или расчётом объёма — просто начните оформление, и мы поможем!\n\n"
        f"🌐 Полный ассортимент на сайте — <a href='{WEBSITE_URL}'>ZOOTOPIA.RU</a>"
    )

    result = []

    if os.path.exists(IMAGE_PATH):
        result.append({
            "image_url": f"file://{os.path.abspath(IMAGE_PATH)}"
        })

    result.append({
        "text": message,
        "buttons": main_menu_buttons(),
        "format": "html"
    })

    return result


# === 5. Мои заказы + отмена (для MAX и Telegram) ===
async def get_orders_response(user_id: str) -> List[Dict[str, Any]]:
    try:
        result = await db.execute_read(
            """
            SELECT id, breed, date, incubator, quantity, price, status, created_at, stock_id, phone
            FROM orders
            WHERE user_id = ? AND status IN ('pending', 'active')
            ORDER BY created_at DESC
            """,
            (int(user_id),)
        )

        if not result:
            return [{"text": "📭 У вас нет активных заказов.", "buttons": main_menu_buttons(), "format": "html"}]

        message_lines = ["📦 <b>Ваши заказы:</b>\n"]
        buttons = []

        for idx, row in enumerate(result, start=1):
            try:
                qty = int(row["quantity"])
                price_val = float(row["price"])
                total = qty * price_val
                formatted_date = _format_date(row["date"])
                formatted_created = _format_date(row["created_at"])
                breed_safe = escape(row["breed"])
                phone_safe = escape(str(row["phone"]) if row["phone"] else "Не указан")
                stock_info = f" | 🏷️<code>{row['stock_id']}</code>" if row["stock_id"] else ""

                status_emoji = "🟡" if row["status"] == "pending" else "🟢"
                status_text = "ожидает подтверждения" if row["status"] == "pending" else "подтверждён"

                # Текст заказа (как в Telegram)
                order_text = (
                    f"{status_emoji} <b>{idx}.</b> 🐔 {breed_safe}{stock_info}\n"
                    f"📅 <b>Поставка:</b> {formatted_date}\n"
                    f"🕒 <b>Создан:</b> {formatted_created}\n"
                    f"📦 <b>{qty} шт.</b> × <b>{int(price_val)} руб.</b> = <b>{int(total)} руб.</b>\n"
                    f"📞 <b>Телефон:</b> {phone_safe}\n"
                    f"ℹ️ <i>{status_text}</i>\n"
                    f"{SEPARATOR}"
                )
                message_lines.append(order_text)

                # Кнопка отмены — только для pending
                if row["status"] == "pending":
                    buttons.append([{
                        "type": "message",
                        "text": f"❌ Отменить №{idx}",
                        "payload": f"{PAYLOAD_CANCEL_ORDER_PREFIX}{row['id']}"
                    }])
            except Exception as e:
                logger.error(f"❌ Ошибка обработки заказа {row.get('id', 'unknown')}: {e}")
                continue

        full_text = "\n".join(message_lines) + "\n\nВыберите действие:"

        # Общие кнопки: отмена заказов + главное меню (всегда на последнем сообщении)
        buttons += main_menu_buttons()

        return [{
            "text": full_text,
            "buttons": buttons,
            "format": "html"
        }]

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке заказов: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка при загрузке заказов.", "buttons": main_menu_buttons(), "format": "html"}]


# === Отмена заказа ===
async def cancel_order_by_id(order_id: int, user_id: str) -> Tuple[bool, str]:
    """
    Отменяет заказ по ID.
    Возвращает (успех, сообщение).
    """
    try:
        # Проверяем, существует ли и его статус
        current = await db.execute_read(
            "SELECT status, quantity, stock_id FROM orders WHERE id = ?",
            (order_id,)
        )
        if not current:
            return False, "Заказ не найден."

        row = current[0]
        if row["status"] != "pending":
            return False, "Заказ уже подтверждён и не может быть отменён."

        if not row["stock_id"]:
            return False, "Заказ не привязан к партии."

        # Откатываем количество и оживляем партию, если она была распродана
        success = await db.execute_transaction([
            ("UPDATE stocks SET available_quantity = available_quantity + ? WHERE id = ?", (row["quantity"], row["stock_id"])),
            ("UPDATE stocks SET status = 'active' WHERE id = ? AND available_quantity > 0", (row["stock_id"],)),
            ("UPDATE orders SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?", (order_id,))
        ])

        if success:
            return True, f"✅ Заказ №{order_id} отменён. {row['quantity']} шт. возвращены в партию."
        else:
            return False, "❌ Не удалось отменить заказ."

    except Exception as e:
        logger.error(f"❌ Ошибка при отмене заказа {order_id}: {e}", exc_info=True)
        return False, "Ошибка при отмене заказа."


# === 6. Каталог для MAX (пошагово) ===
async def start_catalog_flow(user_id: str, chat_id: str) -> Dict[str, Any]:
    session = get_session(user_id)
    session.chat_id = chat_id
    session.state = SELECTING_BREED
    session.data.clear()

    try:
        trusted_phone = await db.get_trusted_phone_for_user(int(user_id))
        if trusted_phone:
            session.data.update({"phone": trusted_phone, "phone_verified": True})
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки доверенного номера: {e}")

    available_breeds = await get_available_breeds_from_db()
    if not available_breeds:
        return {"text": "📅 Нет доступных пород."}

    buttons = [[{
        "type": "message",
        "text": f"🐔 {breed}",
        "payload": f"catalog_breed_{breed}"
    }] for breed in available_breeds]

    buttons.append([{"type": "message", "text": "⬅️ Назад", "payload": "back"}])

    return {
        "text": "🐔 Выберите породу:",
        "buttons": buttons
    }


async def handle_catalog_breed(user_id: str, breed: str) -> Dict[str, Any]:
    session = get_session(user_id)
    available_breeds = await get_available_breeds_from_db()
    if breed not in available_breeds:
        return {"text": "❌ Неизвестная порода."}

    session.data["selected_breed"] = breed
    session.state = SELECTING_INCUBATOR

    result = await db.execute_read(
        "SELECT DISTINCT incubator FROM stocks WHERE breed = ? AND available_quantity > 0 AND status = 'active' AND date >= ?",
        (breed, get_today_str())
    )
    if not result:
        return {"text": "🏭 Нет доступных инкубаторов."}

    incubators = [row[0] for row in result]
    session.data["available_incubators"] = incubators

    buttons = [[{
        "type": "message",
        "text": f"🏭 {inc}",
        "payload": f"catalog_incubator_{inc}"
    }] for inc in incubators]

    buttons.append([{"type": "message", "text": "⬅️ Назад", "payload": "back"}])

    return {
        "text": "🏢 Выберите инкубатор:",
        "buttons": buttons
    }


async def handle_catalog_incubator(user_id: str, incubator: str) -> Dict[str, Any]:
    session = get_session(user_id)
    # Защита: если клик пришёл вне потока (без выбранной породы) — не падаем
    breed = session.data.get("selected_breed")
    if not breed:
        return {"text": "⚠️ Начните с выбора породы.", "buttons": _back_button()}
    session.data["selected_incubator"] = incubator
    session.state = SELECTING_DATE
    result = await db.execute_read(
        "SELECT date, available_quantity, price FROM stocks WHERE breed = ? AND incubator = ? AND available_quantity > 0 AND status = 'active' ORDER BY date ASC",
        (breed, incubator)
    )

    today = datetime.now().date()
    filtered = []
    for date_str, qty, price in result:
        stock_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if stock_date >= today:
            filtered.append((date_str, qty, price))

    if not filtered:
        return {"text": "📅 Нет доступных дат."}

    session.data["available_dates"] = filtered

    buttons = [[{
        "type": "message",
        "text": f"📅 {datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m')} | 📦{qty} шт. | 💰{int(price)} руб.",
        "payload": f"{PAYLOAD_CATALOG_DATE}{d}"
    }] for d, qty, price in filtered]

    buttons.append([{"type": "message", "text": "⬅️ Назад", "payload": "back"}])

    return {
        "text": "📅 Выберите дату поставки:",
        "buttons": buttons
    }


async def handle_catalog_date(user_id: str, date_str: str) -> Dict[str, Any]:
    session = get_session(user_id)
    available = next((d for d in session.data.get("available_dates", []) if d[0] == date_str), None)
    if not available:
        return {"text": "❌ Дата недоступна."}

    qty, price = available[1], available[2]
    session.data.update({
        "selected_date": date_str,
        "available_quantity": qty,
        "selected_price": price
    })
    session.state = CHOOSE_QUANTITY

    try:
        delivery_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        delivery_date = date_str

    return {
        "text": f"📅 *Поставка:* {delivery_date}\n📦 *Доступно:* {qty} шт.\n💰 *Цена:* {int(price)} руб.\n\nВведите количество:",
        "buttons": _back_button(),
        "format": "markdown"
    }


async def handle_catalog_quantity(user_id: str, text: str) -> Dict[str, Any]:
    session = get_session(user_id)
    if not text.isdigit():
        return {"text": "❌ Введите число."}

    qty = int(text)
    avail = session.data.get("available_quantity", 0)
    if not (1 <= qty <= avail):
        return {"text": f"❌ Допустимо от 1 до {avail}."}

    session.data["selected_quantity"] = qty
    session.state = ENTER_PHONE

    phone = session.data.get("phone")
    if phone and session.data.get("phone_verified"):
        return await confirm_order_preview(user_id)
    else:
        return {
            "text": "📞 Введите номер телефона в формате +7XXXXXXXXXX",
            "buttons": _back_button()
        }


async def handle_catalog_phone(user_id: str, phone: str) -> Dict[str, Any]:
    session = get_session(user_id)
    qty = session.data.get("selected_quantity")
    if qty is None:
        return {"text": "⚠️ Начните оформление заново.", "buttons": _back_button()}

    if phone.startswith("8") and len(phone) == 11:
        phone = "+7" + phone[1:]
    elif not phone.startswith("+7"):
        return {"text": "❌ Введите +7XXXXXXXXXX"}

    if await db.is_phone_blocked(phone):
        session.state = "idle"
        session.data.clear()
        return {"text": "🚫 Номер заблокирован."}

    session.data["phone"] = phone
    session.data["phone_verified"] = await db.is_trusted_phone(phone)

    is_admin = False
    if not session.data["phone_verified"] and qty > 50 and not is_admin:
        return {"text": "📞 Для заказа >50 шт. нужен верифицированный номер."}

    return await confirm_order_preview(user_id)


async def confirm_order_preview(user_id: str) -> Dict[str, Any]:
    session = get_session(user_id)
    session.state = CONFIRM_ORDER

    data = session.data
    try:
        delivery_date = datetime.strptime(data["selected_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        delivery_date = data["selected_date"]

    total = int(data["selected_quantity"] * data["selected_price"])

    return {
        "text": (
            f"📄 *Подтверждение заказа*\n\n"
            f"*Порода:* {escape(data['selected_breed'])}\n"
            f"*Инкубатор:* {escape(data['selected_incubator'])}\n"
            f"*Поставка:* {delivery_date}\n"
            f"*Кол-во:* {data['selected_quantity']} шт.\n"
            f"*Цена:* {int(data['selected_price'])} руб.\n"
            f"*Сумма:* {total} руб.\n"
            f"*Телефон:* {data['phone']}\n\n"
            "Подтвердите заказ?"
        ),
        "buttons": [
            [
                {"type": "message", "text": "✅ Подтвердить", "payload": PAYLOAD_CONFIRM_ORDER},
                {"type": "message", "text": "❌ Отменить", "payload": PAYLOAD_CANCEL_ORDER}
            ],
            [{"type": "message", "text": "⬅️ Назад", "payload": PAYLOAD_BACK}]
        ],
        "format": "markdown"
    }


async def confirm_order_final(user_id: str) -> Dict[str, Any]:
    session = get_session(user_id)
    data = session.data

    # Защита: кнопка «Подтвердить» нажата вне активного потока заказа
    required = ("selected_breed", "selected_incubator", "selected_date", "selected_quantity", "selected_price", "phone")
    if not all(k in data for k in required):
        _reset_session(session)
        return {"text": "⚠️ Сессия заказа истекла. Начните заново.", "buttons": _back_button()}

    stock_id = await db.get_stock_id(data["selected_breed"], data["selected_incubator"], data["selected_date"])
    if not stock_id:
        return {"text": "❌ Партия не найдена."}

    stock = await db.execute_read("SELECT available_quantity FROM stocks WHERE id = ?", (stock_id,))
    if not stock or data["selected_quantity"] > stock[0][0]:
        _reset_session(session)
        return {"text": "❌ Количество изменилось. Попробуйте снова."}

    success = await db.execute_transaction([
        ("INSERT INTO orders (user_id, phone, breed, date, quantity, price, stock_id, incubator, status, created_at, updated_at) "
         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'), datetime('now'))",
         (int(user_id), data["phone"], data["selected_breed"], data["selected_date"],
          data["selected_quantity"], data["selected_price"], stock_id, data["selected_incubator"])),

        ("UPDATE stocks SET available_quantity = available_quantity - ? WHERE id = ? AND available_quantity >= ?",
         (data["selected_quantity"], stock_id, data["selected_quantity"])),

        ("UPDATE stocks SET status = 'inactive' WHERE id = ? AND (SELECT available_quantity FROM stocks WHERE id = ?) <= 0",
         (stock_id, stock_id)),
    ])

    if not success:
        return {"text": "❌ Не удалось оформить заказ. Попробуйте позже."}

    try:
        delivery_date = datetime.strptime(data["selected_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        delivery_date = data["selected_date"]

    # ФОРМИРУЕМ сообщение ДО очистки сессии (data — ссылка на session.data!)
    result_text = (
        f"✅ *Заказ оформлен!* 🎉\n\n"
        f"🐔 *Порода:* {escape(data['selected_breed'])}\n"
        f"🏭 *Инкубатор:* {escape(data['selected_incubator'])}\n"
        f"📅 *Поставка:* {delivery_date}\n"
        f"📦 *Кол-во:* {data['selected_quantity']} шт.\n"
        f"📞 *Телефон:* {data['phone']}\n\n"
        "Спасибо за заказ! Мы свяжемся с вами за день до поставки."
    )

    _reset_session(session)

    return {
        "text": result_text,
        "format": "markdown"
    }


# === Главное меню (единая точка) ===
def main_menu_response(user_name: str = "") -> Dict[str, Any]:
    """Приветствие как в Telegram: 👋 Привет, {имя}! ..."""
    name = escape(user_name.strip()) if user_name and user_name.strip() else "Друг"
    text = (
        f"👋 Привет, <b>{name}</b>!\n"
        "Добро пожаловать в сервис <b>Chicken_sales_bot</b>! 🐔\n\n"
        "Мы осуществляем продажу суточных цыплят сельскохозяйственных пород.\n"
        "Выберите нужный раздел 👇"
    )
    return {
        "text": text,
        "buttons": main_menu_buttons(),
        "format": "html",
    }


def _fallback_menu_response() -> Dict[str, Any]:
    return {
        "text": "👋 Привет! Используйте меню.",
        "buttons": main_menu_buttons(),
        "format": "html",
    }


# === Главная маршрутизация ===
async def handle_message_from_messenger(
    messenger: str, user_id: str, text: str, chat_id: str, bot, user_name: str = ""
) -> Any:
    logger.info(f"[{messenger.upper()}] Получено: {text} от {user_id}")

    context = {
        "messenger": messenger,
        "user_id": user_id,
        "chat_id": chat_id,
        "bot": bot,
        "text": text,
        "user_name": user_name,
    }

    session = get_session(user_id)

    # Нормализуем входящий текст (payload кнопок тоже приходит сюда как text)
    raw_text = (text or "").strip()
    text_lower = raw_text.lower()

    # --- /start ---
    if raw_text == "/start" or raw_text == PAYLOAD_START:
        _reset_session(session)
        return main_menu_response(user_name=user_name)

    # --- Мои заказы ---
    if raw_text == PAYLOAD_ORDERS or "мои заказы" in text_lower:
        return await get_orders_response(user_id)

    # --- Отмена заказа (payload: cancel_order_<id>) ---
    if raw_text.startswith(PAYLOAD_CANCEL_ORDER_PREFIX):
        try:
            order_id = int(raw_text.split("_")[-1])
            success, msg = await cancel_order_by_id(order_id, user_id)
            if success:
                return await get_orders_response(user_id)
            else:
                return {"text": msg}
        except (ValueError, IndexError):
            return {"text": "❌ Неверный формат номера заказа."}

    # --- График ---
    if raw_text == PAYLOAD_SCHEDULE or "график" in text_lower:
        text_only = await format_schedule_message()
        return {"text": text_only, "buttons": main_menu_buttons(), "format": "html"}

    # --- Акции ---
    if raw_text == PAYLOAD_PROMOTIONS or "акции" in text_lower:
        return await get_formatted_promotions()

    # --- Контакты ---
    if raw_text == PAYLOAD_CONTACTS or "контакты" in text_lower:
        return await get_contacts_response()

    # --- Справка ---
    if raw_text == PAYLOAD_HELP or "справка" in text_lower or raw_text == "/help":
        return await get_help_response(context)

    # --- Каталог ---
    if raw_text == PAYLOAD_CATALOG or "каталог" in text_lower:
        return await start_catalog_flow(user_id, chat_id)

    # --- Callback: выбор породы ---
    if raw_text.startswith(PAYLOAD_CATALOG_BREED):
        breed = raw_text[len(PAYLOAD_CATALOG_BREED):]
        return await handle_catalog_breed(user_id, breed)

    # --- Callback: инкубатор ---
    if raw_text.startswith(PAYLOAD_CATALOG_INCUBATOR):
        inc = raw_text[len(PAYLOAD_CATALOG_INCUBATOR):]
        return await handle_catalog_incubator(user_id, inc)

    # --- Callback: дата ---
    if raw_text.startswith(PAYLOAD_CATALOG_DATE):
        date_str = raw_text[len(PAYLOAD_CATALOG_DATE):]
        return await handle_catalog_date(user_id, date_str)

    # --- Callback: подтвердить/отменить заказ ---
    if raw_text == PAYLOAD_CONFIRM_ORDER:
        return await confirm_order_final(user_id)
    if raw_text == PAYLOAD_CANCEL_ORDER:
        _reset_session(session)
        return {"text": "❌ Заказ отменён."}

    # --- Назад / отмена ввода ---
    if raw_text == PAYLOAD_BACK or "назад" in text_lower:
        _reset_session(session)
        return main_menu_response(user_name=user_name)

    # --- Ввод количества или телефона (активный диалог) ---
    if session.state == CHOOSE_QUANTITY:
        return await handle_catalog_quantity(user_id, raw_text)
    if session.state == ENTER_PHONE:
        return await handle_catalog_phone(user_id, raw_text)

    return _fallback_menu_response()
