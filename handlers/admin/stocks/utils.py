"""
Утилиты для управления партиями: выбор партии, форматирование списка.
⚠️ Возврат в меню больше НЕ здесь — используйте exit_to_admin_menu из utils/admin_helpers.py
"""

from typing import List, Tuple

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config.buttons import BTN_BACK_FULL
from database.repository import db
from utils.messaging import safe_reply
from html import escape


async def _select_stock(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: str,
    next_state: str
) -> str:
    """
    Показывает список активных партий и запрашивает выбор по номеру.
    Хранит полный список с id для корректного сопоставления.
    """
    stocks = await db.execute_read(
        """
        SELECT id, breed, incubator, date, quantity, available_quantity, price
        FROM stocks 
        WHERE quantity > 0 AND status = 'active'
        ORDER BY date ASC
        """
    )

    if not stocks:
        await safe_reply(
            update,
            context,
            "📭 Нет доступных партий.",
            reply_markup=None,  # будет установлена в хэндлере
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # Сохраняем с id
    context.user_data['stock_list'] = stocks

    # Создаём кнопки с номерами
    buttons = [str(i + 1) for i in range(len(stocks))]
    keyboard_rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    keyboard_rows.append([KeyboardButton(BTN_BACK_FULL)])

    keyboard = ReplyKeyboardMarkup(
        keyboard_rows,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    stock_list_text = _format_stocks_list(stocks)

    await safe_reply(
        update,
        context,
        f"{prompt}\n\n<pre>{escape(stock_list_text)}</pre>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    return next_state


def _format_stocks_list(stocks: List[Tuple]) -> str:
    """
    Форматирует список партий для отображения в <pre> теге.
    Ожидает кортежи: (id, breed, incubator, date, qty, avail, price)
    """
    lines = []
    for i, row in enumerate(stocks, start=1):
        # Распаковываем с id
        _, breed, incubator, date_str, qty, avail, price = row

        # Форматируем дату
        delivery_date = date_str.split()[0] if date_str and ' ' in date_str else date_str or "Не указана"

        # Цена
        try:
            float_price = float(price) if price not in (None, '') else 0.0
            display_price = int(round(float_price))
        except (TypeError, ValueError, OverflowError):
            display_price = 0

        # Экранируем текст
        breed_safe = escape(breed) if breed else "Не указана"
        incubator_safe = escape(incubator) if incubator else "Не указан"

        lines.append(f"{i}. {breed_safe} | {delivery_date} | {qty} шт. | {display_price} руб.")

    return "\n".join(lines)


# === УДАЛЕНО: _back_to_main ===
# Функция _back_to_main удалена, так как:
# - Дублирует exit_to_admin_menu
# - Не ставит HANDLED_KEY
# - Устарела
#
# ✅ Вместо неё используйте:
# from utils.admin_helpers import exit_to_admin_menu
#
# await exit_to_admin_menu(
#     update,
#     context,
#     message="🚪 Вы в главном меню",
#     keys_to_clear=["edit_action", "stock_list", "breed"]
# )