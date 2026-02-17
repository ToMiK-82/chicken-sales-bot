"""
Просмотр и отмена заказов клиентом.
✅ Показывает: pending + active
✅ Отмена только для pending
✅ Безопасная навигация
✅ Защита от устаревших данных после перезапуска
"""

from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from config.buttons import (
    ORDERS_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CANCEL_ORDER_FULL,
    BTN_YES_FULL,
    BTN_NO_FULL,
    get_main_keyboard,
    get_back_only_keyboard,
    get_confirm_cancel_keyboard,
    get_orders_action_keyboard,
)
from database.repository import db
from utils.messaging import safe_reply
from utils.order_utils import cancel_order_by_id
from html import escape
import logging

logger = logging.getLogger(__name__)

# === Состояния ===
ORDERS_MENU, CANCEL_ORDER, CONFIRM_CANCEL = range(3)


# === Очистка данных ===
def clear_order_cancel_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    keys_to_remove = [
        'cancel_order_id', 'cancel_breed', 'cancel_date', 'cancel_quantity',
        'cancel_price', 'cancel_created_at', 'cancel_stock_id', 'cancel_phone',
        'cancel_order_num', 'in_conversation', 'navigation_stack'
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)


# === Форматирование даты ===
def _format_date(date_str: str) -> str:
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str.split()[0] if date_str else "—"


