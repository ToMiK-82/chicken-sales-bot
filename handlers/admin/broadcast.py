"""
Модуль рассылки: админ может отправить сообщение всем или группе пользователей.
Поддерживает текст и фото.
Использует единые утилиты и проверку прав.
✅ Исправлено: точное совпадение кнопок с эмодзи
✅ Исправлено: ConversationHandler в group=2
✅ Исправлено: все кнопки — из config/buttons
✅ Исправлено: «Назад» работает по шагам
✅ Исправлено: выход через exit_to_admin_menu — единый стиль
"""

import logging
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram import Update

from database.repository import db
from config.buttons import (
    # --- Клавиатуры ---
    get_back_only_keyboard,
    get_confirmation_keyboard,
    get_recipients_keyboard,
    # --- Кнопки с эмодзи ---
    BTN_CONFIRM_FULL,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    # --- Тексты кнопок с эмодзи ---
    BROADCAST_RECIPIENTS_ALL_FULL,
    BROADCAST_RECIPIENTS_CUSTOMERS_FULL,
    BROADCAST_RECIPIENTS_ADMINS_FULL,
    BROADCAST_RECIPIENTS_TEST_FULL,
    # --- Entry-point кнопки ---
    ADMIN_BROADCAST_BUTTON_TEXT as BROADCAST_BUTTON_TEXT,
)
from utils.admin_helpers import check_admin, exit_to_admin_menu
from utils.messaging import safe_reply

logger = logging.getLogger(__name__)

# === Состояния ===
ENTER_MESSAGE = 0
SELECT_RECIPIENTS = 1
CONFIRM_SEND = 2

# === Ключи для очистки ===
BROADCAST_KEYS = [
    'broadcast_type', 'text', 'photo_id', 'caption', 'recipients',
    'current_conversation', 'broadcast_flow_history'
]

# === Константа завершения ===
END = ConversationHandler.END


