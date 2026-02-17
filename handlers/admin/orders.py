"""
Обработчики просмотра и управления заказами администратором.
✅ ВСЕ исправления:
- ✅ trust_phone() при ручном подтверждении
- ✅ Проверка user_id из заказа
- ✅ Уведомление клиента
- ✅ Клиент может потом заказывать >50 шт
"""

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config.buttons import (
    SEPARATOR,
    # --- FULL-кнопки ---
    ADMIN_ORDERS_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    BTN_EDIT_FULL,
    BTN_CONFIRM_FULL,
    BTN_BREED_FULL,
    BTN_INCUBATOR_FULL,
    BTN_DELIVERY_DATE_FULL,
    BTN_EDIT_QUANTITY_FULL,
    # --- Клавиатуры ---
    get_back_only_keyboard,
    get_confirmation_keyboard,
)
from utils.order_utils import cancel_order_by_id, check_stock_availability
from utils.admin_helpers import check_admin, exit_to_admin_menu
from utils.messaging import safe_reply
from utils.formatting import format_phone, format_date_display, parse_date_input
from database.repository import db
from html import escape
import logging

logger = logging.getLogger(__name__)

# === Ключи для очистки при выходе ===
ORDER_KEYS_TO_CLEAR = [
    "client_phone", "edit_order_id", "edit_field", "edit_new_value", "edit_old_value"
]

# === Состояния ===
WAITING_FOR_PHONE = "WAITING_FOR_PHONE"
WAITING_ORDER_ACTION = "WAITING_ORDER_ACTION"
CONFIRM_CANCEL = "CONFIRM_CANCEL"
CONFIRM_EDIT = "CONFIRM_EDIT"
WAITING_EDIT_FIELD = "WAITING_EDIT_FIELD"
WAITING_EDIT_VALUE = "WAITING_EDIT_VALUE"
CONFIRM_EDIT_FINAL = "CONFIRM_EDIT_FINAL"
CONFIRM_MANUAL_APPROVE = "CONFIRM_MANUAL_APPROVE"


# === Вспомогательные функции ===
def format_status(status: str) -> str:
    return {
        "active": "Активный",
        "cancelled": "Отменён",
        "issued": "Выдан",
        "pending": "Ожидает подтверждения",
    }.get(status, status.title())


# === Вход: "📋 Все заказы" ===
async def handle_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        logger.warning(f"❌ Доступ запрещён: {update.effective_user.id}")
        return await exit_to_admin_menu(update, context, "❌ Доступ запрещён.")
    
    logger.info(f"👤 Админ {update.effective_user.id} открыл 'Все заказы'")
    await safe_reply(
        update,
        context,
        "📞 Введите последние 4+ цифры номера (например: 4567)",
        reply_markup=get_back_only_keyboard()
    )
    return WAITING_FOR_PHONE


