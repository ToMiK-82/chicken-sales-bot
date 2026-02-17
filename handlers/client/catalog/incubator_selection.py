"""Выбор инкубатора: показ и обработка."""

from .utils import get_today_str
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config.buttons import get_incubator_keyboard, INCUBATORS, INCUBATOR_EMOJI, with_emoji, BTN_BACK_FULL
from utils.messaging import safe_reply
from .navigation import handle_back_button

# УДАЛЕНО:
# from .breed_selection import _back_to_breed_selection
# from .date_selection import _back_to_date_selection

from states import SELECTING_INCUBATOR, SELECTING_DATE, SELECTING_BREED
from config.buttons import BREEDS
from database.repository import db


async def _back_to_incubator_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные инкубаторы для выбранной породы."""
    breed_clean = context.user_data.get("selected_breed")
    if not breed_clean or breed_clean not in BREEDS:
        # ✅ Ленивый импорт — разрываем цикл
        from .breed_selection import _back_to_breed_selection
        return await _back_to_breed_selection(update, context)

    result = await db.execute_read(
        "SELECT DISTINCT incubator FROM stocks WHERE breed = ? AND available_quantity > 0 AND status = 'active' AND date >= ?",
        (breed_clean, get_today_str())
    )
    if not result:
        from config.buttons import get_main_keyboard
        await safe_reply(update, context, "📅 Нет доступных инкубаторов.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    incubators = [row[0] for row in result if row[0] in INCUBATORS]
    context.user_data["available_incubators"] = incubators

    keyboard = get_incubator_keyboard(incubators)
    await safe_reply(update, context, "🏭 Выберите инкубатор:", reply_markup=keyboard)
    return SELECTING_INCUBATOR


async def handle_incubator_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора инкубатора."""
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    selected_inc = None
    for inc in INCUBATORS:
        if with_emoji(inc, INCUBATOR_EMOJI) == text:
            selected_inc = inc
            break

    if not selected_inc:
        keyboard = get_incubator_keyboard(context.user_data.get("available_incubators", []))
        await safe_reply(update, context, "📌 Выберите инкубатор из списка.", reply_markup=keyboard)
        return SELECTING_INCUBATOR

    context.user_data["selected_incubator"] = selected_inc
    context.user_data["navigation_stack"].append(SELECTING_DATE)
    
    # ✅ Ленивый импорт — безопасно
    from .date_selection import _back_to_date_selection
    return await _back_to_date_selection(update, context)