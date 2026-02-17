"""Выбор породы: показ и обработка."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# Статические константы и клавиатуры — из buttons
from config.buttons import (
    get_incubator_keyboard,
    BREEDS,
    BTN_BACK_FULL,
    INCUBATORS,
)

# Динамические функции — из utils/keyboards
from utils.keyboards import (
    get_breeds_keyboard,
    get_available_breeds_from_db,
)

from database.repository import db
from utils.messaging import safe_reply
from .utils import send_breed_info, get_today_str
from .navigation import handle_back_button
from states import SELECTING_BREED, SELECTING_INCUBATOR


async def _back_to_breed_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к выбору породы."""
    keys_to_clear = ["selected_incubator", "selected_date", "quantity"]
    for key in keys_to_clear:
        context.user_data.pop(key, None)

    context.user_data["navigation_stack"] = [SELECTING_BREED]

    # ✅ Теперь импорт из utils.keyboards — работает!
    keyboard = await get_breeds_keyboard(context.application.bot_data)

    await safe_reply(update, context, "🐔 Выберите породу:", reply_markup=keyboard)
    return SELECTING_BREED


async def handle_breed_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора породы."""
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    # Извлекаем чистое имя породы
    breed_clean = text.split(maxsplit=1)[1] if ' ' in text else text

    # Получаем актуальные породы из БД
    available_breeds = await get_available_breeds_from_db()

    # Проверяем, есть ли такая порода
    if breed_clean not in available_breeds and breed_clean not in BREEDS:
        keyboard = await get_breeds_keyboard(context.application.bot_data)
        await safe_reply(update, context, "❌ Неизвестная порода. Выберите из списка.", reply_markup=keyboard)
        return SELECTING_BREED

    context.user_data["selected_breed"] = breed_clean
    await send_breed_info(update, breed_clean, context)

    # Проверяем доступные инкубаторы
    result = await db.execute_read(
        "SELECT DISTINCT incubator FROM stocks WHERE breed = ? AND available_quantity > 0 AND status = 'active' AND date >= ?",
        (breed_clean, get_today_str())
    )
    if not result:
        from config.buttons import get_main_keyboard
        await safe_reply(update, context, "📅 Нет доступных партий этой породы.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    available_incubators = [row[0] for row in result if row[0] in INCUBATORS]
    context.user_data["available_incubators"] = available_incubators
    context.user_data["navigation_stack"] = [SELECTING_BREED, SELECTING_INCUBATOR]

    reply_markup = get_incubator_keyboard(available_incubators)
    await safe_reply(update, context, "🏢 Выберите инкубатор:", reply_markup=reply_markup)
    return SELECTING_INCUBATOR