"""
Обработчик 'Справка' — информирует пользователя о функциях бота.
✅ Кликабельные команды
✅ Кликабельный номер через native tel:+...
✅ Работает на всех устройствах
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from config.buttons import (
    BTN_HELP_FULL,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    get_main_keyboard,
)
from utils.messaging import safe_reply
import logging

logger = logging.getLogger(__name__)

HELP_VIEW = 0

# 🔧 Настройки
SUPPORT_PHONE = "+7 978 7292469"
SUPPORT_PHONE_TEL = f"tel:{SUPPORT_PHONE.replace(' ', '')}"  # tel:+79787292469


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # --- 1. Основной текст ---
        message = (
            "📘 <b>Справка: как пользоваться ботом?</b>\n\n"
            "Этот бот поможет вам быстро и удобно заказать <b>суточных цыплят</b> нужной породы.\n\n"

            "📌 <b>Доступные действия:</b>\n\n"

            "🔹 <b>Главное меню</b>\n"
            "Используйте кнопки внизу для навигации:\n"
            "• 🐔 <b>Каталог</b> — выбрать и оформить заказ\n"
            "• 📅 <b>График</b> — посмотреть все поставки\n"
            "• 🎯 <b>Акции</b> — скидки и спецпредложения\n"
            "• 📦 <b>Мои заказы</b> — отслеживать и отменять\n"
            "• 📞 <b>Контакты</b> — связь с менеджером\n"
            "• ℹ️ <b>Справка</b> — эта страница\n\n"

            "📌 <b>Как сделать заказ:</b>\n"
            "1. Нажмите «🐔 Каталог»\n"
            "2. Выберите породу → инкубатор → дату → количество\n"
            "3. Введите номер телефона\n"
            "4. Подтвердите заказ\n"
            "Готово! Вы получите уведомление перед поставкой.\n\n"

            "🔔 <b>Совет:</b>\n"
            "При любом затруднении нажмите /back или /start — вы вернётесь в главное меню.\n\n"
            "Если остались вопросы — напишите менеджеру через «📞 Контакты». Мы всегда на связи! 🙏"
        )

        await safe_reply(
            update,
            context,
            message,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        # --- 2. Команды ---
        commands_message = (
            "⌨️ <b>Полезные команды (нажмите, чтобы использовать):</b>\n\n"
            "/start — перезапустить бот\n"
            "/back — вернуться в меню\n"
            "/help — показать эту справку"
        )
        await safe_reply(
            update,
            context,
            commands_message,
            parse_mode="HTML",
            disable_cooldown=True
        )

        # --- 3. Техническая информация: версия + кликабельный номер ---
        bot_version = context.application.bot_data.get("BOT_VERSION", "?.?")
        contact_message = (
            f"🔧 <b>Техническая информация:</b>\n"
            f"• Версия: <code>{bot_version}</code>\n"
            f"• Поддержка: {SUPPORT_PHONE_TEL}"
        )
        await safe_reply(
            update,
            context,
            contact_message,
            parse_mode="HTML",
            disable_web_page_preview=True,
            disable_cooldown=True
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при отображении справки: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Произошла ошибка при загрузке справки.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    return ConversationHandler.END


async def fallback_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из режима справки."""
    await safe_reply(
        update,
        context,
        "🚪 Вы вышли из просмотра справки.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


def register_help_handler(application):
    """Регистрирует обработчик 'Справка' как ConversationHandler."""
    global help_handler
    help_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([BTN_HELP_FULL]),
                help_command
            )
        ],
        states={},
        fallbacks=[
            CommandHandler("start", fallback_help),
            CommandHandler("back", fallback_help),
            CommandHandler("cancel", fallback_help),
            MessageHandler(filters.COMMAND, fallback_help),
            MessageHandler(filters.Text([BTN_BACK_FULL, BTN_CANCEL_FULL]), fallback_help),
        ],
        per_user=True,
        allow_reentry=True,
        name="help_handler"
    )
    application.add_handler(help_handler, group=1)
    logger.info(f"✅ Обработчик 'Справка' зарегистрирован: '{BTN_HELP_FULL}' (group=1)")


__all__ = ["help_handler"]