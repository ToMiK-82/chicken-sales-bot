"""
Ввод номера телефона: контакт или текст.
✅ Проверка верификации
✅ Ограничение >50 шт. только для не-админов
✅ Админ может вносить любые заказы от лица клиента
"""

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


"""
Ввод номера телефона: контакт, текст или выбор из доверенного.
✅ Предлагает использовать доверенный номер через кнопку
✅ Поддержка: контакт, ручной ввод, выбор
✅ Проверка верификации
✅ Ограничение >50 шт. только для не-админов
✅ Админ может вносить любые заказы от лица клиента
"""

from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
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
import logging

logger = logging.getLogger(__name__)


async def _back_to_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос телефона: с кнопками выбора действия."""
    phone = context.user_data.get("phone")
    verified = context.user_data.get("phone_verified")

    # Если есть доверенный номер — предлагаем использовать его
    if phone and verified and await db.is_trusted_phone(phone):
        logger.info(f"📞 Предлагаем доверенный номер: {phone}")

        keyboard = [
            [f"📱 Использовать: {phone}"],
            ["📞 Отправить контакт", "✍️ Ввести вручную"],
            [BTN_BACK_FULL]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await safe_reply(update, context,
                         f"📞 У нас сохранён ваш доверенный номер:\n"
                         f"<code>{phone}</code>\n\n"
                         f"Хотите использовать его или указать другой?",
                         reply_markup=reply_markup, parse_mode="HTML")
        return ENTER_PHONE

    # Если нет доверенного — стандартный ввод
    await safe_reply(update, context,
                     "📞 Введите номер телефона в формате +7XXXXXXXXXX\n"
                     "или нажмите кнопку ниже:",
                     reply_markup=get_phone_input_keyboard(), parse_mode="HTML")
    return ENTER_PHONE


async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода телефона: текст, контакт или кнопка."""
    text = update.message.text.strip() if update.message.text else None
    user_id = update.effective_user.id
    is_admin = user_id in context.application.bot_data.get("ADMIN_IDS", [])

    # Проверяем, нажал ли пользователь "Использовать: +7..."
    trusted_phone_match = None
    if text and text.startswith("📱 Использовать: +"):
        try:
            trusted_phone_match = text.split("📱 Использовать: ", 1)[1]
        except IndexError:
            pass

    # 1. Контакт
    if update.message.contact:
        phone = f"+{update.message.contact.phone_number.lstrip('+')}"
        verified = True

    # 2. Кнопка "Использовать доверенный"
    elif trusted_phone_match:
        phone = trusted_phone_match
        if not await db.is_trusted_phone(phone):
            await safe_reply(update, context,
                             "❌ Этот номер больше не доверенный. Введите новый.",
                             reply_markup=get_phone_input_keyboard())
            return ENTER_PHONE
        verified = True

    # 3. Назад
    elif text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    # 4. Ручной ввод
    elif text:
        # Приводим к формату +7
        if text.startswith("8") and len(text) == 11:
            phone = "+7" + text[1:]
        elif text.startswith("+7") and len(text) == 12:
            phone = text
        else:
            await safe_reply(update, context,
                             "❌ Введите +7XXXXXXXXXX, отправьте контакт или выберите из кнопок.",
                             reply_markup=get_phone_input_keyboard())
            return ENTER_PHONE
        verified = False

    else:
        # Неизвестный тип (например, стикер)
        await safe_reply(update, context,
                         "📌 Пожалуйста, введите номер или отправьте контакт.",
                         reply_markup=get_phone_input_keyboard())
        return ENTER_PHONE

    # 🔴 Проверка: номер заблокирован?
    if await db.is_phone_blocked(phone):
        clear_catalog_data(context)
        await safe_reply(update, context, "🚫 Номер заблокирован.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    # Сохраняем номер
    context.user_data.update({
        "phone": phone,
        "phone_verified": verified,
        "saved_phone": {"phone": phone, "verified": verified}
    })

    # Получаем количество
    qty = context.user_data.get("selected_quantity")
    if qty is None:
        await safe_reply(update, context, "❌ Ошибка: количество не указано.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    # ✅ Ограничение >50 шт. для не-верифицированных
    if not verified and qty > 50:
        if not is_admin:
            await safe_reply(update, context,
                             "📞 Для заказа более 50 шт. нужен верифицированный номер.",
                             reply_markup=get_back_only_keyboard())
            return ENTER_PHONE
        else:
            logger.info(f"🛠️ Админ {user_id} вносит заказ >50 шт. за клиента: {phone}")

    # 🔒 Попытки и блокировки — только для не-админов и не-доверенных
    if not is_admin and not verified and not await db.is_trusted_phone(phone):
        attempts = await db.get_daily_attempts(phone)
        if attempts >= 2:
            await db.block_phone(phone, "Слишком много попыток", 24)
            clear_catalog_data(context)
            await safe_reply(update, context, "🚫 Номер заблокирован.", reply_markup=get_main_keyboard())
            return ConversationHandler.END
        await db.add_attempt(phone)

    # Переход к подтверждению
    context.user_data["navigation_stack"].append(CONFIRM_ORDER)
    
    # ✅ Ленивый импорт — разрываем цикл
    from .confirmation import _back_to_confirmation
    return await _back_to_confirmation(update, context)
