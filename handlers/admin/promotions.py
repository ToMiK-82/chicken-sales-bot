"""
Обработчики управления акциями: добавление, просмотр, отмена.
Работает через ConversationHandler.

✅ Кнопки: 'Создать', 'Список', 'Назад' — в одной строке  
✅ После списка: 'Отменить' и 'Назад'  
✅ Отмена по ID: безопасно, с подтверждением  
✅ Все данные очищаются при выходе  
✅ Fallback безопасен  
✅ Валидация: start_date < end_date, корректный формат ДД.ММ.ГГГГ  
✅ Поддержка: фото, пропуск, даты  
✅ Группа: group=2  
✅ is_active=1 при создании  
"""

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from datetime import datetime
from html import escape

from config.buttons import (
    # --- Кнопки ---
    ADMIN_PROMO_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CONFIRM_FULL,
    BTN_LIST_FULL,
    BTN_CREATE_PROMO_FULL,
    BTN_CANCEL_PROMO_FULL,
    # --- Основные клавиатуры ---
    get_promo_action_keyboard,
    get_back_only_keyboard,
    get_confirmation_keyboard,
    get_promo_list_actions_keyboard,
)
from database.repository import db
from utils.admin_helpers import check_admin, exit_to_admin_menu
from utils.messaging import safe_reply

logger = logging.getLogger(__name__)

# === Константы ===
MAX_PROMO_TITLE_LENGTH = 100
MAX_PROMO_DESC_LENGTH = 1024
DATE_FORMAT = "%d.%m.%Y"

# === Состояния ===
PROMO_SELECT_ACTION = 0
PROMO_ADD_TITLE = 1
PROMO_ADD_DESC = 2
PROMO_ADD_IMAGE = 3
PROMO_ADD_START_DATE = 4
PROMO_ADD_END_DATE = 5
PROMO_CONFIRM_ADD = 6
PROMO_CANCEL_SELECT = 7
PROMO_CANCEL_CONFIRM = 8

# === Ключи для очистки ===
PROMO_KEYS = [
    'promo_title', 'promo_desc', 'promo_id', 'promo_current', 'promotions',
    'promo_start_date', 'promo_end_date', 'promo_image_url',
    'current_conversation', 'HANDLED'
]

# === Запуск ===
async def start_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        return await exit_to_admin_menu(update, context, "❌ У вас нет доступа.")

    # Очистка других режимов
    for key in ['stock_edit_mode', 'stock_list']:
        context.user_data.pop(key, None)

    await safe_reply(
        update,
        context,
        "🛠️ <b>Управление акциями</b>",
        reply_markup=get_promo_action_keyboard(),
        parse_mode="HTML",
    )
    context.user_data['current_conversation'] = 'promotions'
    context.user_data['HANDLED'] = True
    return PROMO_SELECT_ACTION


