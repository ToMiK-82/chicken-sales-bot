"""
🎁 Обработчик 'Акции' — показ активных промоакций.
Работает по кнопке '🎁 Акции'.
✅ Исправлен доступ к sqlite3.Row
✅ Удалён недопустимый параметр disable_web_page_preview
✅ Отправка фото по одному — стабильно и безопасно
"""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database.repository import db
from config.buttons import PROMOTIONS_BUTTON_TEXT, get_main_keyboard
from utils.messaging import safe_reply
from html import escape
import logging

logger = logging.getLogger(__name__)


async def handle_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает клиенту активные акции.
    Работает с sqlite3.Row напрямую.
    """
    if not update.effective_user or not update.effective_message:
        return

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
            return

        sent_count = 0
        failed_count = 0

        for promo in promotions:
            try:
                # ✅ Правильный доступ к sqlite3.Row
                title = escape(str(promo['title']))
                desc = escape(str(promo['description']))
                image_url = promo['image_url']
                start_date = promo['start_date']
                end_date = promo['end_date']

                # Формируем текст
                start_str = f"📅 Начало: {start_date}\n" if start_date else ""
                end_str = f"🔚 Окончание: {end_date}\n" if end_date else "🔚 Окончание: бессрочно\n"
                caption = f"🎁 <b>{title}</b>\n\n{start_str}{end_str}{desc}"

                # Отправляем фото или текст
                if image_url and str(image_url).strip():
                    try:
                        await update.effective_message.reply_photo(
                            photo=str(image_url).strip(),
                            caption=caption,
                            parse_mode="HTML",
                            # ✅ УДАЛЕНО: disable_web_page_preview=True
                            # ❌ Этот параметр НЕ поддерживается в reply_photo()
                            disable_notification=True
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.warning(f"🖼️ Не удалось отправить фото для акции '{title}': {e}")
                        try:
                            await safe_reply(update, context, caption, parse_mode="HTML", reply_markup=None)
                            sent_count += 1
                        except Exception:
                            failed_count += 1
                else:
                    try:
                        await safe_reply(update, context, caption, parse_mode="HTML", reply_markup=None)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить текст акции '{title}': {e}")
                        failed_count += 1

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке акции: {e}", exc_info=True)
                failed_count += 1

        # Итоговое сообщение
        if sent_count > 0:
            summary = "🚀 Следите за новыми предложениями!"
            if failed_count > 0:
                summary += f"\n\n⚠️ Не удалось показать {failed_count} элементов."
            await safe_reply(
                update,
                context,
                summary,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await safe_reply(
                update,
                context,
                "⚠️ Не удалось загрузить ни одну акцию.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при показе акций: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Ошибка загрузки акций. Попробуйте позже.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )


def register_promotions_handler(application):
    """Регистрирует обработчик акций."""
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Text([PROMOTIONS_BUTTON_TEXT]),
            handle_promotions
        ),
        group=1
    )
    logger.info(f"✅ Обработчик 'Акции' зарегистрирован: '{PROMOTIONS_BUTTON_TEXT}' (group=1)")


__all__ = ["handle_promotions"]
