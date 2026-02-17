"""Выбор даты поставки: форматирование, клавиатура 3 в строке."""

from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from utils.messaging import safe_reply
from config.buttons import BTN_BACK_FULL
from .navigation import handle_back_button

# === ИМПОРТЫ НАВЕРХ ===
from states import SELECTING_DATE, CHOOSE_QUANTITY, SELECTING_INCUBATOR
from database.repository import db
from .incubator_selection import _back_to_incubator_selection


def _build_date_keyboard(dates):
    """Создаёт клавиатуру с датами (3 в строке)."""
    keyboard = []
    row = []
    for date_str, _, _ in dates:
        formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m")
        row.append(KeyboardButton(formatted))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([BTN_BACK_FULL])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


async def _back_to_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные даты."""
    breed_clean = context.user_data.get("selected_breed")
    incubator = context.user_data.get("selected_incubator")
    if not breed_clean or not incubator:
        return await _back_to_incubator_selection(update, context)

    result = await db.execute_read(
        "SELECT date, available_quantity, price FROM stocks WHERE breed = ? AND incubator = ? AND available_quantity > 0 AND status = 'active' ORDER BY date ASC",
        (breed_clean, incubator)
    )
    if not result:
        from config.buttons import get_main_keyboard
        await safe_reply(update, context, "❌ Нет доступных партий.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    today = datetime.now().date()
    filtered = []
    for date_str, qty, price in result:
        try:
            stock_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if stock_date >= today:
                filtered.append((date_str, qty, price))
        except ValueError:
            continue

    if not filtered:
        from config.buttons import get_main_keyboard
        await safe_reply(update, context, "📅 Нет доступных дат.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    context.user_data["available_dates"] = filtered
    keyboard = _build_date_keyboard(filtered)
    await safe_reply(update, context, "📅 Выберите дату поставки:", reply_markup=keyboard)
    return SELECTING_DATE


async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора даты."""
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    available_dates = context.user_data.get("available_dates", [])
    selected_date = None
    for date_str, qty, price in available_dates:
        formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m")
        if formatted == text:
            selected_date = date_str
            context.user_data.update({
                "selected_date": selected_date,
                "available_quantity": qty,
                "selected_price": price
            })
            break

    if not selected_date:
        keyboard = _build_date_keyboard(available_dates)
        await safe_reply(update, context, "📌 Выберите дату из списка.", reply_markup=keyboard)
        return SELECTING_DATE

    # ✅ Переход к вводу количества
    context.user_data["navigation_stack"].append(CHOOSE_QUANTITY)
    
    # ✅ ЛЕНИВЫЙ ИМПОРТ — чтобы избежать цикла
    from .quantity_input import _back_to_quantity_input
    return await _back_to_quantity_input(update, context)