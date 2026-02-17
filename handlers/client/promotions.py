"""
🎁 Обработчик 'Акции' — показ активных промоакций.
Работает по кнопке '🎁 Акции'.
✅ Удалён HANDLED_KEY — он мешает повторному вызову
"""

from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from database.repository import db
from config.buttons import (
    PROMOTIONS_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    get_main_keyboard,
    # HANDLED_KEY больше не используется
)
from utils.messaging import safe_reply
from html import escape
import logging

logger = logging.getLogger(__name__)

PROMO_VIEW = 0
promotions_handler = None


async def promotions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает активные акции."""
    # ❌ Убрано: if context.user_data.get(HANDLED_KEY): return

    try:
        promotions = await db.get_active_promotions()
        if not promotions:
            await safe_reply(
                update,
                context,
                "📭 Нет активных акций.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            return ConversationHandler.END  # можно просто END, можно None

        media = []
        text_parts = []

        for promo in promotions:
            title = escape(promo['title'])
            desc = escape(promo['description'])
            image_url = promo['image_url']

            if image_url and image_url.strip():
                caption = f"🎁 <b>{title}</b>\n\n{desc}"
                media.append(InputMediaPhoto(media=image_url, caption=caption, parse_mode="HTML"))
            else:
                text_parts.append(f"🎁 <b>{title}</b>\n\n{desc}")

        if media:
            try:
                await update.effective_message.reply_media_group(media=media, disable_notification=True)
            except Exception as e:
                logger.error(f"❌ Не удалось отправить media group: {e}")
                for part in text_parts:
                    await safe_reply(
                        update,
                        context,
                        part,
                        parse_mode="HTML",
                        reply_markup=None
                    )

        for part in text_parts:
            await safe_reply(
                update,
                context,
                part,
                parse_mode="HTML",
                reply_markup=None
            )

        await safe_reply(
            update,
            context,
            "🚀 Следите за новыми предложениями!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке акций: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Ошибка загрузки акций.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

    # ❌ Убрано: context.user_data[HANDLED_KEY] = True
    return ConversationHandler.END


async def fallback_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Безопасно завершает просмотр акций."""
    # ❌ Убрано: if context.user_data.get(HANDLED_KEY): return

    await safe_reply(
        update,
        context,
        "🚪 Просмотр акций завершён.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    # ❌ Убрано: context.user_data[HANDLED_KEY] = True
    return ConversationHandler.END


def register_promotions_handler(application):
    global promotions_handler

    promotions_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([PROMOTIONS_BUTTON_TEXT]),
                promotions_command
            )
        ],
        states={},
        fallbacks=[
            CommandHandler("start", fallback_promotions),
            CommandHandler("cancel", fallback_promotions),
            MessageHandler(filters.COMMAND, fallback_promotions),
            MessageHandler(filters.Text([BTN_BACK_FULL, BTN_CANCEL_FULL]), fallback_promotions),
        ],
        per_user=True,
        allow_reentry=True,
        name="client_promotions_conversation"
    )

    application.add_handler(promotions_handler, group=1)
    logger.info(f"✅ Обработчик 'Акции' зарегистрирован: '{PROMOTIONS_BUTTON_TEXT}' (group=1)")


__all__ = ["promotions_handler"]