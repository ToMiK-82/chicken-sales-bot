"""
Обработчики редактирования партии:
1. Выбор партии → 2. Что изменить → 3. Ввод → 4. Подтверждение

✅ Работает по stock_id
✅ Проверка: дата, продажи, доступное количество
✅ Только точное совпадение кнопок с эмодзи
✅ Группа: group=3 (чтобы не конфликтовать)
✅ Использует exit_to_admin_menu — только для полной отмены
✅ «Назад» возвращает на предыдущий шаг, на первом — в меню
✅ Безопасная работа с историей
✅ Все fallbacks покрыты
✅ Нет дублирования при входе
✅ Не перехватывает чужие кнопки (например, 🔧 Изменить)
"""

import logging
from datetime import date, datetime
from typing import List, Tuple

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from config.buttons import (
    BTN_EDIT_FULL,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    BTN_CONFIRM_FULL,
    BTN_EDIT_QUANTITY_FULL,
    BTN_EDIT_DATE_FULL,
    get_back_only_keyboard,
    get_confirmation_keyboard,
    get_admin_main_keyboard,
    get_quantity_date_keyboard,
)
from database.repository import db
from utils.messaging import safe_reply
from utils.admin_helpers import check_admin, exit_to_admin_menu
from html import escape

logger = logging.getLogger(__name__)

# === Состояния ===
from states import (
    EDIT_STOCK_SELECT,
    EDIT_STOCK_QUANTITY,
    EDIT_STOCK_DATE,
    CONFIRM_EDIT_STOCK,
    WAITING_FOR_ACTION,
)

# === Ключи для очистки ===
EDIT_STOCK_KEYS = [
    "edit_stock_id", "edit_quantity", "edit_date",
    "stock_list", "edit_action", "in_edit_flow",
    "edit_flow_history", "current_conversation", "HANDLED"
]

