"""
Модуль выдачи заказов с интеграцией 1С и уведомлениями.
✅ Поддержка: по ID, по телефону (по 4 цифрам), по партии
✅ Только точные кнопки — без clean_button_text
✅ Сначала БД → потом 1С и уведомления
✅ Очистка всех временных данных
✅ Унифицированный выход через exit_to_admin_menu
✅ Чистые фильтры: Text, без Regex
✅ Группа: 2 — админские диалоги
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import logging
from datetime import datetime
from html import escape

# === Внешние зависимости ===
from database.repository import db
from utils.messaging import safe_reply
from config.buttons import (
    # --- FULL-кнопки ---
    ADMIN_ISSUE_BUTTON_TEXT,
    BTN_BY_ID_FULL,
    BTN_BY_BATCH_FULL,
    BTN_BY_PHONE_FULL,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    BTN_CONFIRM_FULL,
    # --- Клавиатуры ---
    get_confirmation_keyboard,
    get_back_only_keyboard,
)
from states import (  # ✅ Централизованные состояния
    CHOOSE_ISSUE_METHOD,
    WAITING_ISSUE_ID,
    WAITING_BATCH_DATE,
    WAITING_PHONE,
    CHOOSE_ORDER_ID,
    CONFIRM_ISSUE_FINAL,
)

from utils.admin_helpers import check_admin, exit_to_admin_menu
from utils.erp import send_to_1c  # ← обновлённая версия
from utils.notifications import notify_client_issue
from utils.formatting import format_phone

logger = logging.getLogger(__name__)

# === Константа для завершения диалога ===
END = ConversationHandler.END

# === Ключи для очистки при выходе ===
ISSUE_KEYS_TO_CLEAR = ["issue_order", "issue_phone_orders", "issue_batch_orders"]

# === Клавиатура: 2×2 + Назад ===
KEYBOARD_METHOD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_BY_ID_FULL), KeyboardButton(BTN_BY_PHONE_FULL)],
        [KeyboardButton(BTN_BY_BATCH_FULL), KeyboardButton(BTN_BACK_FULL)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


# === Утилита: парсинг даты с валидацией ===
def parse_date_input(date_str: str) -> str | None:
    date_str = date_str.strip()
    formats = ["%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if 2000 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# === Утилита: форматирование даты для вывода ===
def format_date_display(date_str: str) -> str:
    """Преобразует YYYY-MM-DD → DD-MM-YYYY"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except:
        return date_str


# === Утилита: формат вывода заказа как карточки ===
def format_order_card(order: dict) -> str:
    """Форматирует заказ как красивую карточку"""
    total_price = order["quantity"] * order["price"]
    return (
        f"1. 🐔 <b>{escape(order['breed'])}</b> | 🏷️{order['id']}\n"
        f"📅 Поставка: <b>{format_date_display(order['date'])}</b>\n"
        f"🕒 Создан: <b>{format_date_display(order['created_at'])}</b>\n"
        f"📦 {order['quantity']} шт. × {order['price']} руб. = <b>{total_price}</b> руб.\n"
        f"📞 Телефон: <b>{format_phone(order['phone'])}</b>\n"
        f"──────────────────"
    )


# === Обработчики ===

async def start_issue_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        logger.warning(f"❌ Доступ запрещён: user_id={update.effective_user.id}")
        return await exit_to_admin_menu(update, context, "❌ Доступ запрещён.")
    
    logger.info(f"👤 Админ {update.effective_user.id} начал выдачу")
    await safe_reply(
        update,
        context,
        "📦 <b>Выдача заказов</b>\n\nВыберите способ:",
        reply_markup=KEYBOARD_METHOD,
        parse_mode="HTML"
    )
    return CHOOSE_ISSUE_METHOD


