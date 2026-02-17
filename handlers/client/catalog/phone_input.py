"""Ввод номера телефона: контакт или текст."""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config.buttons import (
    get_phone_input_keyboard,
    get_back_only_keyboard,
    get_main_keyboard,
    BTN_BACK_FULL,
)
from utils.messaging import safe_reply
from .navigation import handle_back_button
from .utils import clear_catalog_data
from states import ENTER_PHONE, CONFIRM_ORDER, CHOOSE_QUANTITY
from database.repository import db


async def _back_to_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос телефона: автоматически подставляем доверенный номер."""
    phone = context.user_data.get("phone")
    verified = context.user_data.get("phone_verified")

    # Если номер уже есть и он доверенный — не запрашиваем
    if phone and verified and await db.is_trusted_phone(phone):
        from logging import getLogger
        logger = getLogger(__name__)
        logger.info(f"📞 Автоподстановка доверенного номера: {phone}")
        await safe_reply(update, context, f"📞 Используем ваш номер: <code>{phone}</code>", parse_mode="HTML")
        
        # ✅ Ленивый импорт — разрываем цикл
        from .confirmation import _back_to_confirmation
        return await _back_to_confirmation(update, context)

    await safe_reply(update, context,
                     "📞 Введите номер телефона в формате +7XXXXXXXXXX\n"
                     "или нажмите кнопку ниже:",
                     reply_markup=get_phone_input_keyboard(), parse_mode="HTML")
    return ENTER_PHONE


async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода телефона (текст или контакт)."""
    if update.message.contact:
        phone = f"+{update.message.contact.phone_number.lstrip('+')}"
        verified = True
    else:
        text = update.message.text.strip()
        if text == BTN_BACK_FULL:
            return await handle_back_button(update, context)
        if text.startswith("8") and len(text) == 11:
            text = "+7" + text[1:]
        elif text.startswith("+7") and len(text) == 12:
            pass
        else:
            await safe_reply(update, context, "❌ Введите +7XXXXXXXXXX или отправьте контакт.", reply_markup=get_phone_input_keyboard())
            return ENTER_PHONE
        phone = text
        verified = False

    # 🔴 Проверка: номер заблокирован?
    if await db.is_phone_blocked(phone):
        clear_catalog_data(context)
        await safe_reply(update, context, "🚫 Номер заблокирован.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    context.user_data.update({
        "phone": phone,
        "phone_verified": verified,
        "saved_phone": {"phone": phone, "verified": verified}
    })

    qty = context.user_data["selected_quantity"]
    if not verified and qty > 50:
        await safe_reply(update, context, "📞 Для >50 шт. нужен верифицированный номер.", reply_markup=get_back_only_keyboard())
        return ENTER_PHONE

    if not verified and not await db.is_trusted_phone(phone):
        attempts = await db.get_daily_attempts(phone)
        if attempts >= 2:
            await db.block_phone(phone, "Слишком много попыток", 24)
            clear_catalog_data(context)
            await safe_reply(update, context, "🚫 Номер заблокирован.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        await db.add_attempt(phone)

    context.user_data["navigation_stack"].append(CONFIRM_ORDER)
    
    # ✅ Ленивый импорт — безопасный переход к подтверждению
    from .confirmation import _back_to_confirmation
    return await _back_to_confirmation(update, context)