"""
Утилиты, которые могут использоваться во всём боте.
Не зависят от конкретных диалогов (например, заказа).
"""

import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config.buttons import get_main_keyboard
from utils.messaging import safe_reply
import logging

logger = logging.getLogger(__name__)


# === 1. Универсальный выход в главное меню ===
async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Безопасно возвращает пользователя в главное меню.
    Очищает user_data.
    Работает как с message, так и с callback_query — через safe_reply.
    """
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выходит в главное меню")

    # Очищаем все данные сессии
    context.user_data.clear()

    # Отправляем сообщение через safe_reply (автоматически обработает тип update)
    await safe_reply(
        update,
        context,
        "🏠 Вы в главном меню.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

    return ConversationHandler.END


# === 2. Форматирование даты ===
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


# === 3. Очистка текста (безопасность) ===
def clean_text(text: str) -> str:
    """
    Очищает текст: убирает лишние пробелы, переносы.
    """
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.strip().split())


# === 4. Проверка, является ли сообщение командой ===
def is_command(text: str) -> bool:
    """
    Проверяет, начинается ли текст с '/' (команда).
    Учитывает пробелы в начале.
    """
    return isinstance(text, str) and text.lstrip().startswith("/")


# === 5. Проверка, является ли текст числом ===
def is_valid_number(text: str) -> bool:
    """
    Проверяет, можно ли преобразовать строку в положительное целое число.
    """
    if not text or not isinstance(text, str):
        return False
    cleaned = text.strip()
    return cleaned.isdigit() and int(cleaned) > 0


# === 6. Проверка, является ли текст номером телефона (+7XXXXXXXXXX) ===
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


# === 7. Проверка, является ли текст датой в формате YYYY-MM-DD ===
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
    "format_date",
    "clean_text",
    "is_command",
    "is_valid_number",
    "is_valid_phone",
    "is_valid_date",
]