async def choose_issue_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    # 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: обработка "Назад" на экране выбора метода
    if text == BTN_BACK_FULL:
        logger.info(f"🔧 Админ {update.effective_user.id} нажал 'Назад' на выборе метода")
        return await exit_to_admin_menu(
            update,
            context,
            message="🚪 Выдача отменена.",
            keys_to_clear=ISSUE_KEYS_TO_CLEAR
        )

    if text == BTN_BY_ID_FULL:
        await safe_reply(
            update,
            context,
            "🔢 Введите <b>ID заказа</b>:",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_ISSUE_ID

    if text == BTN_BY_PHONE_FULL:
        await safe_reply(
            update,
            context,
            "📞 Введите <b>последние 4 цифры телефона</b>:",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_PHONE

    if text == BTN_BY_BATCH_FULL:
        try:
            result = await db.execute_read("""
                SELECT DISTINCT date, breed 
                FROM stocks 
                WHERE status = 'active' AND available_quantity > 0 
                ORDER BY date DESC
            """)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки партий: {e}")
            result = []

        if result:
            batches_list = "\n".join([f"• <code>{row[0]}</code> — {row[1]}" for row in result])
            text_msg = (
                "📅 <b>Введите дату поставки</b> для выдачи.\n\n"
                "<b>Доступные партии:</b>\n"
                f"{batches_list}\n\n"
                "Формат: <b>ГГГГ-ММ-ДД</b>"
            )
        else:
            text_msg = "⚠️ <b>Нет активных партий.</b>\nСоздайте партию через «Добавить»."

        await safe_reply(
            update,
            context,
            text_msg,
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_BATCH_DATE

    # Неизвестная команда
    await safe_reply(update, context, "❌ Выберите способ.", reply_markup=KEYBOARD_METHOD)
    return CHOOSE_ISSUE_METHOD


async def handle_issue_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await go_back(update, context)

    if not text.isdigit():
        await safe_reply(update, context, "❌ Введите ID числом.", reply_markup=get_back_only_keyboard())
        return WAITING_ISSUE_ID

    order_id = int(text)
    order = await db.fetch_one(
        "SELECT * FROM orders WHERE id = ? AND status = 'active'",
        (order_id,)
    )

    if not order:
        await safe_reply(update, context, "❌ Заказ не найден или уже выдан.")
        return WAITING_ISSUE_ID

    context.user_data["issue_order"] = order
    await _send_confirmation(update, context, order)
    return CONFIRM_ISSUE_FINAL


async def handle_issue_by_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await go_back(update, context)

    if not text.isdigit() or len(text) != 4:
        await safe_reply(update, context, "❌ Введите ровно 4 цифры.", reply_markup=get_back_only_keyboard())
        return WAITING_PHONE

    orders = await db.execute_read(
        "SELECT * FROM orders WHERE phone LIKE ? AND status = 'active' ORDER BY phone",
        (f'%{text}',)
    )

    if not orders:
        await safe_reply(update, context, f"📞 Нет активных заказов с номером, оканчивающимся на <b>{text}</b>.", parse_mode="HTML")
        return WAITING_PHONE

    if len(orders) == 1:
        context.user_data["issue_order"] = orders[0]
        await _send_confirmation(update, context, orders[0])
        return CONFIRM_ISSUE_FINAL

    msg = f"📞 Найдено <b>{len(orders)}</b> заказов с номером, оканчивающимся на <b>{text}</b>:\n\n"
    for order in orders:
        msg += f"{format_order_card(order)}\n"

    order_ids = [str(o["id"]) for o in orders[:50]]
    keyboard = [order_ids[i:i+3] for i in range(0, len(order_ids), 3)]
    keyboard.append([BTN_BACK_FULL])
    quick_select_kb = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    msg += "\n✅ Выберите ID заказа для выдачи:"
    if len(orders) > 50:
        msg += "\n\n<i>⚠️ Показаны первые 50 заказов.</i>"

    context.user_data["issue_phone_orders"] = orders
    await safe_reply(update, context, msg, reply_markup=quick_select_kb, parse_mode="HTML")
    return CHOOSE_ORDER_ID


async def handle_issue_by_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await go_back(update, context)

    parsed_date = parse_date_input(text)
    if not parsed_date:
        await safe_reply(update, context, "❌ Неверный формат даты.", reply_markup=get_back_only_keyboard())
        return WAITING_BATCH_DATE

    orders = await db.execute_read(
        "SELECT * FROM orders WHERE date = ? AND status = 'active' ORDER BY phone",
        (parsed_date,)
    )

    if not orders:
        await safe_reply(update, context, f"📅 Нет активных заказов на {text}.", parse_mode="HTML")
        return WAITING_BATCH_DATE

    if len(orders) == 1:
        context.user_data["issue_order"] = orders[0]
        await _send_confirmation(update, context, orders[0])
        return CONFIRM_ISSUE_FINAL

    msg = f"📦 Заказы на поставку <b>{format_date_display(parsed_date)}</b>:\n\n"
    for order in orders:
        msg += f"{format_order_card(order)}\n"

    order_ids = [str(o["id"]) for o in orders[:50]]
    keyboard = [order_ids[i:i+3] for i in range(0, len(order_ids), 3)]
    keyboard.append([BTN_BACK_FULL])
    quick_select_kb = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    msg += "\n✅ Выберите ID заказа для выдачи:"
    if len(orders) > 50:
        msg += "\n\n<i>⚠️ Показаны первые 50 заказов.</i>"

    context.user_data["issue_batch_orders"] = orders
    await safe_reply(update, context, msg, reply_markup=quick_select_kb, parse_mode="HTML")
    return CHOOSE_ORDER_ID


async def handle_order_id_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await go_back(update, context)

    if not text.isdigit():
        await safe_reply(update, context, "❌ Выберите заказ кнопкой.", reply_markup=get_back_only_keyboard())
        return CHOOSE_ORDER_ID

    order_id = int(text)
    all_orders = (
        context.user_data.get("issue_phone_orders", []) +
        context.user_data.get("issue_batch_orders", [])
    )

    order = next((o for o in all_orders if o["id"] == order_id), None)
    if not order or order["status"] != "active":
        await safe_reply(update, context, "❌ Заказ не найден или уже выдан.", reply_markup=get_back_only_keyboard())
        return CHOOSE_ORDER_ID

    context.user_data["issue_order"] = order
    await _send_confirmation(update, context, order)
    return CONFIRM_ISSUE_FINAL


async def _send_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, order):
    total_price = order["quantity"] * order["price"]
    msg = (
        f"⚠️ Подтвердите выдачу заказа №<b>{order['id']}</b>\n\n"
        f"🐔 <b>{escape(order['breed'])}</b>\n"
        f"📦 <b>{order['quantity']}</b> шт.\n"
        f"💰 <b>{order['price']}</b> руб./шт. → Итого: <b>{total_price}</b> руб.\n"
        f"📞 <b>{format_phone(order['phone'])}</b>\n"
        f"📅 Поставка: {format_date_display(order['date'])}\n"
        f"🏢 Инкубатор: {order['incubator'] or '—'}"
    )
    await safe_reply(update, context, msg, reply_markup=get_confirmation_keyboard(), parse_mode="HTML")


async def confirm_issue_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text != BTN_CONFIRM_FULL:
        await exit_to_admin_menu(
            update,
            context,
            "❌ Выдача отменена.",
            keys_to_clear=ISSUE_KEYS_TO_CLEAR
        )
        return END

    order = context.user_data.get("issue_order")
    if not order:
        await exit_to_admin_menu(
            update,
            context,
            "❌ Ошибка данных.",
            keys_to_clear=ISSUE_KEYS_TO_CLEAR
        )
        return END

    try:
        # === 1. Обновляем статус в БД ===
        await db.execute_write("UPDATE orders SET status = 'issued' WHERE id = ?", (order["id"],))

        # === 2. Отправляем в 1С как Реализацию товаров ===
        success, msg = await send_to_1c(
            order_id=order["id"],
            phone=order["phone"],
            breed=order["breed"],
            quantity=order["quantity"],
            price=order["price"],  # ← теперь передаём цену
            action="issue"
        )

        if not success:
            logger.error(f"❌ Ошибка отправки в 1С: {msg}")
            # Можно добавить повтор или уведомление
        else:
            logger.info(f"✅ Документ реализации для заказа #{order['id']} создан в 1С")

        # === 3. Уведомляем клиента ===
        try:
            await notify_client_issue(order)
        except Exception as e:
            logger.error(f"❌ Ошибка уведомления клиента: {e}")

        # === 4. Ответ админу ===
        await exit_to_admin_menu(
            update,
            context,
            f"✅ Заказ №<b>{order['id']}</b> выдан и отправлен в 1С.",
            keys_to_clear=ISSUE_KEYS_TO_CLEAR,
            parse_mode="HTML"
        )
        return END

    except Exception as e:
        logger.error(f"❌ Ошибка при выдаче {order['id']}: {e}", exc_info=True)
        await exit_to_admin_menu(
            update,
            context,
            "❌ Ошибка при выдаче.",
            keys_to_clear=ISSUE_KEYS_TO_CLEAR
        )
        return END


# === Возврат к выбору метода (не выход) ===
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору метода выдачи (внутри диалога)"""
    await safe_reply(
        update,
        context,
        "📦 <b>Выдача заказов</b>\n\nВыберите способ:",
        reply_markup=KEYBOARD_METHOD,
        parse_mode="HTML"
    )
    return CHOOSE_ISSUE_METHOD


# === Прямой выход при «Назад» на подтверждении ===
async def exit_on_confirm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный выход в админ-меню при нажатии 'Назад' на этапе подтверждения"""
    logger.info(f"🔧 Админ {update.effective_user.id} нажал 'Назад' на подтверждении выдачи")
    await exit_to_admin_menu(
        update,
        context,
        message="🚪 Выдача отменена.",
        keys_to_clear=ISSUE_KEYS_TO_CLEAR
    )
    return END


# === Обработка мусора — только на начальном экране ===
async def fallback_unknown_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(
        update,
        context,
        "❌ Пожалуйста, используйте кнопки ниже.",
        reply_markup=KEYBOARD_METHOD
    )
    return CHOOSE_ISSUE_METHOD


# === РЕГИСТРАЦИЯ ===
def register_admin_issue_handler(application):
    """Регистрирует обработчик выдачи заказов в приложении."""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ADMIN_ISSUE_BUTTON_TEXT]),
                start_issue_flow
            )
        ],
        states={
            CHOOSE_ISSUE_METHOD: [
                MessageHandler(
                    filters.Text([BTN_BY_ID_FULL, BTN_BY_PHONE_FULL, BTN_BY_BATCH_FULL]),
                    choose_issue_method
                ),
                # 🔥 Обработка "Назад" на этом же экране
                MessageHandler(filters.Text([BTN_BACK_FULL]), exit_on_confirm_back),
                # Мусор
                MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_unknown_input),
            ],
            WAITING_ISSUE_ID: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), go_back),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_issue_by_id)
            ],
            WAITING_BATCH_DATE: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), go_back),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_issue_by_batch)
            ],
            WAITING_PHONE: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), go_back),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_issue_by_phone)
            ],
            CHOOSE_ORDER_ID: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), go_back),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_id_selection)
            ],
            CONFIRM_ISSUE_FINAL: [
                MessageHandler(filters.Text([BTN_CONFIRM_FULL]), confirm_issue_final),
                MessageHandler(filters.Text([BTN_BACK_FULL]), exit_on_confirm_back),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Text([BTN_CANCEL_FULL]), exit_on_confirm_back),
            MessageHandler(filters.COMMAND, exit_on_confirm_back),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_issue_handler"
    )

    application.add_handler(conv_handler, group=2)
    logger.info("✅ Обработчик 'Выдача заказов' зарегистрирован (group=2)")


# === ЭКСПОРТ ===
__all__ = ["register_admin_issue_handler"]
