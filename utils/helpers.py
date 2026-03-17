"""
Утилиты, которые могут использоваться во всём боте.
Не зависят от конкретных диалогов (например, заказа).
"""

import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config.buttons import get_main_keyboard, get_admin_main_keyboard
from utils.messaging import safe_reply
from utils.admin_helpers import is_admin  # ← убедись, что он экспортируется
import logging

logger = logging.getLogger(__name__)


# === 1. Полный выход в главное меню (админ или клиент) ===
async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ПОЛНЫЙ выход из диалога.
    Очищает весь user_data и возвращает в главное меню (с учётом роли).
    Используется при:
    - /start
    - /cancel
    - Кнопке "Выход"
    - Завершении действия
    """
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выполняет полный выход в главное меню")

    # Очищаем весь контекст
    context.user_data.clear()

    # Определяем, является ли пользователь админом
    is_admin_user = await is_admin(user_id, context.application, log=False)
    keyboard = get_admin_main_keyboard() if is_admin_user else get_main_keyboard()
    menu_name = "🔐 Админ-панель" if is_admin_user else "🏠 Главное меню"

    await safe_reply(
        update,
        context,
        f"Вы в главном меню.\n\n{menu_name}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return ConversationHandler.END


# === 2. Возврат на предыдущий шаг диалога ===
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возвращает пользователя на предыдущий шаг диалога.
    Использует navigation_stack.
    Если шагов нет — переходит в главное меню.
    """
    user_id = update.effective_user.id
    stack = context.user_data.get("navigation_stack", [])

    logger.info(f"Пользователь {user_id} нажал 'Назад'. Стек: {stack}")

    if len(stack) <= 1:
        logger.info("Стек пуст — переход в главное меню")
        return await back_to_main_menu(update, context)

    # Удаляем текущий шаг
    stack.pop()
    context.user_data["navigation_stack"] = stack

    # Сообщаем о возврате
    await safe_reply(
        update,
        context,
        "◀️ Вернулись на предыдущий шаг.",
        # Клавиатура будет установлена в обработчике состояния
    )

    return stack[-1]  # Возвращаемся к предыдущему состоянию


# === 3. Добавление шага в стек навигации ===
def push_navigation_step(context: ContextTypes.DEFAULT_TYPE, state: str):
    """
    Добавляет состояние в стек навигации.
    Вызывается при входе в новое состояние.
    """
    if "navigation_stack" not in context.user_data:
        context.user_data["navigation_stack"] = []
    context.user_data["navigation_stack"].append(state)


# === 4. Очистка стека навигации ===
def clear_navigation_stack(context: ContextTypes.DEFAULT_TYPE):
    """Очищает стек навигации."""
    if "navigation_stack" in context.user_data:
        del context.user_data["navigation_stack"]


# === 5. Форматирование даты ===
def format_date(date_str: str, input_format: str = "%Y-%m-%d", output_format: str = "%d-%m-%Y") -> str:
    """
    Форматирует строку с датой.
    Пример: "2025-04-05" → "05-04-2025"
    """
    if not date_str or not isinstance(date_str, str):
        return ""
    try:
        return datetime.strptime(date_str.strip(), input_format).strftime(output_format)
    except (ValueError, TypeError) as e:
        logger.warning(f"❌ Не удалось распарсить дату: '{date_str}' — {e}")
        return date_str


# === 6. Очистка текста (безопасность) ===
def clean_text(text: str) -> str:
    """
    Очищает текст: убирает лишние пробелы, переносы.
    """
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.strip().split())


# === 7. Проверка, является ли сообщение командой ===
def is_command(text: str) -> bool:
    """
    Проверяет, начинается ли текст с '/' (команда).
    Учитывает пробелы в начале.
    """
    return isinstance(text, str) and text.lstrip().startswith("/")


# === 8. Проверка, является ли текст числом ===
def is_valid_number(text: str) -> bool:
    """
    Проверяет, можно ли преобразовать строку в положительное целое число.
    """
    if not text or not isinstance(text, str):
        return False
    cleaned = text.strip()
    return cleaned.isdigit() and int(cleaned) > 0


# === 9. Проверка, является ли текст номером телефона (+7XXXXXXXXXX) ===
def is_valid_phone(text: str) -> bool:
    """
    Проверяет, является ли текст валидным российским номером.
    Допустимо: +7 или 8, затем 10 цифр.
    Примеры: +7 900 123-45-67, 89001234567 — валидны.
    """
    if not isinstance(text, str):
        return False
    digits = re.sub(r"\D", "", text.strip())
    return (len(digits) == 11) and (digits[0] in "78") and digits[1:].isdigit()


# === 10. Проверка, является ли текст датой в формате YYYY-MM-DD ===
def is_valid_date(text: str) -> bool:
    """
    Проверяет, соответствует ли текст дате в формате YYYY-MM-DD.
    """
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return False
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


__all__ = [
    "back_to_main_menu",
    "go_back",
    "push_navigation_step",
    "clear_navigation_stack",
    "format_date",
    "clean_text",
    "is_command",
    "is_valid_number",
    "is_valid_phone",
    "is_valid_date",
]
