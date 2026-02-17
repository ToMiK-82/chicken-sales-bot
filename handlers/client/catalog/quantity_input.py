"""Ввод количества: проверка на доступность."""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.messaging import safe_reply
from config.buttons import get_back_only_keyboard, BTN_BACK_FULL
from .navigation import handle_back_button

# === ИМПОРТЫ НАВЕРХ ===
from states import CHOOSE_QUANTITY, ENTER_PHONE, SELECTING_DATE
from database.repository import db

# ✅ УДАЛЁН: from .phone_input import _back_to_phone_input


async def _back_to_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос количества с отображением доступного."""
    breed_clean = context.user_data.get("selected_breed")
    incubator = context.user_data.get("selected_incubator")
    date = context.user_data.get("selected_date")
    if not all([breed_clean, incubator, date]):
        # ✅ Оставляем — это безопасно, так как _back_to_date_selection уже был загружен ранее
        from .date_selection import _back_to_date_selection
        return await _back_to_date_selection(update, context)

    result = await db.execute_read(
        "SELECT available_quantity, price FROM stocks WHERE breed = ? AND incubator = ? AND date = ? AND status = 'active' AND available_quantity > 0",
        (breed_clean, incubator, date)
    )
    if not result:
        from config.buttons import get_main_keyboard
        await safe_reply(update, context, "❌ Партия недоступна.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    avail_qty, price = result[0]
    context.user_data.update({"available_quantity": avail_qty, "selected_price": price})

    try:
        delivery_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        delivery_date = date

    await safe_reply(update, context,
                     f"📅 <b>Поставка:</b> {delivery_date}\n"
                     f"📦 <b>Доступно:</b> {avail_qty} шт.\n"
                     f"💰 <b>Цена:</b> {int(price)} руб.\n\n"
                     f"Введите количество:",
                     reply_markup=get_back_only_keyboard(), parse_mode="HTML")
    return CHOOSE_QUANTITY


async def handle_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода количества."""
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    if not text.isdigit():
        await safe_reply(update, context, "❌ Введите число.", reply_markup=get_back_only_keyboard())
        return CHOOSE_QUANTITY

    qty = int(text)
    avail = context.user_data.get("available_quantity", 0)
    if not (1 <= qty <= avail):
        await safe_reply(update, context, f"❌ Допустимо от 1 до {avail}.", reply_markup=get_back_only_keyboard())
        return CHOOSE_QUANTITY

    context.user_data["selected_quantity"] = qty
    context.user_data["navigation_stack"].append(ENTER_PHONE)

    # ✅ ЛЕНИВЫЙ ИМПОРТ — разрываем цикл
    from .phone_input import _back_to_phone_input
    return await _back_to_phone_input(update, context)