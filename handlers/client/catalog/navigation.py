"""Управление навигацией: стек состояний, кнопка «Назад»."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from states import (
    SELECTING_BREED,
    SELECTING_INCUBATOR,
    SELECTING_DATE,
    CHOOSE_QUANTITY,
    ENTER_PHONE,
    CONFIRM_ORDER,
)
from config.buttons import get_main_keyboard
from .utils import clear_catalog_data
from utils.messaging import safe_reply


async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки «Назад»."""
    stack = context.user_data.get("navigation_stack", [])
    if not isinstance(stack, list) or len(stack) <= 1:
        clear_catalog_data(context)
        await safe_reply(update, context, "🏠 Главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    stack.pop()
    state = stack[-1]
    context.user_data["navigation_stack"] = stack
    context.user_data.pop("confirmation_sent", None)
    return await _back_to_state(update, context, state)


async def _back_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE, state):
    """Возврат к предыдущему состоянию."""
    # Ленивые импорты — чтобы избежать циклических зависимостей
    from .breed_selection import _back_to_breed_selection
    from .incubator_selection import _back_to_incubator_selection
    from .date_selection import _back_to_date_selection
    from .quantity_input import _back_to_quantity_input
    from .phone_input import _back_to_phone_input

    if state == SELECTING_BREED:
        return await _back_to_breed_selection(update, context)
    elif state == SELECTING_INCUBATOR:
        return await _back_to_incubator_selection(update, context)
    elif state == SELECTING_DATE:
        return await _back_to_date_selection(update, context)
    elif state == CHOOSE_QUANTITY:
        return await _back_to_quantity_input(update, context)
    elif state == ENTER_PHONE:
        return await _back_to_phone_input(update, context)
    elif state == CONFIRM_ORDER:
        # ✅ Ленивый импорт — разрываем цикл
        from .confirmation import _back_to_confirmation
        return await _back_to_confirmation(update, context)

    # fallback
    return await _back_to_breed_selection(update, context)