# === Fallback: полная отмена ===
async def fallback_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход в админ-панель с очисткой данных и завершением диалога."""
    await exit_to_admin_menu(
        update,
        context,
        message="❌ Редактирование отменено.",
        keys_to_clear=EDIT_STOCK_KEYS
    )
    return ConversationHandler.END


# === 1. Начало: "Редактировать партию" ===
async def handle_edit_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.effective_message.text.strip()

    logger.info(f"🔄 [handle_edit_stock] Вызов обработчика редактирования партии")
    logger.info(f"👤 Пользователь: {user_id}")
    logger.info(f"💬 Получено сообщение: '{message_text}'")
    logger.debug(f"📊 context.user_data до проверки: {context.user_data}")

    current_conv = context.user_data.get("current_conversation")
    is_handled = context.user_data.get("HANDLED")

    logger.info(f"📌 Текущее состояние: current_conversation='{current_conv}', HANDLED={is_handled}")

    if current_conv in ["view_orders", "edit_order"]:
        logger.warning(f"🚫 handle_edit_stock: блокировка вызова из контекста '{current_conv}'")
        return ConversationHandler.END

    if current_conv == "stock_view":
        from handlers.admin.stocks.view import STOCK_VIEW_KEYS
        for key in STOCK_VIEW_KEYS + ["current_conversation"]:
            if key in context.user_data:
                logger.debug(f"🧹 Очистка ключа: {key}")
                context.user_data.pop(key, None)
        context.user_data["HANDLED"] = True
        logger.info("🚪 Успешно вышли из состояния 'stock_view'")

    if not await check_admin(update, context):
        logger.warning(f"❌ Доступ запрещён: пользователь {user_id} не админ")
        return await exit_to_admin_menu(update, context, "❌ У вас нет прав.")

    logger.info(f"✅ Админ {user_id} начал редактирование партии")

    rows: List[Tuple] = await db.execute_read("""
        SELECT id, breed, incubator, date, quantity, available_quantity, price
        FROM stocks 
        WHERE status = 'active'
        ORDER BY date ASC
    """)

    if not rows:
        logger.warning("📭 Нет активных партий для редактирования")
        return await exit_to_admin_menu(update, context, "📭 Нет активных партий для редактирования.")

    logger.info(f"📋 Найдено {len(rows)} активных партий")

    stock_list = []
    message_lines = ["🔍 <b>Выберите партию для редактирования:</b>\n"]

    for i, row in enumerate(rows):
        stock_id, breed, incubator, date_str, qty, avail, price = row
        line = f"<b>{escape(breed)}</b> ({incubator}, {date_str}, {qty} шт, {price} ₽)"
        stock_list.append((stock_id, line))
        message_lines.append(f"<b>{i+1}.</b> {line}")

    message_text_out = "\n".join(message_lines) + "\n\nВведите номер партии."

    await safe_reply(
        update,
        context,
        message_text_out,
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML"
    )

    context.user_data['edit_flow_history'] = ['SELECT_STOCK']
    context.user_data['stock_list'] = stock_list
    context.user_data['current_conversation'] = 'edit_stock'
    context.user_data['HANDLED'] = True

    logger.info("🔄 Переход в состояние EDIT_STOCK_SELECT")
    logger.debug(f"📊 Полное состояние после инициализации: {context.user_data}")

    return EDIT_STOCK_SELECT


# === 2. Выбор партии по номеру ===
async def handle_edit_stock_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()
    logger.info(f"🔢 [handle_edit_stock_select] Ввод: '{text}'")

    if text == BTN_BACK_FULL:
        logger.info("🔙 Переход в главное меню (отмена редактирования)")
        await exit_to_admin_menu(
            update,
            context,
            "🚪 Вы отменили редактирование.",
            keys_to_clear=EDIT_STOCK_KEYS
        )
        return ConversationHandler.END

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите число.",
            reply_markup=get_back_only_keyboard()
        )
        return ConversationHandler.END

    try:
        index = int(text) - 1
        stock_list = context.user_data.get('stock_list', [])
        if index < 0 or index >= len(stock_list):
            raise ValueError
        stock_id, display_line = stock_list[index]
        context.user_data['edit_stock_id'] = stock_id
        logger.info(f"✅ Выбрана партия: ID={stock_id}")
    except (ValueError, IndexError):
        await safe_reply(
            update,
            context,
            "❌ Введите корректный номер.",
            reply_markup=get_back_only_keyboard()
        )
        return EDIT_STOCK_SELECT

    row = await db.execute_read("SELECT breed FROM stocks WHERE id = ? AND status = 'active'", (stock_id,))
    if not row:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    breed_safe = escape(row[0][0])
    await safe_reply(
        update,
        context,
        f"🛠️ Что изменить для «<b>{breed_safe}</b>»?",
        reply_markup=get_quantity_date_keyboard(),
        parse_mode="HTML"
    )

    context.user_data['edit_flow_history'].append('CHOOSE_ACTION')
    context.user_data['HANDLED'] = True
    return WAITING_FOR_ACTION


# === 3. Выбор: количество или дата ===
async def handle_edit_action_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()
    history = context.user_data.setdefault('edit_flow_history', [])
    logger.info(f"⚙️ [handle_edit_action_choice] Выбор действия: '{text}'")

    if text == BTN_BACK_FULL:
        if len(history) > 1:
            history.pop()
            await safe_reply(
                update,
                context,
                "🔍 <b>Выберите партию для редактирования:</b>\n\nВведите номер партии.",
                reply_markup=get_back_only_keyboard(),
                parse_mode="HTML"
            )
            context.user_data['HANDLED'] = True
            return EDIT_STOCK_SELECT
        else:
            await fallback_to_main(update, context)
            return ConversationHandler.END

    if text == BTN_EDIT_QUANTITY_FULL:
        context.user_data["edit_action"] = "quantity"
        stock_id = context.user_data['edit_stock_id']
        row = await db.execute_read("SELECT breed, quantity FROM stocks WHERE id = ?", (stock_id,))
        if not row:
            await fallback_to_main(update, context)
            return ConversationHandler.END
        breed, curr_qty = row[0]
        breed_safe = escape(breed)
        await safe_reply(
            update,
            context,
            f"🔢 Введите новое количество (было: {curr_qty}):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        history.append('ENTER_QUANTITY')
        context.user_data['HANDLED'] = True
        return EDIT_STOCK_QUANTITY

    elif text == BTN_EDIT_DATE_FULL:
        context.user_data["edit_action"] = "date"
        stock_id = context.user_data['edit_stock_id']
        row = await db.execute_read("SELECT breed, date FROM stocks WHERE id = ?", (stock_id,))
        if not row:
            await fallback_to_main(update, context)
            return ConversationHandler.END
        breed, curr_date = row[0]
        breed_safe = escape(breed)
        await safe_reply(
            update,
            context,
            f"📅 Введите новую дату (была: {curr_date}):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        history.append('ENTER_DATE')
        context.user_data['HANDLED'] = True
        return EDIT_STOCK_DATE

    await safe_reply(
        update,
        context,
        "❌ Выберите действие.",
        reply_markup=get_quantity_date_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_FOR_ACTION


# === 3.1. Ввод нового количества ===
async def handle_edit_stock_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()
    history = context.user_data.setdefault('edit_flow_history', [])

    if text == BTN_BACK_FULL:
        if len(history) > 1:
            history.pop()
            stock_id = context.user_data['edit_stock_id']
            row = await db.execute_read("SELECT breed FROM stocks WHERE id = ?", (stock_id,))
            if row:
                breed_safe = escape(row[0][0])
                await safe_reply(
                    update,
                    context,
                    f"🛠️ Что изменить для «<b>{breed_safe}</b>»?",
                    reply_markup=get_quantity_date_keyboard(),
                    parse_mode="HTML"
                )
            context.user_data['HANDLED'] = True
            return WAITING_FOR_ACTION
        else:
            await fallback_to_main(update, context)
            return ConversationHandler.END

    if not text.isdigit():
        await safe_reply(update, context, "❌ Введите число ≥ 0.")
        return EDIT_STOCK_QUANTITY

    try:
        new_qty = int(text)
        if new_qty < 0:
            raise ValueError
    except ValueError:
        await safe_reply(update, context, "❌ Введите число ≥ 0.")
        return EDIT_STOCK_QUANTITY

    stock_id = context.user_data['edit_stock_id']
    row = await db.execute_read("SELECT quantity, available_quantity FROM stocks WHERE id = ?", (stock_id,))
    if not row:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    old_qty, avail = row[0]
    sold = old_qty - avail
    if new_qty < sold:
        await safe_reply(update, context, f"❌ Нельзя установить {new_qty} шт — уже продано {sold} шт.")
        return EDIT_STOCK_QUANTITY

    context.user_data['edit_quantity'] = new_qty
    row = await db.execute_read("SELECT breed FROM stocks WHERE id = ?", (stock_id,))
    breed_safe = escape(row[0][0])
    await safe_reply(
        update,
        context,
        f"✅ Подтвердите изменение:\n\n"
        f"🐔 <b>{breed_safe}</b>\n"
        f"➡️ Количество: <b>{old_qty}</b> → <b>{new_qty}</b> шт.\n\n"
        f"Нажмите ✅ Подтвердить.",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    history.append('CONFIRM_QUANTITY')
    context.user_data['HANDLED'] = True
    return CONFIRM_EDIT_STOCK


# === 3.2. Ввод новой даты ===
async def handle_edit_stock_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()
    history = context.user_data.setdefault('edit_flow_history', [])

    if text == BTN_BACK_FULL:
        if len(history) > 1:
            history.pop()
            stock_id = context.user_data['edit_stock_id']
            row = await db.execute_read("SELECT breed FROM stocks WHERE id = ?", (stock_id,))
            if row:
                breed_safe = escape(row[0][0])
                await safe_reply(
                    update,
                    context,
                    f"🛠️ Что изменить для «<b>{breed_safe}</b>»?",
                    reply_markup=get_quantity_date_keyboard(),
                    parse_mode="HTML"
                )
            context.user_data['HANDLED'] = True
            return WAITING_FOR_ACTION
        else:
            await fallback_to_main(update, context)
            return ConversationHandler.END

    text = text.replace('.', '-').replace('/', '-')
    try:
        parsed = datetime.strptime(text, "%d-%m-%Y")
        if parsed.date() < date.today():
            await safe_reply(update, context, "❌ Дата не может быть в прошлом.")
            return EDIT_STOCK_DATE
        formatted = parsed.strftime("%d-%m-%Y")
        context.user_data['edit_date'] = formatted
    except ValueError:
        await safe_reply(update, context, "❌ Формат: ДД-ММ-ГГГГ")
        return EDIT_STOCK_DATE

    stock_id = context.user_data['edit_stock_id']
    row = await db.execute_read("SELECT breed, date FROM stocks WHERE id = ?", (stock_id,))
    if not row:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    breed, old_date = row[0]
    breed_safe = escape(breed)
    await safe_reply(
        update,
        context,
        f"✅ Подтвердите изменение:\n\n"
        f"🐔 <b>{breed_safe}</b>\n"
        f"📅 Дата: <b>{old_date}</b> → <b>{formatted}</b>\n\n"
        f"Нажмите ✅ Подтвердить.",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    history.append('CONFIRM_DATE')
    context.user_data['HANDLED'] = True
    return CONFIRM_EDIT_STOCK


# === 4. Подтверждение изменений ===
async def handle_confirm_edit_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        history = context.user_data.setdefault('edit_flow_history', [])
        if len(history) > 1:
            current = history.pop()
            prev = history[-1]

            if prev == 'ENTER_QUANTITY':
                stock_id = context.user_data['edit_stock_id']
                row = await db.execute_read("SELECT breed, quantity FROM stocks WHERE id = ?", (stock_id,))
                if row:
                    breed, curr_qty = row[0]
                    breed_safe = escape(breed)
                    await safe_reply(
                        update,
                        context,
                        f"🔢 Введите новое количество (было: {curr_qty}):",
                        reply_markup=get_back_only_keyboard(),
                        parse_mode="HTML"
                    )
                context.user_data['HANDLED'] = True
                return EDIT_STOCK_QUANTITY

            elif prev == 'ENTER_DATE':
                stock_id = context.user_data['edit_stock_id']
                row = await db.execute_read("SELECT breed, date FROM stocks WHERE id = ?", (stock_id,))
                if row:
                    breed, curr_date = row[0]
                    breed_safe = escape(breed)
                    await safe_reply(
                        update,
                        context,
                        f"📅 Введите новую дату (была: {curr_date}):",
                        reply_markup=get_back_only_keyboard(),
                        parse_mode="HTML"
                    )
                context.user_data['HANDLED'] = True
                return EDIT_STOCK_DATE

        # Если нельзя вернуться — отмена
        await fallback_to_main(update, context)
        return ConversationHandler.END

    if text != BTN_CONFIRM_FULL:
        await fallback_to_main(update, context)
        return ConversationHandler.END

    # --- Логика сохранения ---
    try:
        stock_id = context.user_data.get('edit_stock_id')
        action = context.user_data.get('edit_action')

        if not stock_id or not action:
            await exit_to_admin_menu(update, context, "❌ Ошибка: данные утеряны.")
            return ConversationHandler.END

        if action == "quantity":
            new_value = context.user_data.get('edit_quantity')
            field_name = "quantity"
            old_row = await db.execute_read("SELECT quantity FROM stocks WHERE id = ?", (stock_id,))
            old_value = old_row[0][0] if old_row else "неизвестно"
            await db.execute_write("UPDATE stocks SET quantity = ? WHERE id = ?", (new_value, stock_id))

        elif action == "date":
            new_value = context.user_data.get('edit_date')
            field_name = "date"
            old_row = await db.execute_read("SELECT date FROM stocks WHERE id = ?", (stock_id,))
            old_value = old_row[0][0] if old_row else "неизвестно"
            await db.execute_write("UPDATE stocks SET date = ? WHERE id = ?", (new_value, stock_id))

        else:
            await exit_to_admin_menu(update, context, "❌ Неизвестное действие.")
            return ConversationHandler.END

        await safe_reply(
            update,
            context,
            f"✅ Успешно обновлено:\n\n"
            f"🔧 Поле: <b>{field_name}</b>\n"
            f"🔄 Старое значение: <code>{old_value}</code>\n"
            f"🆕 Новое значение: <code>{new_value}</code>",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении партии: {e}", exc_info=True)
        await exit_to_admin_menu(update, context, "❌ Ошибка при сохранении.")

    finally:
        # Очистка данных
        for key in EDIT_STOCK_KEYS:
            context.user_data.pop(key, None)
        context.user_data["HANDLED"] = True

    return ConversationHandler.END


# === Регистрация ===
def register_edit_stock_handler(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text([BTN_EDIT_FULL]), handle_edit_stock),
        ],
        states={
            EDIT_STOCK_SELECT: [
                MessageHandler(
                    filters.Regex(r'^\d+$') | filters.Text([BTN_BACK_FULL]),
                    handle_edit_stock_select
                ),
            ],
            WAITING_FOR_ACTION: [
                MessageHandler(
                    filters.Text([BTN_EDIT_QUANTITY_FULL, BTN_EDIT_DATE_FULL, BTN_BACK_FULL]),
                    handle_edit_action_choice
                ),
            ],
            EDIT_STOCK_QUANTITY: [
                MessageHandler(
                    filters.Regex(r'^\d+$') | filters.Text([BTN_BACK_FULL]),
                    handle_edit_stock_quantity
                ),
            ],
            EDIT_STOCK_DATE: [
                MessageHandler(
                    filters.Regex(r'^\d{2}-\d{2}-\d{4}$') | filters.Text([BTN_BACK_FULL]),
                    handle_edit_stock_date
                ),
            ],
            CONFIRM_EDIT_STOCK: [
                MessageHandler(
                    filters.Text([BTN_CONFIRM_FULL, BTN_BACK_FULL]),
                    handle_confirm_edit_stock
                ),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Text([BTN_CANCEL_FULL]), fallback_to_main),
            MessageHandler(filters.COMMAND, fallback_to_main),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_edit_stock"
    )

    application.add_handler(conv_handler, group=3)
    logger.info("✅ Обработчик 'Редактировать партию' зарегистрирован (group=3)")
