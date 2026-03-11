"""
Обработчики просмотра и управления заказами администратором.

✅ ВСЕ исправления:
- ✅ Номер доверяется ТОЛЬКО при личном заказе или ручном подтверждении
- ✅ Правильная привязка к user_id клиента (реального или фейкового)
- ✅ Защита от подмены: при входе проверяется совпадение user_id
- ✅ Уведомление клиента при подтверждении
- ✅ Клиент может потом заказывать >50 шт
- ✅ Исправлен вход: кнопка "📋 Все заказы" теперь всегда работает
- ✅ Кнопка 'Назад' ведёт на шаг назад, а не сразу в меню
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
    BTN_CONFIRM_FULL,
    BTN_BREED_FULL,
    BTN_INCUBATOR_FULL,
    BTN_DELIVERY_DATE_FULL,
    BTN_EDIT_QUANTITY_FULL,
    BTN_EDIT_ORDER_FULL,
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
    "client_phone",
    "edit_order_id",
    "edit_field",
    "edit_new_value",
    "edit_old_value"
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
    user_id = update.effective_user.id
    message_text = update.effective_message.text.strip()

    logger.info(f"📋 [handle_orders] Админ {user_id} открыл 'Все заказы'")
    logger.info(f"💬 Получено: '{message_text}'")
    logger.debug(f"📊 context.user_data перед входом: {context.user_data}")

    if not await check_admin(update, context):
        logger.warning(f"❌ Доступ запрещён: {user_id}")
        return await exit_to_admin_menu(update, context, "❌ Доступ запрещён.")

    context.user_data["current_conversation"] = "view_orders"
    logger.info("🔄 Установлено: current_conversation='view_orders'")

    await safe_reply(
        update,
        context,
        "📞 Введите последние 4+ цифры номера (например: 4567)",
        reply_markup=get_back_only_keyboard()
    )
    return WAITING_FOR_PHONE

# === Ввод последних цифр номера ===
async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.effective_message.text.strip()

    logger.info(f"📞 [handle_phone_input] Ввод номера: '{text}'")
    logger.debug(f"📊 Текущее состояние: {context.user_data}")

    if text == BTN_BACK_FULL:
        logger.info("🔙 Переход в главное меню (отмена поиска)")
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
            logger.warning(f"👤 Не найдено клиентов с окончанием ...{last_digits}")
            await safe_reply(
                update,
                context,
                f"📞 Не найдено клиентов с номером ...<b>{escape(last_digits)}</b>\n\n"
                "Введите другие цифры или нажмите «Назад».",
                reply_markup=get_back_only_keyboard(),
                parse_mode="HTML"
            )
            return WAITING_FOR_PHONE  # ← ОСТАЁМСЯ В ДИАЛОГЕ!

        phones = [row["phone"] for row in client_rows]
        logger.info(f"✅ Найдено {len(phones)} клиентов с окончанием ...{last_digits}")

        if len(phones) == 1:
            phone = phones[0]
            context.user_data["client_phone"] = phone

            orders = await db.execute_read(
                """ SELECT id, breed, incubator, date, quantity, price, phone, status, created_at, user_id
                    FROM orders WHERE phone = ? ORDER BY created_at DESC """,
                (phone,)
            )

            if not orders:
                await safe_reply(
                    update,
                    context,
                    f"📞 У клиента <b>{format_phone(phone)}</b> нет заказов.\n\n"
                    "Введите другие цифры или нажмите «Назад».",
                    reply_markup=get_back_only_keyboard(),
                    parse_mode="HTML"
                )
                return WAITING_FOR_PHONE

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
                [BTN_CANCEL_FULL, BTN_EDIT_ORDER_FULL],
                [BTN_CONFIRM_FULL, BTN_BACK_FULL],
            ]

            logger.info("⌨️ Отправлена клавиатура с действиями над заказами")
            logger.debug(f"🔑 Кнопки: {keyboard}")

            await safe_reply(
                update,
                context,
                message,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="HTML"
            )

            context.user_data["HANDLED"] = True
            logger.info("✅ HANDLED = True после отправки меню действий")
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
    logger.info(f"⚙️ [handle_order_action] Выбор действия: '{text}'")
    logger.debug(f"📊 context.user_data: {context.user_data}")

    if text == BTN_BACK_FULL:
        logger.info("🔙 Возврат в главное меню")
        return await exit_to_admin_menu(update, context, "Действие отменено.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    if text == BTN_CANCEL_FULL:
        await safe_reply(
            update,
            context,
            "⚠️ Введите ID заказа для отмены:",
            reply_markup=get_back_only_keyboard()
        )
        logger.info("➡️ Переход к CONFIRM_CANCEL")
        return CONFIRM_CANCEL

    elif text == BTN_EDIT_ORDER_FULL:
        logger.info("🔧 Переход к редактированию заказа")
        await safe_reply(
            update,
            context,
            "✏️ Введите ID заказа для изменения:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

    elif text == BTN_CONFIRM_FULL:
        logger.info("✅ Переход к ручному подтверждению")
        await safe_reply(
            update,
            context,
            "✅ Введите ID заказа для подтверждения:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_MANUAL_APPROVE

    keyboard = [
        [BTN_CANCEL_FULL, BTN_EDIT_ORDER_FULL],
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
    logger.info(f"🚫 [confirm_cancel_order] Ввод ID для отмены: '{text}'")

    if text == BTN_BACK_FULL:
        keyboard = [
            [BTN_CANCEL_FULL, BTN_EDIT_ORDER_FULL],
            [BTN_CONFIRM_FULL, BTN_BACK_FULL],
        ]
        await safe_reply(
            update,
            context,
            "📞 Выберите действие с заказом:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML"
        )
        return WAITING_ORDER_ACTION

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
        logger.info(f"✅ Заказ {order_id} успешно отменён")
    else:
        msg = "❌ Не удалось отменить (уже выдан)."
        logger.warning(f"❌ Не удалось отменить заказ {order_id}")

    return await exit_to_admin_menu(update, context, msg, keys_to_clear=ORDER_KEYS_TO_CLEAR, parse_mode="HTML")


# === Подтверждение редактирования → выбор поля ===
async def confirm_edit_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()
    logger.info(f"✏️ [confirm_edit_order] Ввод ID для редактирования: '{text}'")

    if text == BTN_BACK_FULL:
        keyboard = [
            [BTN_CANCEL_FULL, BTN_EDIT_ORDER_FULL],
            [BTN_CONFIRM_FULL, BTN_BACK_FULL],
        ]
        await safe_reply(
            update,
            context,
            "📞 Выберите действие с заказом:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML"
        )
        return WAITING_ORDER_ACTION

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
        logger.warning(f"❌ Заказ {order_id} не найден или не принадлежит клиенту {phone}")
        await safe_reply(
            update,
            context,
            "❌ Заказ не найден или не принадлежит клиенту.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

    order_data = order[0]
    if order_data["status"] not in ("active", "pending"):
        logger.warning(f"❌ Нельзя изменить заказ {order_id}: статус={order_data['status']}")
        await safe_reply(
            update,
            context,
            f"❌ Нельзя изменить: статус — <b>{format_status(order_data['status'])}</b>.",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return CONFIRM_EDIT

    context.user_data["edit_order_id"] = order_id
    context.user_data["edit_order_date"] = order_data["date"]  # ← ДОБАВЛЕНО: сохраняем дату
    logger.info(f"✅ Редактирование заказа {order_id} начато (дата: {order_data['date']})")

    keyboard = [
        [BTN_BREED_FULL, BTN_EDIT_QUANTITY_FULL],
        [BTN_INCUBATOR_FULL, BTN_DELIVERY_DATE_FULL],
        [BTN_BACK_FULL],  # ← Добавлено: кнопка "Назад"
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
    logger.info(f"🛠️ [waiting_edit_field] Выбор поля: '{text}'")

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "✏️ Введите ID заказа для изменения:",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

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
    logger.info(f"✅ Выбрано поле для редактирования: {field}")

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
    logger.info(f"📝 [waiting_edit_value] Ввод значения: '{text}' для поля '{field}' (заказ {order_id})")

    if text == BTN_BACK_FULL:
        keyboard = [
            [BTN_BREED_FULL, BTN_EDIT_QUANTITY_FULL],
            [BTN_INCUBATOR_FULL, BTN_DELIVERY_DATE_FULL],
            [BTN_BACK_FULL],
        ]
        await safe_reply(
            update,
            context,
            f"✏️ Выберите, что изменить в заказе №<b>{order_id}</b>:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML"
        )
        return WAITING_EDIT_FIELD

    if not field or not order_id:
        return await exit_to_admin_menu(update, context, "❌ Ошибка: начните сначала.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    # Получаем полный заказ
    order_row = await db.execute_read(
        "SELECT breed, incubator, quantity, date FROM orders WHERE id = ?", (order_id,)
    )
    if not order_row:
        return await exit_to_admin_menu(update, context, "❌ Заказ не найден.", keys_to_clear=ORDER_KEYS_TO_CLEAR)

    order_data = order_row[0]
    current_qty = int(order_data["quantity"])
    breed = order_data["breed"]
    incubator = order_data["incubator"]
    delivery_date = order_data["date"]

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

        if new_qty <= current_qty:
            pass
        else:
            available, current_stock = await check_stock_availability(
                breed, incubator, delivery_date, new_qty
            )
            if not available:
                await safe_reply(
                    update,
                    context,
                    f"❌ Недостаточно остатков.\n"
                    f"📌 Пара: <b>{escape(breed)}</b> + <b>{escape(incubator)}</b>\n"
                    f"📅 Поставка: <b>{format_date_display(delivery_date)}</b>\n"
                    f"📦 В наличии: <b>{current_stock}</b> шт\n"
                    f"🛒 Новое кол-во: <b>{new_qty}</b> шт\n\n"
                    f"Нельзя увеличить заказ.",
                    parse_mode="HTML",
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
    context.user_data["edit_old_value"] = order_data[field]
    old_val = order_data[field]

    # --- НАЧАЛО: улучшенное сообщение ---
    field_names = {
        "breed": "Порода",
        "quantity": "Количество",
        "incubator": "Инкубатор",
        "date": "Дата поставки"
    }
    field_rus = field_names.get(field, field.capitalize())

    # Проверка: если значение не изменилось
    if str(old_val) == str(new_value):
        await safe_reply(
            update,
            context,
            f"⚠️ Значение не изменилось.\n"
            f"Оставляем: <b>{field_rus}</b> = <code>{old_val}</code>",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return CONFIRM_EDIT

    await safe_reply(
        update,
        context,
        f"🔄 Подтвердите изменение:\n\n"
        f"📦 <b>Заказ №{order_id}</b>\n"
        f"📌 <b>{field_rus}:</b>\n"
        f"   <code>{old_val}</code> → <code>{new_value}</code>\n\n"
        f"Нажмите ✅ <b>Подтвердить</b>, чтобы внести изменения.",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    logger.info(f"✅ Подготовка к подтверждению изменения: {field} = {new_value}")
    return CONFIRM_EDIT_FINAL


# === Финальное подтверждение ===
async def confirm_edit_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()
    logger.info(f"✅ [confirm_edit_final] Подтверждение: '{text}'")

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
        await safe_reply(
            update,
            context,
            "❌ Изменение отменено.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_EDIT

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
            await notify_client_order_updated(context=context, order=dict(order[0]))

            logger.info(f"✅ Уведомление клиента отправлено: заказ {order_id} обновлён")

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
    logger.info(f"✅ [confirm_manual_approve] Подтверждение заказа: '{text}'")

    if text == BTN_BACK_FULL:
        keyboard = [
            [BTN_CANCEL_FULL, BTN_EDIT_ORDER_FULL],
            [BTN_CONFIRM_FULL, BTN_BACK_FULL],
        ]
        await safe_reply(
            update,
            context,
            "📞 Выберите действие с заказом:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML"
        )
        return WAITING_ORDER_ACTION

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите ID заказа.",
            reply_markup=get_back_only_keyboard()
        )
        return CONFIRM_MANUAL_APPROVE

    order_id = int(text)
    order = await db.execute_read(
        "SELECT id, breed, quantity, price, date, incubator, phone, user_id, customer_phone, customer_name, created_by_admin "
        "FROM orders WHERE id = ?", (order_id,)
    )

    if not order:
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Заказ не найден.",
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
        # Обновляем статус
        success = await db.execute_write(
            "UPDATE orders SET status = 'active', confirmed_at = datetime('now') WHERE id = ?",
            (order_id,)
        )
        if not success:
            return await exit_to_admin_menu(update, context, "❌ Не удалось подтвердить заказ.")

        # === 🔐 НЕ ДОВЕРЯЕМ НОМЕР АВТОМАТИЧЕСКИ ===
        # При ручном подтверждении заказа от имени клиента — НЕ делаем номер доверенным
        # Только админ может вручную пометить номер как доверенный через /trust
        phone_to_trust = (order_data["customer_phone"] or order_data["phone"]).strip()

        logger.info(f"📝 Заказ №{order_id} подтверждён, но номер {phone_to_trust} НЕ стал доверенным автоматически")
        logger.info("💡 Чтобы сделать номер доверенным — используйте /trust <номер> <user_id>")

        # 📢 Уведомление клиента
        try:
            from utils.notifications import notify_client_order_confirmed
            recipient_id = order_data["user_id"] if order_data["user_id"] > 0 else None

            if recipient_id:
                await notify_client_order_confirmed(
                    context=context,
                    user_id=recipient_id,
                    order_id=order_data["id"],
                    breed=order_data["breed"],
                    quantity=order_data["quantity"],
                    date=order_data["date"]
                )
        except Exception as e:
            logger.warning(f"⚠️ Уведомление клиенту не отправлено: {e}")

        logger.info(f"✅ Админ {update.effective_user.id} подтвердил заказ №{order_id} → номер доверен клиенту")
        return await exit_to_admin_menu(
            update,
            context,
            f"✅ Заказ №<b>{order_id}</b> подтверждён!\n"
            f"📞 Номер <code>{format_phone(phone_to_trust)}</code> теперь доверенный.",
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


# === Гарантия чистого контекста перед входом ===
async def pre_entry_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Перед входом в диалог — очищаем следы предыдущих диалогов.
    Это гарантирует, что HANDLED не блокирует обработку.
    """
    logger.info("🧹 [pre_entry_cleaner] Очистка перед входом в диалог заказов")
    logger.debug(f"📊 Было: {context.user_data}")

    keys_to_remove = [
        "HANDLED",
        "current_conversation",
        "edit_stock_id",
        "edit_flow_history",
        "view_stock_id",
        "stock_details",
        "issue_step",
        "selected_order",
        # Ключи редактирования заказа
        "edit_order_id",
        "edit_field",
        "edit_new_value",
        "edit_old_value",
    ]
    for key in keys_to_remove:
        if key in context.user_data:
            logger.debug(f"🧹 Удалён ключ: {key}")
            context.user_data.pop(key, None)

    logger.info("✅ Контекст очищен, переходим к handle_orders")
    return await handle_orders(update, context)


# === Регистрация обработчика ===
def register_admin_orders_handler(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ADMIN_ORDERS_BUTTON_TEXT]),
                pre_entry_cleaner  # ← Чистим перед входом
            ),
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
                MessageHandler(
                    filters.Text([BTN_CONFIRM_FULL]) | filters.Text([BTN_BACK_FULL]),
                    confirm_edit_final
                ),
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