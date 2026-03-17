# handlers/debug.py
"""
Отладочный обработчик: логирует все необработанные текстовые сообщения.
🔧 Показывает сырой текст — без обработки эмодзи
📌 Помогает понять, какие сообщения не были обработаны
✅ Максимально простой и понятный
⚠️ Включать ТОЛЬКО в development!
"""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from utils.messaging import safe_reply
from config.buttons import get_admin_main_keyboard
from html import escape
import logging

logger = logging.getLogger(__name__)

# Включать только в development!
DEBUG_MODE = True


async def debug_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Логирует ВСЕ текстовые сообщения, которые не были обработаны.
    Показывает сырой текст — как есть.
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name

    # Логируем сырой текст — без изменений
    logger.warning(
        f"🔍 [DEBUG] Необработанный текст от {username} (id={user.id}): '{text}'"
    )

    # ⚠️ Только в dev-режиме — можно включить ответ
    if DEBUG_MODE:
        try:
            reply_markup = get_admin_main_keyboard()  # ← теперь из config.buttons
            await safe_reply(
                update,
                context,
                f"🔧 <b>Получено:</b> <code>{escape(text)}</code>\n\n"
                f"Бот обрабатывает команды. Нажмите кнопку ниже.",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.debug(f"Не удалось отправить debug-сообщение: {e}")


def register_debug_handler(application):
    """Регистрирует debug-обработчик. Использовать ТОЛЬКО в dev!"""
    if DEBUG_MODE:
        # Группа 100 — самый низкий приоритет (ловит то, что не поймали другие)
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                debug_unknown_message
            ),
            group=100
        )
        logger.info("🐞 Debug-обработчик включён — все необработанные тексты логируются")