# === Ввод последних цифр номера ===
async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(update, context, "Поиск отменён.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    if not text.isdigit() or len(text) < 4:
        await safe_reply(
            update,
            context,
            "❌ Введите минимум 4 цифры.",
            reply_markup=get_back_only_keyboard()
        )
        return WAITING_FOR_PHONE

    last_digits = text[-10:]

    try:
        client_rows = await db.execute_read(
            "SELECT DISTINCT phone FROM orders WHERE phone LIKE ?",
            (f"%{last_digits}",)
        )

        if not client_rows:
            return await exit_to_admin_menu(
                update,
                context,
                f"📞 Не найдено клиентов с номером ...<b>{escape(last_digits)}</b>",
                keys_to_clear=ORDER_KEYS_TO_CLEAR,
                parse_mode="HTML"
            )

        phones = [row["phone"] for row in client_rows]

        if len(phones) == 1:
            phone = phones[0]
            context.user_data["client_phone"] = phone

            orders = await db.execute_read(
                """
                SELECT id, breed, incubator, date, quantity, price, phone, status, created_at, user_id
                FROM orders WHERE phone = ? ORDER BY created_at DESC
                """,
                (phone,)
            )

            if not orders:
                return await exit_to_admin_menu(
                    update,
                    context,
                    f"📞 У клиента <b>{format_phone(phone)}</b> нет заказов.",
                    keys_to_clear=ORDER_KEYS_TO_CLEAR,
                    parse_mode="HTML"
                )

            message = f"📦 <b>Заказы клиента {format_phone(phone)}</b>:\n\n"
            for order in orders:
                try:
                    qty = int(order["quantity"])
                    price = int(float(order["price"]))
                    total = qty * price
                except (TypeError, ValueError):
                    total = "—"

                message += (
                    f"🔢 <b>Номер:</b> {order['id']}\n"
                    f"🐔 <b>Порода:</b> {escape(order['breed'])}\n"
                    f"🏢 <b>Инкубатор:</b> {escape(order['incubator']) if order['incubator'] else '—'}\n"
                    f"📅 <b>Поставка:</b> {format_date_display(order['date'])}\n"
                    f"📦 <b>Кол-во:</b> {qty} шт.\n"
                    f"💰 <b>Цена:</b> {price} руб.\n"
                    f"🧮 <b>Сумма:</b> {total} руб.\n"
                    f"📞 <b>Телефон:</b> {format_phone(phone)}\n"
                    f"🕒 <b>Создан:</b> {format_date_display(order['created_at'])}\n"
                    f"📌 <b>Статус:</b> {format_status(order['status'])}\n"
                    f"{SEPARATOR}"
                )

            keyboard = [
                [BTN_CANCEL_FULL, BTN_EDIT_FULL],
                [BTN_CONFIRM_FULL, BTN_BACK_FULL],
            ]
            await safe_reply(
                update,
                context,
                message,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="HTML"
            )
            return WAITING_ORDER_ACTION

        else:
            clients_list = "\n".join(f"📞 ...{p[-10:]}" for p in phones[:10])
            if len(phones) > 10:
                clients_list += "\n...и ещё несколько"

            await safe_reply(
                update,
                context,
                f"✅ Найдено <b>{len(phones)}</b> клиентов с окончанием ...<b>{escape(last_digits)}</b>:\n\n"
                f"<pre>{escape(clients_list)}</pre>\n\n"
                "Введите больше цифр для уточнения.",
                reply_markup=get_back_only_keyboard(),
                parse_mode="HTML"
            )
            return WAITING_FOR_PHONE

    except Exception as e:
        logger.error(f"❌ Ошибка поиска заказов: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "⚠️ Ошибка при поиске.", keys_to_clear=ORDER_KEYS_TO_CLEAR)


# === Выбор действия ===
async def handle_order_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(update, context, "Действие отменено.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    if text == BTN_CANCEL_FULL:
        await safe_reply(
            update,
            context,
            "⚠️ Введите ID заказа для отмены:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_CANCEL

    if text == BTN_EDIT_FULL:
        await safe_reply(
            update,
            context,
            "✏️ Введите ID заказа для изменения:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

    if text == BTN_CONFIRM_FULL:
        await safe_reply(
            update,
            context,
            "✅ Введите ID заказа для подтверждения:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_MANUAL_APPROVE

    keyboard = [
        [BTN_CANCEL_FULL, BTN_EDIT_FULL],
        [BTN_CONFIRM_FULL, BTN_BACK_FULL],
    ]
    await safe_reply(
        update,
        context,
        "❌ Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="HTML"
    )
    return WAITING_ORDER_ACTION


# === Подтверждение отмены ===
async def confirm_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_order_action(update, context)

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите ID заказа.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_CANCEL

    order_id = int(text)
    success = await cancel_order_by_id(order_id, context=context, admin_initiated=True)

    if success:
        msg = f"🚫 Заказ №<b>{order_id}</b> отменён."
    else:
        msg = "❌ Не удалось отменить (уже выдан)."

    return await exit_to_admin_menu(update, context, msg, keys_to_clear=ORDER_KEYS_TO_CLEAR, parse_mode="HTML")


# === Подтверждение редактирования → выбор поля ===
async def confirm_edit_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_order_action(update, context)

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите ID заказа.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

    order_id = int(text)
    phone = context.user_data.get("client_phone")

    order = await db.execute_read(
        "SELECT id, breed, incubator, date, quantity, status FROM orders WHERE id = ? AND phone = ?",
        (order_id, phone)
    )

    if not order:
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Заказ не найден или не принадлежит клиенту.",
            keys_to_clear=ORDER_KEYS_TO_CLEAR
        )

    order_data = order[0]
    if order_data["status"] != "active":
        return await exit_to_admin_menu(
            update,
            context,
            f"❌ Нельзя изменить: статус — <b>{format_status(order_data['status'])}</b>.",
            keys_to_clear=ORDER_KEYS_TO_CLEAR,
            parse_mode="HTML"
        )

    context.user_data["edit_order_id"] = order_id

    keyboard = [
        [BTN_BREED_FULL, BTN_EDIT_QUANTITY_FULL],
        [BTN_INCUBATOR_FULL, BTN_DELIVERY_DATE_FULL],
    ]
    await safe_reply(
        update,
        context,
        f"✏️ Выберите, что изменить в заказе №<b>{order_id}</b>:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="HTML"
    )
    return WAITING_EDIT_FIELD


# === Выбор поля ===
async def waiting_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_order_action(update, context)

    field_map = {
        BTN_BREED_FULL: ("breed", "например: Бройлер"),
        BTN_EDIT_QUANTITY_FULL: ("quantity", "целое число, например: 50"),
        BTN_INCUBATOR_FULL: ("incubator", "название инкубатора"),
        BTN_DELIVERY_DATE_FULL: ("date", "в формате ДД-ММ-ГГГГ")
    }

    if text not in field_map:
        await safe_reply(update, context, "❌ Выберите поле из списка.")
        return WAITING_EDIT_FIELD

    field, hint = field_map[text]
    context.user_data["edit_field"] = field

    await safe_reply(
        update,
        context,
        f"🖊 Введите новое значение для <b>{text.split()[-1]}</b>.\n\n💡 Подсказка: {hint}",
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_EDIT_VALUE


# === Ввод нового значения ===
async def waiting_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()
    field = context.user_data.get("edit_field")
    order_id = context.user_data.get("edit_order_id")

    if text == BTN_BACK_FULL:
        return await handle_order_action(update, context)

    if not field or not order_id:
        return await exit_to_admin_menu(update, context, "❌ Ошибка: начните сначала.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    order = await db.execute_read("SELECT breed, incubator, quantity FROM orders WHERE id = ?", (order_id,))
    if not order:
        return await exit_to_admin_menu(update, context, "❌ Заказ не найден.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    current_order = order[0]
    new_value = text.strip()

    if field == "breed":
        if not new_value or len(new_value.strip()) < 2:
            await safe_reply(update, context, "❌ Введите корректную породу.")
            return WAITING_EDIT_VALUE
        new_value = new_value.strip()

    elif field == "incubator":
        if not new_value or len(new_value.strip()) < 2:
            await safe_reply(update, context, "❌ Введите корректное название.")
            return WAITING_EDIT_VALUE
        new_value = new_value.strip()

    elif field == "quantity":
        if not new_value.isdigit() or (new_qty := int(new_value)) <= 0:
            await safe_reply(update, context, "❌ Введите положительное число.")
            return WAITING_EDIT_VALUE

        available, current_stock = await check_stock_availability(
            current_order["breed"], current_order["incubator"], new_qty
        )
        if not available:
            await safe_reply(
                update,
                context,
                f"❌ Недостаточно остатков.\n"
                f"📦 В наличии: {current_stock} шт.\n"
                f"🛒 Новое кол-во: {new_qty} шт.\n\n"
                f"Нельзя увеличить заказ.",
                reply_markup=get_back_only_keyboard()
            )
            return WAITING_EDIT_VALUE
        new_value = new_qty

    elif field == "date":
        parsed = parse_date_input(new_value)
        if not parsed:
            await safe_reply(update, context, "❌ Введите дату в формате ДД-ММ-ГГГГ.")
            return WAITING_EDIT_VALUE
        new_value = parsed

    context.user_data["edit_new_value"] = new_value
    context.user_data["edit_old_value"] = current_order[field]

    old_val = current_order[field]
    await safe_reply(
        update,
        context,
        f"🔄 Подтвердите изменение:\n\n"
        f"🔢 Заказ: <b>#{order_id}</b>\n"
        f"🔧 Поле: <b>{field.capitalize()}</b>\n"
        f"➡️ <code>{old_val}</code> → <code>{new_value}</code>\n\n"
        f"Нажмите ✅ <b>Подтвердить</b>, чтобы внести изменения.",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    return CONFIRM_EDIT_FINAL


# === Финальное подтверждение ===
async def confirm_edit_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        field = context.user_data.get("edit_field")
        hint_map = {
            "breed": "например: Бройлер",
            "quantity": "целое число, например: 50",
            "incubator": "название инкубатора",
            "date": "в формате ДД-ММ-ГГГГ"
        }
        hint = hint_map.get(field, "")

        await safe_reply(
            update,
            context,
            f"🖊 Введите новое значение для <b>{field.capitalize()}</b>.\n\n💡 Подсказка: {hint}",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_EDIT_VALUE

    if text != BTN_CONFIRM_FULL:
        return await exit_to_admin_menu(update, context, "❌ Изменение отменено.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    field = context.user_data.get("edit_field")
    new_value = context.user_data.get("edit_new_value")
    order_id = context.user_data.get("edit_order_id")

    if not all([field, new_value, order_id]):
        return await exit_to_admin_menu(update, context, "❌ Ошибка данных.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    try:
        await db.execute_write(f"UPDATE orders SET {field} = ? WHERE id = ?", (new_value, order_id))

        order = await db.execute_read("SELECT * FROM orders WHERE id = ?", (order_id,))
        if order:
            from utils.notifications import notify_client_order_updated
            await notify_client_order_updated(dict(order[0]))

        return await exit_to_admin_menu(
            update,
            context,
            f"✅ Заказ №<b>{order_id}</b> обновлён.\n"
            f"<b>{field.capitalize()}</b>: → <code>{escape(str(new_value))}</code>",
            keys_to_clear=ORDER_KEYS_TO_CLEAR,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении заказа {order_id}: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Ошибка при сохранении.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

# === Ручное подтверждение заказа ===
async def confirm_manual_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_order_action(update, context)

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите ID заказа.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_MANUAL_APPROVE

    order_id = int(text)
    phone = context.user_data.get("client_phone")

    # 🔍 Получаем заказ с user_id
    order = await db.execute_read(
        "SELECT id, breed, quantity, price, date, incubator, phone, user_id FROM orders WHERE id = ? AND phone = ?",
        (order_id, phone)
    )

    if not order:
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Заказ не найден или не принадлежит клиенту.",
            keys_to_clear=ORDER_KEYS_TO_CLEAR
        )

    order_data = order[0]

    current_status_row = await db.execute_read("SELECT status FROM orders WHERE id = ?", (order_id,))
    if not current_status_row:
        return await exit_to_admin_menu(update, context, "❌ Заказ не существует.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    current_status = current_status_row[0]["status"]
    if current_status != "pending":
        return await exit_to_admin_menu(
            update,
            context,
            f"❌ Нельзя подтвердить: статус — <b>{format_status(current_status)}</b>.",
            keys_to_clear=ORDER_KEYS_TO_CLEAR,
            parse_mode="HTML"
        )

    try:
        # ✅ Обновляем статус
        success = await db.execute_write(
            "UPDATE orders SET status = 'active', confirmed_at = datetime('now') WHERE id = ?",
            (order_id,)
        )

        if not success:
            return await exit_to_admin_menu(update, context, "❌ Не удалось подтвердить заказ.")

        # ✅ Доверяем номер
        await db.trust_phone(order_data["phone"], order_data["user_id"])

        # ✅ Уведомляем клиента
        try:
            from utils.notifications import notify_client_order_confirmed
            await notify_client_order_confirmed(
                context=context,           # правильный контекст
                user_id=order_data["user_id"],
                order_id=order_data["id"],
                breed=order_data["breed"],
                quantity=order_data["quantity"],
                date=order_data["date"]
            )
        except Exception as e:
            logger.warning(f"⚠️ Уведомление клиенту не отправлено: {e}")

        logger.info(f"✅ Админ {update.effective_user.id} подтвердил заказ №{order_id} → номер доверен")

        return await exit_to_admin_menu(
            update,
            context,
            f"✅ Заказ №<b>{order_id}</b> и номер подтверждён!",
            keys_to_clear=ORDER_KEYS_TO_CLEAR,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при ручном подтверждении заказа {order_id}: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Не удалось подтвердить заказ.")

# === Fallback: "Назад" → возврат в меню ===
async def fallback_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚪 fallback_back_to_main: возврат в меню")
    return await exit_to_admin_menu(update, context, "🚪 Возвращаемся в меню.", keys_to_clear=ORDER_KEYS_TO_CLEAR)


# === Регистрация обработчика ===
def register_admin_orders_handler(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Text([ADMIN_ORDERS_BUTTON_TEXT]),
                handle_orders
            )
        ],
        states={
            WAITING_FOR_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_input)
            ],
            WAITING_ORDER_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_action)
            ],
            CONFIRM_CANCEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_cancel_order)
            ],
            CONFIRM_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_edit_order)
            ],
            WAITING_EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_edit_field)
            ],
            WAITING_EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_edit_value)
            ],
            CONFIRM_EDIT_FINAL: [
                MessageHandler(filters.Text([BTN_CONFIRM_FULL]), confirm_edit_final),
            ],
            CONFIRM_MANUAL_APPROVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_manual_approve)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Text([BTN_BACK_FULL]), fallback_back_to_main),
            MessageHandler(filters.COMMAND, fallback_back_to_main),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_view_orders"
    )

    application.add_handler(conv_handler, group=2)
    logger.info("✅ Обработчик 'Все заказы' зарегистрирован (group=2)")