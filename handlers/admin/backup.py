"""
Команда /backup — выгружает файл базы данных.
Доступна только администраторам.
✅ Защита от MessageTooLong
✅ Экранирование HTML
✅ Уникальное имя файла
✅ Исправлено: reply_document → через effective_message
✅ Логирование
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.admin_helpers import admin_required
from utils.messaging import safe_reply
from database.repository import DB_PATH
import logging
import os
import html

logger = logging.getLogger(__name__)

# 📦 Текст команды (для /help)
HELP_TEXT = "📤 Создать резервную копию базы данных (только для админов)"


@admin_required
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет файл базы данных админу"""
    effective_message = update.effective_message

    if not os.path.exists(DB_PATH):
        folder_listing = "; ".join(os.listdir(".")[:10])
        if len(os.listdir(".")) > 10:
            folder_listing += "; ..."
        escaped_listing = html.escape(folder_listing)
        escaped_path = html.escape(os.path.abspath(DB_PATH))

        await safe_reply(
            update,
            context,
            f"❌ Файл базы данных не найден.\n"
            f"🔍 Путь: <code>{escaped_path}</code>\n"
            f"📁 Файлы в папке:\n<code>{escaped_listing}</code>",
            parse_mode="HTML"
        )
        logger.warning(f"❌ БД не найдена: {os.path.abspath(DB_PATH)}")
        return

    file_size = os.path.getsize(DB_PATH)
    if file_size > 50 * 1024 * 1024:  # 50 МБ
        human_size = f"{file_size / (1024*1024):.1f} МБ"
        await safe_reply(
            update,
            context,
            f"❌ База данных слишком большая: {human_size} (>50 МБ)"
        )
        return

    try:
        # ✅ Уникальное имя: user_id + timestamp
        timestamp = update.message.date.strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{update.effective_user.id}_{timestamp}.db"

        with open(DB_PATH, "rb") as f:
            await effective_message.reply_document(
                document=f,
                filename=filename,
                caption="📦 <b>Резервная копия базы данных</b>\n✅ Создана по запросу администратора",
                parse_mode="HTML"
            )
        logger.info(f"📤 /backup: отправлено админу {update.effective_user.id}, размер: {file_size / (1024*1024):.1f} МБ")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке бэкапа: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Не удалось отправить файл.")


def register_backup_handler(application):
    """Регистрирует обработчик /backup"""
    application.add_handler(CommandHandler("backup", backup_command))
    logger.info("✅ Команда /backup зарегистрирована")


# ✅ Опционально: добавь это в центральный help
def get_help_text() -> str:
    """Возвращает текст помощи для этой команды"""
    return HELP_TEXT