# === Выбор действия ===
async def handle_promo_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return await exit_to_admin_menu(update, context, "❌ Ожидался текст.", keys_to_clear=PROMO_KEYS)

    text = update.effective_message.text.strip()

    # Очистка других режимов
    for key in ['stock_edit_mode', 'stock_list']:
        context.user_data.pop(key, None)

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(
            update,
            context,
            "🚪 Возвращаемся в админ-меню.",
            keys_to_clear=['promotions']
        )

    # ✅ Список акций
    if text == BTN_LIST_FULL:
        promos = await db.get_active_promotions()
        if not promos:
            await safe_reply(
                update,
                context,
                "📭 Нет активных акций.",
                reply_markup=get_promo_action_keyboard(),
                parse_mode="HTML",
                disable_cooldown=True
            )
            context.user_data['HANDLED'] = True
            return PROMO_SELECT_ACTION

        sent_count = 0
        for promo in promos:
            try:
                promo_id = promo['id']
                title = escape(promo['title'])
                desc = escape(promo['description'])
                img_url = promo['image_url']
                start = promo['start_date']
                end = promo['end_date']

                start_str = f"📅 Начало: {start}\n" if start else ""
                end_str = f"🔚 Окончание: {end}\n" if end else "🔚 Окончание: бессрочно\n"

                message = f"🆔 <b>{promo_id}</b>\n\n📌 <b>{title}</b>\n\n{start_str}{end_str}{desc}"

                if img_url:
                    try:
                        await update.effective_message.reply_photo(
                            photo=img_url,
                            caption=message,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.warning(f"🖼️ Не удалось отправить фото для акции {promo_id}: {e}")
                        await safe_reply(
                            update,
                            context,
                            f"🖼️ Фото недоступно\n\n{message}",
                            parse_mode="HTML",
                            disable_cooldown=True
                        )
                else:
                    await safe_reply(
                        update,
                        context,
                        message,
                        parse_mode="HTML",
                        disable_cooldown=True
                    )
                sent_count += 1
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке акции {promo.get('id', 'unknown')}: {e}", exc_info=True)
                continue

        if sent_count == 0:
            await safe_reply(
                update,
                context,
                "⚠️ Не удалось отобразить ни одну акцию.",
                parse_mode="HTML",
                disable_cooldown=True
            )
        elif sent_count < len(promos):
            await safe_reply(
                update,
                context,
                f"⚠️ Показано {sent_count} из {len(promos)} акций.",
                parse_mode="HTML",
                disable_cooldown=True
            )

        await safe_reply(
            update,
            context,
            "✅ Выберите действие:",
            reply_markup=get_promo_list_actions_keyboard(),
            parse_mode="HTML",
            disable_cooldown=True
        )
        context.user_data['HANDLED'] = True
        return PROMO_CANCEL_SELECT

    # ✅ ОСНОВНАЯ ПОПРАВКА: Обработка кнопки "Создать"
    if text == BTN_CREATE_PROMO_FULL:
        await safe_reply(
            update,
            context,
            "✏️ Введите заголовок акции (макс. 100 симв.):",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_TITLE

    # ❌ Неизвестная команда
    await safe_reply(
        update,
        context,
        "📌 Выберите действие из кнопок ниже.",
        reply_markup=get_promo_action_keyboard(),
        parse_mode="HTML",
        disable_cooldown=True
    )
    context.user_data['HANDLED'] = True
    return PROMO_SELECT_ACTION


# === Добавление: заголовок ===
async def promo_add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message:
        return await exit_to_admin_menu(update, context, "❌ Ожидался текст.", keys_to_clear=PROMO_KEYS)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_promo_action(update, context)

    if not text or len(text) > MAX_PROMO_TITLE_LENGTH:
        await safe_reply(update, context, f"✏️ Введите заголовок (макс. {MAX_PROMO_TITLE_LENGTH} симв.):")
        context.user_data['HANDLED'] = True
        return PROMO_ADD_TITLE

    context.user_data['promo_title'] = text
    await safe_reply(
        update,
        context,
        "📝 Введите описание (макс. 1024 символа):",
        reply_markup=get_back_only_keyboard(),
    )
    context.user_data['HANDLED'] = True
    return PROMO_ADD_DESC


# === Добавление: описание ===
async def promo_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message:
        return await exit_to_admin_menu(update, context, "❌ Ожидался текст.", keys_to_clear=PROMO_KEYS)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "✏️ Введите заголовок акции (макс. 100 симв.):",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_TITLE

    if not text or len(text) > MAX_PROMO_DESC_LENGTH:
        await safe_reply(update, context, f"📝 Введите описание (макс. {MAX_PROMO_DESC_LENGTH} симв.):")
        context.user_data['HANDLED'] = True
        return PROMO_ADD_DESC

    context.user_data['promo_desc'] = text
    await safe_reply(
        update,
        context,
        "🖼️ Пришлите фото (или напишите <b>пропустить</b>):",
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML",
    )
    context.user_data['HANDLED'] = True
    return PROMO_ADD_IMAGE


# === Добавление: фото ===
async def promo_add_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "📝 Введите описание (макс. 1024 символа):",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_DESC

    if update.message and update.message.photo:
        context.user_data['promo_image_url'] = update.message.photo[-1].file_id
        await safe_reply(
            update,
            context,
            "📅 Введите дату начала в формате <b>ДД.ММ.ГГГГ</b> (или <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_START_DATE

    text = update.effective_message.text.strip() if update.effective_message else ""

    SKIP_COMMANDS = {"пропустить", "skip", "pass", "пропуск", "оставить", "как есть", ""}
    if text.lower() in SKIP_COMMANDS:
        context.user_data['promo_image_url'] = None
        await safe_reply(
            update,
            context,
            "📅 Введите дату начала в формате <b>ДД.ММ.ГГГГ</b> (или <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_START_DATE

    await safe_reply(
        update,
        context,
        "🖼️ Пришлите фото или напишите <b>пропустить</b>.",
        parse_mode="HTML",
    )
    context.user_data['HANDLED'] = True
    return PROMO_ADD_IMAGE


# === Добавление: дата начала ===
async def promo_add_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip() if update.effective_message else ""

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "🖼️ Пришлите фото (или напишите <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_IMAGE

    SKIP_COMMANDS = {"пропустить", "skip", "pass", "пропуск", "оставить", "как есть", ""}
    if text.lower() in SKIP_COMMANDS:
        context.user_data['promo_start_date'] = None
        await safe_reply(
            update,
            context,
            "🔚 Введите дату окончания (или <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_END_DATE

    try:
        dt = datetime.strptime(text, DATE_FORMAT)
        context.user_data['promo_start_date'] = dt.strftime("%Y-%m-%d")
        await safe_reply(
            update,
            context,
            f"✅ Начало: {text}\n\n🔚 Введите дату окончания (или <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_END_DATE
    except ValueError:
        await safe_reply(
            update,
            context,
            f"📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>, например: <code>25.12.2026</code>",
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_START_DATE


# === Добавление: дата окончания ===
async def promo_add_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip() if update.effective_message else ""

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "📅 Введите дату начала в формате <b>ДД.ММ.ГГГГ</b> (или <b>пропустить</b>):",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_ADD_START_DATE

    SKIP_COMMANDS = {"пропустить", "skip", "pass", "пропуск", "оставить", "как есть", ""}
    if text.lower() in SKIP_COMMANDS:
        context.user_data['promo_end_date'] = None
    else:
        try:
            dt = datetime.strptime(text, DATE_FORMAT)
            context.user_data['promo_end_date'] = dt.strftime("%Y-%m-%d")
        except ValueError:
            await safe_reply(
                update,
                context,
                f"📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>, например: <code>01.01.2027</code>",
                parse_mode="HTML",
            )
            context.user_data['HANDLED'] = True
            return PROMO_ADD_END_DATE

    # Валидация: start_date < end_date
    start = context.user_data.get('promo_start_date')
    end = context.user_data.get('promo_end_date')
    if start and end and start > end:
        await safe_reply(
            update,
            context,
            "❌ Дата начала не может быть позже даты окончания. Попробуйте снова.",
            parse_mode="HTML",
        )
        context.user_data['promo_end_date'] = None
        context.user_data['HANDLED'] = True
        return PROMO_ADD_END_DATE

    # Подтверждение
    title = context.user_data['promo_title']
    start_str = datetime.strptime(start, "%Y-%m-%d").strftime("%d.%m.%Y") if start else "не указана"
    end_str = datetime.strptime(end, "%Y-%m-%d").strftime("%d.%m.%Y") if end else "бессрочно"

    message = (
        f"✅ <b>Готово к добавлению</b>:\n\n"
        f"📌 <b>{escape(title)}</b>\n\n"
        f"📅 <b>Начало:</b> {start_str}\n"
        f"🔚 <b>Окончание:</b> {end_str}\n\n"
        f"Подтвердите добавление."
    )

    await safe_reply(
        update,
        context,
        message,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
    )
    context.user_data['HANDLED'] = True
    return PROMO_CONFIRM_ADD


# === Сохранение ===
async def promo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or update.effective_message.text != BTN_CONFIRM_FULL:
        return ConversationHandler.END

    if context.user_data.get('current_conversation') != 'promotions':
        return ConversationHandler.END

    try:
        await db.add_promotion(
            title=context.user_data['promo_title'],
            description=context.user_data['promo_desc'],
            image_url=context.user_data.get('promo_image_url'),
            start_date=context.user_data.get('promo_start_date'),
            end_date=context.user_data.get('promo_end_date'),
            is_active=True,
        )
        logger.info(f"✅ Админ {update.effective_user.id} добавил акцию: {context.user_data['promo_title']}")
        return await exit_to_admin_menu(
            update,
            context,
            "✅ Акция добавлена!",
            keys_to_clear=['promo_title', 'promo_desc', 'promo_image_url', 'promo_start_date', 'promo_end_date', 'current_conversation']
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении акции: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Не удалось добавить акцию.")


# === Шаг 1: Выбор действия после списка ===
async def handle_promo_cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """После вывода списка: отменить или назад."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_admin_menu(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "🛠️ <b>Управление акциями</b>",
            reply_markup=get_promo_action_keyboard(),
            parse_mode="HTML",
        )
        context.user_data['HANDLED'] = True
        return PROMO_SELECT_ACTION

    if text == BTN_CANCEL_PROMO_FULL:
        await safe_reply(
            update,
            context,
            "🗑️ Введите ID акции, которую хотите отменить:",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_CANCEL_CONFIRM

    await safe_reply(
        update,
        context,
        "📌 Пожалуйста, используйте кнопки.",
        reply_markup=get_promo_list_actions_keyboard(),
    )
    context.user_data['HANDLED'] = True
    return PROMO_CANCEL_SELECT


# === Шаг 2: Подтверждение отмены по ID ===
async def handle_promo_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение отмены акции по ID."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_admin_menu(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        promos = await db.get_active_promotions()
        msg = "📭 Нет активных акций." if not promos else "✅ Выберите действие:"
        await safe_reply(
            update,
            context,
            msg,
            reply_markup=get_promo_list_actions_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_CANCEL_SELECT

    if not text.isdigit():
        await safe_reply(
            update,
            context,
            "❌ Введите корректный ID акции.",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_CANCEL_CONFIRM

    promo_id = int(text)
    promo = await db.get_promotion_by_id(promo_id)
    if not promo:
        await safe_reply(
            update,
            context,
            "❌ Акция с таким ID не найдена.",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return PROMO_CANCEL_CONFIRM

    try:
        await db.delete_promotion(promo_id)
        logger.info(f"✅ Админ {update.effective_user.id} отменил акцию ID={promo_id}")
        await safe_reply(
            update,
            context,
            f"🗑️ Акция №<b>{promo_id}</b> успешно удалена.",
            reply_markup=get_promo_action_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при отмене акции {promo_id}: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Не удалось отменить акцию.")

    for key in PROMO_KEYS:
        context.user_data.pop(key, None)
    context.user_data["HANDLED"] = True
    return PROMO_SELECT_ACTION


# === Fallback — безопасный выход ===
async def fallback_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in ['stock_edit_mode', 'stock_list', 'current_conversation']:
        context.user_data.pop(key, None)

    return await exit_to_admin_menu(
        update,
        context,
        "🚪 Вы вышли из управления акциями.",
        keys_to_clear=PROMO_KEYS
    )


# === Регистрация ===
def register_admin_promotions_handler(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ADMIN_PROMO_BUTTON_TEXT]),
                start_promotions
            )
        ],
        states={
            PROMO_SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_promo_action)],
            PROMO_ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_add_title)],
            PROMO_ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_add_desc)],
            PROMO_ADD_IMAGE: [
                MessageHandler(filters.PHOTO, promo_add_image),
                MessageHandler(filters.TEXT & ~filters.COMMAND, promo_add_image),
            ],
            PROMO_ADD_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_add_start_date)],
            PROMO_ADD_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_add_end_date)],
            PROMO_CONFIRM_ADD: [MessageHandler(filters.Text([BTN_CONFIRM_FULL]), promo_save)],
            PROMO_CANCEL_SELECT: [
                MessageHandler(filters.Text([BTN_CANCEL_PROMO_FULL, BTN_BACK_FULL]), handle_promo_cancel_select),
            ],
            PROMO_CANCEL_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_promo_cancel_confirm),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, fallback_to_admin_menu),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_promotions_handler",
    )

    application.add_handler(conv_handler, group=2)
    logger.info("✅ Обработчик 'Управление акциями' зарегистрирован")