# === Показать список заказов ===
async def show_orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 🔒 Проверка инициализации
    if not context.application.bot_data.get("INITIALIZED"):
        await safe_reply(
            update,
            context,
            "🔄 Бот запускается... Пожалуйста, подождите.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    try:
        result = await db.execute_read(
            """
            SELECT 
                id, breed, date, incubator, quantity, price, status, created_at,
                stock_id, phone
            FROM orders
            WHERE user_id = ? 
              AND status IN ('pending', 'active')
            ORDER BY created_at DESC
            """,
            (user_id,)
        )

        if not result:
            await safe_reply(
                update,
                context,
                "📭 У вас нет активных заказов.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            return ConversationHandler.END

        message_lines = ["📦 <b>Ваши заказы:</b>\n"]
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

                # Добавляем статус
                status_emoji = "🟡" if row["status"] == "pending" else "🟢"
                status_text = "ожидает подтверждения" if row["status"] == "pending" else "подтверждён"

                message_lines.append(
                    f"{status_emoji} <b>{idx}.</b> 🐔 {breed_safe}{stock_info}\n"
                    f"📅 <b>Поставка:</b> {formatted_date}\n"
                    f"🕒 <b>Создан:</b> {formatted_created}\n"
                    f"📦 <b>{qty} шт.</b> × <b>{int(price_val)} руб.</b> = <b>{int(total)} руб.</b>\n"
                    f"📞 <b>Телефон:</b> {phone_safe}\n"
                    f"ℹ️ <i>{status_text}</i>\n"
                    "──────────────────"
                )
            except Exception as e:
                logger.error(f"❌ Ошибка обработки заказа {row.get('id', 'unknown')}: {e}")
                continue

        full_text = "\n".join(message_lines) + "\n\nВыберите действие:"

        await safe_reply(
            update,
            context,
            full_text,
            reply_markup=get_orders_action_keyboard(),
            parse_mode="HTML"
        )
        return ORDERS_MENU

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке заказов: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Ошибка при загрузке заказов.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END


# === Обработчик кнопки 'Назад' ===
async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stack = context.user_data.get("navigation_stack", [])

    if len(stack) <= 1:
        clear_order_cancel_data(context)
        await safe_reply(
            update,
            context,
            "🏠 Главное меню",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    stack.pop()
    context.user_data["navigation_stack"] = stack

    if stack[-1] == ORDERS_MENU:
        return await show_orders_list(update, context)

    await safe_reply(
        update,
        context,
        "🏠 Главное меню",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# === Открытие 'Мои заказы' ===
async def handle_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔒 Блокировка, если бот ещё не инициализирован
    if not context.application.bot_data.get("INITIALIZED"):
        await safe_reply(
            update,
            context,
            "🔄 Бот запускается... Пожалуйста, подождите.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    user_id = update.effective_user.id
    logger.info(f"📱 Пользователь {user_id} открыл 'Мои заказы'")

    clear_order_cancel_data(context)
    context.user_data["navigation_stack"] = [ORDERS_MENU]
    context.user_data["in_conversation"] = True

    return await show_orders_list(update, context)


# === Начало отмены заказа ===
async def start_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клиент может отменить ТОЛЬКО `pending` заказы"""
    # 🔒 Проверка инициализации
    if not context.application.bot_data.get("INITIALIZED"):
        await safe_reply(
            update,
            context,
            "🔄 Бот был перезапущен. Состояние сброшено.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        clear_order_cancel_data(context)
        return ConversationHandler.END

    context.user_data["navigation_stack"].append(CANCEL_ORDER)

    user_id = update.effective_user.id
    result = await db.execute_read(
        """
        SELECT id, breed, date, quantity, price, created_at, stock_id, phone
        FROM orders
        WHERE user_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        """,
        (user_id,)
    )

    if not result:
        await safe_reply(
            update,
            context,
            "📭 Нет заказов, которые можно отменить.\nТолько <b>ожидающие подтверждения</b> доступны для отмены.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return await handle_back_button(update, context)

    await safe_reply(
        update,
        context,
        f"Введите номер заказа для отмены (1–{len(result)}):",
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML"
    )
    return CANCEL_ORDER


# === Ввод номера для отмены ===
async def handle_cancel_order_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return CANCEL_ORDER

    # 🔒 Проверка инициализации
    if not context.application.bot_data.get("INITIALIZED"):
        await safe_reply(
            update,
            context,
            "🔄 Бот был перезапущен. Состояние сброшено.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        clear_order_cancel_data(context)
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите номер заказа.",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return CANCEL_ORDER

    order_num = int(text)
    user_id = update.effective_user.id

    # Только pending заказы можно отменить
    result = await db.execute_read(
        """
        SELECT id, breed, date, quantity, price, created_at, stock_id, phone
        FROM orders
        WHERE user_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        """,
        (user_id,)
    )

    if not result:
        await safe_reply(
            update,
            context,
            "📭 Нет заказов для отмены.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if order_num < 1 or order_num > len(result):
        await safe_reply(
            update,
            context,
            f"❌ Номер должен быть от 1 до {len(result)}.",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        return CANCEL_ORDER

    row = result[order_num - 1]
    order_id = row["id"]
    breed = row["breed"]
    date = row["date"]
    quantity = row["quantity"]
    price = row["price"]
    created_at = row["created_at"]
    stock_id = row["stock_id"]
    phone = row["phone"]

    if not stock_id:
        await safe_reply(
            update,
            context,
            "❌ Отмена невозможна: заказ не привязан к партии.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    context.user_data.update({
        'cancel_order_id': order_id,
        'cancel_breed': breed,
        'cancel_date': date,
        'cancel_quantity': quantity,
        'cancel_price': price,
        'cancel_created_at': created_at,
        'cancel_stock_id': stock_id,
        'cancel_phone': phone,
        'cancel_order_num': order_num,
    })

    context.user_data["navigation_stack"].append(CONFIRM_CANCEL)

    formatted_date = _format_date(date)
    formatted_created = _format_date(created_at)
    total = int(quantity) * int(float(price))
    phone_safe = escape(str(phone)) if phone else "Не указан"

    confirmation_text = (
        f"<b>Отменить этот заказ?</b>\n\n"
        f"<b>1.</b> 🐔 <b>{escape(breed)}</b> | 🏷️<code>{stock_id}</code>\n"
        f"📅 <b>Поставка:</b> {formatted_date}\n"
        f"🕒 <b>Создан:</b> {formatted_created}\n"
        f"📦 <b>{quantity} шт.</b> × <b>{int(price)} руб.</b> = <b>{total} руб.</b>\n"
        f"📞 <b>Телефон:</b> {phone_safe}\n"
        "──────────────────"
    )

    await safe_reply(
        update,
        context,
        confirmation_text,
        reply_markup=get_confirm_cancel_keyboard(),
        parse_mode="HTML"
    )
    return CONFIRM_CANCEL


# === Подтверждение отмены ===
async def handle_confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return CONFIRM_CANCEL

    # 🔒 Проверка инициализации
    if not context.application.bot_data.get("INITIALIZED"):
        await safe_reply(
            update,
            context,
            "🔄 Бот был перезапущен. Состояние сброшено.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        clear_order_cancel_data(context)
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == BTN_NO_FULL:
        clear_order_cancel_data(context)
        return await show_orders_list(update, context)

    if text == BTN_YES_FULL:
        order_id = context.user_data.get('cancel_order_id')
        quantity = context.user_data.get('cancel_quantity')
        order_num = context.user_data.get('cancel_order_num')

        if not all([order_id, quantity, order_num]):
            await safe_reply(
                update,
                context,
                "❌ Ошибка: данные повреждены или устарели.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            clear_order_cancel_data(context)
            return ConversationHandler.END

        # 🔍 Проверяем, что заказ всё ещё существует и его статус — pending
        try:
            current_order = await db.execute_read(
                "SELECT status FROM orders WHERE id = ?",
                (order_id,)
            )
            if not current_order:
                await safe_reply(
                    update,
                    context,
                    "❌ Заказ не найден — возможно, он уже был удалён.",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
                clear_order_cancel_data(context)
                return ConversationHandler.END

            if current_order[0]["status"] != "pending":
                await safe_reply(
                    update,
                    context,
                    "❌ Этот заказ больше нельзя отменить — его статус изменился.",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
                clear_order_cancel_data(context)
                return ConversationHandler.END
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса заказа {order_id}: {e}")
            await safe_reply(
                update,
                context,
                "⚠️ Не удалось проверить статус заказа.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            clear_order_cancel_data(context)
            return ConversationHandler.END

        success = await cancel_order_by_id(order_id, context, update.effective_user.id)

        if success:
            await safe_reply(
                update,
                context,
                f"✅ Заказ №{order_num} отменён. {quantity} шт. возвращены в партию.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await safe_reply(
                update,
                context,
                "❌ Не удалось отменить заказ. Возможно, он уже был изменён.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )

        clear_order_cancel_data(context)
        return ConversationHandler.END

    await safe_reply(
        update,
        context,
        "📌 Пожалуйста, выберите: <b>✅ Да</b> или <b>❌ Нет</b>",
        reply_markup=get_confirm_cancel_keyboard(),
        parse_mode="HTML"
    )
    return CONFIRM_CANCEL


# === Регистрация диалога ===
def register_my_orders_handler(application):
    global my_orders_handler
    my_orders_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ORDERS_BUTTON_TEXT]),
                handle_orders
            )
        ],
        states={
            ORDERS_MENU: [
                MessageHandler(filters.Text([BTN_CANCEL_ORDER_FULL]), start_cancel_order),
                MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
            ],
            CANCEL_ORDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cancel_order_input),
            ],
            CONFIRM_CANCEL: [
                MessageHandler(filters.Text([BTN_YES_FULL, BTN_NO_FULL]), handle_confirm_cancel),
            ],
        },
        fallbacks=[
            CommandHandler("start", handle_back_button),
            CommandHandler("cancel", handle_back_button),
            MessageHandler(filters.COMMAND, handle_back_button),
            MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
        ],
        per_user=True,
        allow_reentry=True,
        name="my_orders_flow"
    )

    application.add_handler(my_orders_handler, group=1)
    logger.info(f"✅ Диалог 'Мои заказы' зарегистрирован: '{ORDERS_BUTTON_TEXT}' (group=1)")


__all__ = ["my_orders_handler"]
