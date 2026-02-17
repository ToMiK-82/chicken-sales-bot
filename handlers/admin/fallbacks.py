"""
🛡️ Обработчики отмены и возврата для админских диалогов.
✅ Не зависят от других модулей
✅ Используют только safe_reply и клавиатуры
✅ Проверяют права админа
✅ Возвращаются в главное **клиентское** меню при выходе
✅ Обрабатывают как кнопки, так и команды
✅ Поддерживают выход через /cancel, /start и кнопки меню
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.messaging import safe_reply
from config.buttons import (
    get_admin_main_keyboard,
    get_action_keyboard,
    get_confirmation_keyboard,
    get_main_keyboard,
    # Кнопки меню
    SCHEDULE_BUTTON_TEXT,
    CATALOG_BUTTON_TEXT,
    ORDERS_BUTTON_TEXT,
    PROMOTIONS_BUTTON_TEXT,
    CONTACTS_BUTTON_TEXT,
    HELP_BUTTON_TEXT,
)
from utils.admin_helpers import check_admin
from utils.helpers import back_to_main_menu
from html import escape
import logging

from states import (
    WAITING_FOR_ACTION,
    EDIT_STOCK_SELECT,
    EDIT_STOCK_QUANTITY,
    CANCEL_STOCK_SELECT,
)

logger = logging.getLogger(__name__)

__all__ = [
    "fallback_unknown",
    "fallback_back_to_main",
    "fallback_back_to_actions",
    "fallback_edit_back_to_select",
    "fallback_edit_back_to_quantity",
    "fallback_cancel_back_to_select",
]


async def fallback_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ловит любые неожидаемые сообщения.
    Если это кнопка меню — выходит в главное меню.
    Если команда — обрабатывает.
    Иначе — показывает подсказку.
    """
    if not await check_admin(update, context):
        logger.warning(f"🚫 fallback_unknown: не-админ ID={update.effective_user.id} ввёл: {repr(update.message.text)}")
        await safe_reply(
            update,
            context,
            "📌 Пожалуйста, используйте кнопки меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        return ConversationHandler.END

    logger.warning(f"🛠️ fallback_unknown: админ {update.effective_user.id} ввёл: {repr(text)}")

    # 🔽 КНОПКИ ГЛАВНОГО МЕНЮ — выход из диалога
    MAIN_MENU_BUTTONS = {
        SCHEDULE_BUTTON_TEXT,
        CATALOG_BUTTON_TEXT,
        ORDERS_BUTTON_TEXT,
        PROMOTIONS_BUTTON_TEXT,
        CONTACTS_BUTTON_TEXT,
        HELP_BUTTON_TEXT,
    }

    if text in MAIN_MENU_BUTTONS:
        logger.info(f"🚪 Админ выбрал меню '{text}' — выход из диалога")
        return await back_to_main_menu(update, context)

    # ❓ Неизвестный ввод — показываем подсказку
    await safe_reply(
        update,
        context,
        "📌 Пожалуйста, используйте кнопки ниже или команды.",
        reply_markup=get_admin_main_keyboard(),
    )
    return ConversationHandler.END


async def fallback_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное клиентское меню (унифицированный выход)."""
    if not await check_admin(update, context):
        logger.warning("🚫 fallback_back_to_main: не-админ пытается вернуться в меню")
        await safe_reply(
            update,
            context,
            "🏠 Вы в главном меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    logger.info("🔙 Админ вызвал возврат в главное меню")
    return await back_to_main_menu(update, context)


async def fallback_back_to_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору действия с партией."""
    if not await check_admin(update, context):
        logger.warning("🚫 fallback_back_to_actions: не-админ пытается выбрать действие")
        await safe_reply(
            update,
            context,
            "🏠 Вы в главном меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    logger.info("🔙 Админ возвратился к выбору действия с партией")
    await safe_reply(
        update,
        context,
        "🛠️ Выберите действие с партией:",
        reply_markup=get_action_keyboard(),
    )
    return WAITING_FOR_ACTION


async def fallback_edit_back_to_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору партии для редактирования."""
    if not await check_admin(update, context):
        logger.warning("🚫 fallback_edit_back_to_select: не-админ пытается редактировать партию")
        await safe_reply(
            update,
            context,
            "🏠 Вы в главном меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    logger.info("🔙 Админ возвратился к выбору партии для редактирования")
    await safe_reply(
        update,
        context,
        "📋 Выберите партию для редактирования:",
        reply_markup=get_action_keyboard(),
    )
    return EDIT_STOCK_SELECT


async def fallback_edit_back_to_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к вводу количества при редактировании партии."""
    if not await check_admin(update, context):
        logger.warning("🚫 fallback_edit_back_to_quantity: не-админ пытается ввести количество")
        await safe_reply(
            update,
            context,
            "🏠 Вы в главном меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    breed = context.user_data.get('edit_breed', 'цыплят')
    if not isinstance(breed, str):
        breed = 'цыплят'
    breed_safe = escape(breed)
    logger.info(f"🔙 Админ возвратился к вводу количества для «{breed}»")
    await safe_reply(
        update,
        context,
        f"🔢 Введите новое количество для «<b>{breed_safe}</b>»:",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    return EDIT_STOCK_QUANTITY


async def fallback_cancel_back_to_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору партии для отмены."""
    if not await check_admin(update, context):
        logger.warning("🚫 fallback_cancel_back_to_select: не-админ пытается отменить партию")
        await safe_reply(
            update,
            context,
            "🏠 Вы в главном меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    logger.info("🔙 Админ возвратился к выбору партии для отмены")
    await safe_reply(
        update,
        context,
        "📋 Выберите партию для отмены:",
        reply_markup=get_action_keyboard(),
    )
    return CANCEL_STOCK_SELECT