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


def make_tel_link(phone: str) -> str:
    cleaned = phone.replace(" ", "").replace("-", "").replace("+", "")
    return f"tel:+7{cleaned}"


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
def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")


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

        message_lines = ["📦 *График поставок:*", ""]
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
                f"🐔 *Порода:* {breed_safe}\n"
                f"🏢 *Инкубатор:* {incubator_safe}\n"
                f"📅 *Поставка:* {formatted_date}\n"
                f"{icon} *Доступно:* {avail} шт.\n"
                f"💰 *Цена:* {price_value} руб."
            )
            message_lines.append("")

        return "\n".join(message_lines).strip()

    except Exception as e:
        logger.error(f"❌ Ошибка формирования графика: {e}", exc_info=True)
        return "⚠️ Ошибка при загрузке графика."


# === 2. Получение акций ===
async def get_formatted_promotions() -> List[Dict[str, Any]]:
    try:
        promotions = await db.get_active_promotions()
        if not promotions:
            return [{"text": "📭 Нет активных акций.", "image_url": None}]

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
                text = f"🎁 *{title}*\n\n{start_str}{end_str}{desc}"

                result.append({
                    "text": text,
                    "image_url": image_url
                })
            except Exception as e:
                logger.error(f"❌ Ошибка формирования акции: {e}", exc_info=True)

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки акций: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка загрузки акций.", "image_url": None}]


# === 3. Справка — много сообщений ===
async def get_help_response(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        bot_version = context["bot"].application.bot_data.get("BOT_VERSION", "?.?")

        main_text = (
            "📘 *Справка: как пользоваться ботом?*\n\n"
            "Этот бот поможет вам быстро и удобно заказать *суточных цыплят* нужной породы.\n\n"
            "*📌 Доступные действия:*\n\n"
            "🔹 *Главное меню*\n"
            "• 🐔 Каталог — выбрать и оформить заказ\n"
            "• 📅 График — посмотреть все поставки\n"
            "• 🎯 Акции — скидки и спецпредложения\n"
            "• 📦 Мои заказы — отслеживать и отменять\n"
            "• 📞 Контакты — связь с менеджером\n"
            "• ℹ️ Справка — эта страница\n\n"
            "*📌 Как сделать заказ:*\n"
            "1. Нажмите «🐔 Каталог»\n"
            "2. Выберите породу → инкубатор → дату → количество\n"
            "3. Введите номер телефона\n"
            "4. Подтвердите заказ\n"
            "Готово! Вы получите уведомление перед поставкой.\n\n"
            "*🔔 Совет:*\n"
            "При любом затруднении нажмите /back или /start — вы вернётесь в главное меню.\n\n"
            "Если остались вопросы — напишите менеджеру через «📞 Контакты». Мы всегда на связи! 🙏"
        )

        commands_text = (
            "⌨️ *Полезные команды:*\n\n"
            "/start — перезапустить бот\n"
            "/back — вернуться в меню\n"
            "/help — показать эту справку"
        )

        contact_text = (
            f"🔧 *Техническая информация:*\n"
            f"• Версия: `{bot_version}`\n"
            f"• Поддержка: +7 978 729-24-69\n"
            f"• Для звонка: нажмите и удерживайте номер"
        )

        return [
            {"text": main_text},
            {"text": commands_text},
            {"text": contact_text}
        ]

    except Exception as e:
        logger.error(f"❌ Ошибка при формировании справки: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка загрузки справки."}]


# === 4. Контакты — универсальная поддержка ===
async def get_contacts_response() -> List[Dict[str, Any]]:
    message = (
        "Наша компания предлагает широкий ассортимент товаров для сельскохозяйственных животных и домашних питомцев,\n"
        "включая корма, аксессуары, игрушки и товары для рыбалки 😊.\n\n"
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
        "buttons": [[{
            "type": "link",
            "text": "🌐 Перейти на сайт",
            "url": WEBSITE_URL
        }]],
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
            return [{"text": "📭 У вас нет активных заказов."}]

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

                # Текст заказа
                order_text = (
                    f"{status_emoji} <b>{idx}.</b> 🐔 {breed_safe}{stock_info}\n"
                    f"📅 <b>Поставка:</b> {formatted_date}\n"
                    f"🕒 <b>Создан:</b> {formatted_created}\n"
                    f"📦 <b>{qty} шт.</b> × <b>{int(price_val)} руб.</b> = <b>{int(total)} руб.</b>\n"
                    f"📞 <b>Телефон:</b> {phone_safe}\n"
                    f"ℹ️ <i>{status_text}</i>"
                )
                message_lines.append(order_text)

                # Кнопка отмены — только для pending
                if row["status"] == "pending":
                    buttons.append([{
                        "type": "message",
                        "text": f"❌ Отменить №{idx}",
                        "payload": f"cancel_order_{row['id']}"
                    }])
            except Exception as e:
                logger.error(f"❌ Ошибка обработки заказа {row.get('id', 'unknown')}: {e}")
                continue

        full_text = "\n\n".join(message_lines)

        # Общие кнопки
        buttons.append([{"type": "message", "text": "⬅️ Назад", "payload": "back"}])

        return [{
            "text": full_text,
            "buttons": buttons,
            "format": "html"
        }]

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке заказов: {e}", exc_info=True)
        return [{"text": "⚠️ Ошибка при загрузке заказов."}]


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

        # Откатываем количество
        success = await db.execute_transaction([
            ("UPDATE stocks SET available_quantity = available_quantity + ? WHERE id = ?", (row["quantity"], row["stock_id"])),
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
    session.data["selected_incubator"] = incubator
    session.state = SELECTING_DATE

    breed = session.data["selected_breed"]
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
        "payload": f"catalog_date_{d}"
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
        "buttons": [[{"type": "message", "text": "⬅️ Назад", "payload": "back"}]],
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
            "buttons": [[{"type": "message", "text": "⬅️ Назад", "payload": "back"}]]
        }


async def handle_catalog_phone(user_id: str, phone: str) -> Dict[str, Any]:
    session = get_session(user_id)
    qty = session.data["selected_quantity"]

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
                {"type": "message", "text": "✅ Подтвердить", "payload": "confirm_order"},
                {"type": "message", "text": "❌ Отменить", "payload": "cancel_order"}
            ],
            [{"type": "message", "text": "⬅️ Назад", "payload": "back"}]
        ],
        "format": "markdown"
    }


