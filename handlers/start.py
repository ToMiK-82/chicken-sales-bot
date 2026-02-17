"""
Обработчик команды /start.
✅ Добавляет пользователя в БД при первом запуске
✅ Использует db.upsert_user из database/repository
✅ Совместим с рассылкой и admin-панелью
✅ Сохраняет имя, username, user_id
✅ Гарантирует, что все пользователи попадут в рассылку
"""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application
from config.buttons import get_main_keyboard
from utils.messaging import log_action, handle_error
from utils.helpers import back_to_main_menu
from database.repository import db  # ← Ключевой импорт для upsert_user
import logging
from html import escape

logger = logging.getLogger(__name__)

# === Флаг, чтобы не запускать дважды ===
ALREADY_STARTED = "ALREADY_STARTED"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, silent: bool = False):
    """
    Обработчик команды /start.
    Отправляет приветственное сообщение ТОЛЬКО при явном /start и после инициализации.
    
    Args:
        update: Telegram Update
        context: Context
        silent: Если True — не отправлять сообщение (для автозапуска)
    """
    try:
        if not update.message:
            logger.warning("Получен update без message в /start")
            return

        user = update.effective_user
        user_id = user.id
        full_name = f"{user.first_name} {user.last_name}".strip() if user.last_name else user.first_name or "Неизвестно"
        username = user.username

        # === ЖДЁМ ИНИЦИАЛИЗАЦИИ БД ===
        if not context.application.bot_data.get("INITIALIZED"):
            logger.debug(f"⏳ /start вызван до инициализации — игнорируем для пользователя {user_id}")
            return

        # === 🔥 ДОБАВЛЯЕМ ПОЛЬЗОВАТЕЛЯ В БАЗУ СРАЗУ ПРИ ЗАПУСКЕ ===
        try:
            await db.upsert_user(
                user_id=user_id,
                full_name=full_name,
                username=username,
                phone=None  # пока неизвестен
            )
            logger.info(f"✅ Пользователь {user_id} ({full_name}) добавлен/обновлён в БД при /start")
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении пользователя {user_id} в БД: {e}", exc_info=True)

        # === 1. Полный сброс состояния ===
        dialog_keys = [
            "awaiting_action", "dialog_state", "in_active_dialog",
            "selected_breed", "selected_date", "quantity", "cart",
            "phone", "current_handler", "conversation"
        ]
        cleared_keys = [k for k in dialog_keys if k in context.user_data]
        for key in cleared_keys:
            context.user_data.pop(key, None)
        if cleared_keys:
            logger.debug(f"🧹 Очищены ключи user_data: {cleared_keys}")

        # === 2. Устанавливаем флаг, что пользователь уже стартовал ===
        context.user_data[ALREADY_STARTED] = True

        # === 3. Обновляем список started_users в bot_data ===
        started_users = set(context.application.bot_data.get("started_users", []))
        started_users.add(user_id)
        context.application.bot_data["started_users"] = list(started_users)

        # === 4. Отправляем сообщение только при явном /start и не в silent режиме ===
        is_explicit_start = update.message.text and update.message.text.strip() == "/start"
        should_send = is_explicit_start and not silent

        if should_send:
            message = (
                f"👋 Привет, <b>{escape(full_name)}</b>!\n"
                "Добро пожаловать в сервис <b>Chicken_sales_bot</b>! 🐔\n\n"
                "Мы осуществляем продажу суточных цыплят сельскохозяйственных пород.\n"
                "Выберите нужный раздел 👇"
            )

            await update.message.reply_text(
                message,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )

            log_action(user_id, "Команда /start", "Главное меню")
        else:
            logger.info(f"🔄 Пользователь {full_name} ({user_id}) автоматически активирован после перезапуска")

    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}", exc_info=True)
        await handle_error(update, context)


def register_start_handler(application: Application):
    """Регистрирует обработчики /start и /back."""
    application.add_handler(CommandHandler("start", start), group=0)
    application.add_handler(CommandHandler("back", back_to_main_menu), group=0)
    logger.info("✅ Обработчики /start и /back зарегистрированы (group=0)")