# === Fallback: полная отмена ===
async def fallback_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход в админ-панель с очисткой."""
    return await exit_to_admin_menu(
        update,
        context,
        message="🚪 Рассылка отменена.",
        keys_to_clear=BROADCAST_KEYS
    )


# === 1. Начало: запрос сообщения ===
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        return await exit_to_admin_menu(update, context, "❌ У вас нет доступа.")

    # Выходим из других диалогов
    if context.user_data.get("current_conversation") in ("stock_view", "edit_stock"):
        from handlers.admin.stocks.view import STOCK_VIEW_KEYS
        from handlers.admin.stocks.edit import EDIT_STOCK_KEYS
        for key in STOCK_VIEW_KEYS + EDIT_STOCK_KEYS + ["current_conversation"]:
            context.user_data.pop(key, None)

    await safe_reply(
        update,
        context,
        "📩 <b>Введите сообщение для рассылки.</b>\n"
        "Можно отправить текст или фото (с подписью).",
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML"
    )

    context.user_data['broadcast_flow_history'] = ['ENTER_MESSAGE']
    context.user_data['current_conversation'] = 'broadcast'
    context.user_data["HANDLED"] = True

    return ENTER_MESSAGE


# === 2. Принимаем текст или фото ===
async def enter_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip() if update.effective_message.text else ""

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(
            update,
            context,
            "🚪 Рассылка отменена.",
            keys_to_clear=BROADCAST_KEYS
        )

    if update.message.photo:
        context.user_data['broadcast_type'] = 'photo'
        context.user_data['photo_id'] = update.message.photo[-1].file_id
        context.user_data['caption'] = update.message.caption or ""
        await safe_reply(update, context, "📸 Фото получено.")
    elif update.message.text:
        context.user_data['broadcast_type'] = 'text'
        context.user_data['text'] = update.message.text
        await safe_reply(update, context, "📝 Текст получен.")
    else:
        await safe_reply(update, context, "❌ Отправьте текст или фото.")
        return ENTER_MESSAGE

    await safe_reply(
        update,
        context,
        "📬 Кому отправить?",
        reply_markup=get_recipients_keyboard(),
    )
    context.user_data['broadcast_flow_history'].append('SELECT_RECIPIENTS')
    context.user_data["HANDLED"] = True
    return SELECT_RECIPIENTS


# === 3. Выбор получателя ===
async def select_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        context.user_data['broadcast_flow_history'].pop()
        await safe_reply(
            update,
            context,
            "📩 Отправьте новое сообщение или нажмите «Назад».",
            reply_markup=get_back_only_keyboard()
        )
        context.user_data["HANDLED"] = True
        return ENTER_MESSAGE

    valid_recipients = {
        BROADCAST_RECIPIENTS_ALL_FULL,
        BROADCAST_RECIPIENTS_CUSTOMERS_FULL,
        BROADCAST_RECIPIENTS_ADMINS_FULL,
        BROADCAST_RECIPIENTS_TEST_FULL,
    }

    if text not in valid_recipients:
        await safe_reply(
            update,
            context,
            "❌ Выберите получателя из кнопок:",
            reply_markup=get_recipients_keyboard(),
        )
        return SELECT_RECIPIENTS

    context.user_data['recipients'] = text
    await safe_reply(
        update,
        context,
        "Подтвердите отправку:",
        reply_markup=get_confirmation_keyboard()
    )
    context.user_data['broadcast_flow_history'].append('CONFIRM_SEND')
    context.user_data["HANDLED"] = True
    return CONFIRM_SEND


# === 4. Подтверждение и отправка ===
async def confirm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        context.user_data['broadcast_flow_history'].pop()
        await safe_reply(
            update,
            context,
            "📬 Кому отправить?",
            reply_markup=get_recipients_keyboard(),
        )
        context.user_data["HANDLED"] = True
        return SELECT_RECIPIENTS

    if text != BTN_CONFIRM_FULL:
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Отправка отменена.",
            keys_to_clear=BROADCAST_KEYS
        )

    b_type = context.user_data.get('broadcast_type')
    recipients_label = context.user_data.get('recipients')

    if not b_type or not recipients_label:
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Ошибка данных.",
            keys_to_clear=BROADCAST_KEYS
        )

    try:
        if recipients_label == BROADCAST_RECIPIENTS_ALL_FULL:
            rows = await db.execute_read("SELECT DISTINCT user_id FROM users")
        elif recipients_label == BROADCAST_RECIPIENTS_CUSTOMERS_FULL:
            rows = await db.execute_read("SELECT DISTINCT user_id FROM orders WHERE status = 'active'")
        elif recipients_label == BROADCAST_RECIPIENTS_ADMINS_FULL:
            rows = await db.execute_read("SELECT user_id FROM admins")
        elif recipients_label == BROADCAST_RECIPIENTS_TEST_FULL:
            user_id = update.effective_user.id
            rows = [(user_id,)]
        else:
            rows = []

        user_ids = [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователей: {e}", exc_info=True)
        return await exit_to_admin_menu(
            update,
            context,
            "❌ Ошибка базы данных.",
            keys_to_clear=BROADCAST_KEYS
        )

    logger.info(f"Запуск рассылки: {len(user_ids)} получателей, тип: {b_type}")

    sent, blocked, failed = 0, 0, 0
    for user_id in user_ids:
        try:
            if b_type == 'text':
                await context.bot.send_message(
                    chat_id=user_id,
                    text=context.user_data['text'],
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            elif b_type == 'photo':
                caption = context.user_data.get('caption', '')
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=context.user_data['photo_id'],
                    caption=caption,
                    parse_mode="HTML" if caption else None
                )
            sent += 1
        except Exception as e:
            error_msg = str(e).lower()
            if "blocked" in error_msg or "kicked" in error_msg or "bot was blocked" in error_msg:
                logger.info(f"🚫 Пользователь {user_id} заблокировал бота — пропускаем.")
                blocked += 1
            else:
                logger.error(f"❌ Ошибка отправки {user_id}: {e}")
                failed += 1

    summary = (
        f"📤 <b>Рассылка завершена:</b>\n"
        f"✅ Доставлено: <b>{sent}</b>\n"
        f"🛡️ Заблокировали: <b>{blocked}</b>\n"
        f"❌ Ошибки: <b>{failed}</b>"
    )

    await exit_to_admin_menu(
        update,
        context,
        summary,
        parse_mode="HTML",
        keys_to_clear=BROADCAST_KEYS
    )
    return END


# === Fallback: безопасная обработка мусора ===
async def fallback_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, context, "📌 Пожалуйста, используйте кнопки меню.")
    # Возвращаем текущее состояние, чтобы не сломать диалог
    return None  # Telegram сам сохранит состояние


# === Регистрация обработчика ===
def register_admin_broadcast_handler(application):
    """Регистрирует обработчик рассылки"""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([BROADCAST_BUTTON_TEXT]),
                handle_broadcast
            )
        ],
        states={
            ENTER_MESSAGE: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), fallback_to_main),  # ← Точная обработка
                MessageHandler(filters.PHOTO, enter_message),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_message),
            ],
            SELECT_RECIPIENTS: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), select_recipients),  # ← Обратно к сообщению
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_recipients),
            ],
            CONFIRM_SEND: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), confirm_send),      # ← Обратно к выбору
                MessageHandler(filters.Text([BTN_CONFIRM_FULL]), confirm_send),   # ← Подтверждение
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_send),    # ← На всякий случай
            ],
        },
        fallbacks=[
            MessageHandler(filters.Text([BTN_CANCEL_FULL]), fallback_to_main),
            MessageHandler(filters.COMMAND, fallback_to_main),
            MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_unknown),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_broadcast_handler"
    )

    application.add_handler(conv_handler, group=2)
    logger.info("✅ Обработчик 'Рассылка' (админ) зарегистрирован (group=2)")