async def confirm_order_final(user_id: str) -> Dict[str, Any]:
    session = get_session(user_id)
    data = session.data

    stock_id = await db.get_stock_id(data["selected_breed"], data["selected_incubator"], data["selected_date"])
    if not stock_id:
        return {"text": "❌ Партия не найдена."}

    stock = await db.execute_read("SELECT available_quantity FROM stocks WHERE id = ?", (stock_id,))
    if not stock or data["selected_quantity"] > stock[0][0]:
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

    session.state = "idle"
    session.data.clear()

    return {
        "text": (
            f"✅ *Заказ оформлен!* 🎉\n\n"
            f"🐔 *Порода:* {escape(data['selected_breed'])}\n"
            f"🏭 *Инкубатор:* {escape(data['selected_incubator'])}\n"
            f"📅 *Поставка:* {delivery_date}\n"
            f"📦 *Кол-во:* {data['selected_quantity']} шт.\n"
            f"📞 *Телефон:* {data['phone']}\n\n"
            "Спасибо за заказ! Мы свяжемся с вами за день до поставки."
        ),
        "format": "markdown"
    }


# === Главная маршрутизация ===
async def handle_message_from_messenger(messenger: str, user_id: str, text: str, chat_id: str, bot) -> Any:
    logger.info(f"[{messenger.upper()}] Получено: {text} от {user_id}")

    context = {
        "messenger": messenger,
        "user_id": user_id,
        "chat_id": chat_id,
        "bot": bot,
        "text": text
    }

    session = get_session(user_id)

    # --- /start ---
    if text == "/start":
        session.state = "idle"
        session.data.clear()
        return {
            "text": "🐔 Добро пожаловать!\n\nДоступные команды:\n• График\n• Акции\n• Каталог\n• Справка",
            "buttons": [
                [{"type": "message", "text": "📅 График", "payload": "schedule"}, {"type": "message", "text": "🎁 Акции", "payload": "promotions"}],
                [{"type": "message", "text": "📋 Каталог", "payload": "catalog"}, {"type": "message", "text": "📞 Контакты", "payload": "contacts"}],
                [{"type": "message", "text": ORDERS_BUTTON_TEXT, "payload": "orders"}, {"type": "message", "text": "ℹ️ Справка", "payload": "help"}]
            ]
        }

    # --- Мои заказы ---
    elif "мои заказы" in text.lower() or text == "orders":
        return await get_orders_response(user_id)

    # --- Отмена заказа ---
    elif text.startswith("cancel_order_"):
        try:
            order_id = int(text.split("_")[-1])
            success, msg = await cancel_order_by_id(order_id, user_id)
            if success:
                return await get_orders_response(user_id)
            else:
                return {"text": msg}
        except (ValueError, IndexError):
            return {"text": "❌ Неверный формат номера заказа."}

    # --- График ---
    elif "график" in text.lower():
        text_only = await format_schedule_message()
        return {"text": text_only}

    # --- Акции ---
    elif "акции" in text.lower():
        return await get_formatted_promotions()

    # --- Контакты ---
    elif "контакты" in text.lower() or text == "contacts":
        return await get_contacts_response()

    # --- Справка ---
    elif "справка" in text.lower() or text == "/help":
        return await get_help_response(context)

    # --- Каталог ---
    elif "каталог" in text.lower():
        return await start_catalog_flow(user_id, chat_id)

    # --- Callback: выбор породы ---
    elif text.startswith("__callback:catalog_breed_"):
        breed = text[len("__callback:catalog_breed_"):]
        return await handle_catalog_breed(user_id, breed)

    # --- Callback: инкубатор ---
    elif text.startswith("__callback:catalog_incubator_"):
        inc = text[len("__callback:catalog_incubator_"):]
        return await handle_catalog_incubator(user_id, inc)

    # --- Callback: дата ---
    elif text.startswith("__callback:catalog_date_"):
        date_str = text[len("__callback:catalog_date_"):]
        return await handle_catalog_date(user_id, date_str)

    # --- Callback: подтвердить/отменить ---
    elif text == "__callback:confirm_order":
        return await confirm_order_final(user_id)
    elif text == "__callback:cancel_order":
        session.state = "idle"
        session.data.clear()
        return {"text": "❌ Заказ отменён."}

    # --- Назад ---
    elif "назад" in text.lower() or "__callback:back__" in text:
        session.state = "idle"
        session.data.clear()
        return await handle_message_from_messenger(messenger, user_id, "/start", chat_id, bot)

    # --- Ввод количества или телефона ---
    else:
        if session.state == CHOOSE_QUANTITY:
            return await handle_catalog_quantity(user_id, text)
        elif session.state == ENTER_PHONE:
            return await handle_catalog_phone(user_id, text)

        return {
            "text": "👋 Привет! Используйте меню.",
            "buttons": [
                [{"type": "message", "text": "📋 Каталог", "payload": "catalog"}, {"type": "message", "text": "ℹ️ Справка", "payload": "help"}]
            ]
        }
