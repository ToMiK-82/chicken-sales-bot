"""
Команда /backup — безопасная выгрузка базы данных.
Использует sqlite3 .backup() для 'горячего' копирования.
Временные файлы создаются в папке backups/
Доступна только администраторам.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.admin_helpers import admin_required
from utils.messaging import safe_reply
from database.repository import DB_PATH
import logging
import os
import html
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# 📦 Текст команды (для /help)
HELP_TEXT = "📤 Создать резервную копию базы данных (только для админов)"

# Путь к папке бэкапов
BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)


@admin_required
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет безопасную копию БД админу через .backup()"""
    effective_message = update.effective_message
    user_id = update.effective_user.id

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

    # 🔧 Временный файл теперь в папке backups/
    temp_backup = os.path.join(
        BACKUP_DIR,
        f"temp_backup_{user_id}_{int(datetime.now().timestamp())}.db"
    )
    
    try:
        # Используем .backup() для горячей копии
        conn = sqlite3.connect(DB_PATH)
        with sqlite3.connect(temp_backup) as bck:
            conn.backup(bck)
        conn.close()

        file_size = os.path.getsize(temp_backup)
        if file_size > 50 * 1024 * 1024:  # 50 МБ
            human_size = f"{file_size / (1024*1024):.1f} МБ"
            await safe_reply(
                update,
                context,
                f"❌ Резервная копия слишком большая: {human_size} (>50 МБ)"
            )
            os.remove(temp_backup)
            return

        # Уникальное имя файла при отправке
        timestamp = update.message.date.strftime("%Y%m%d_%H%M%S")
        filename = f"backup_admin_{user_id}_{timestamp}.db"

        with open(temp_backup, "rb") as f:
            await effective_message.reply_document(
                document=f,
                filename=filename,
                caption="📦 <b>Резервная копия базы данных</b>\n✅ Создана по запросу администратора",
                parse_mode="HTML"
            )

        logger.info(f"📤 /backup: отправлено админу {user_id}, размер: {file_size / (1024*1024):.1f} МБ")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании или отправке бэкапа: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Не удалось создать или отправить резервную копию.")
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_backup):
            try:
                os.remove(temp_backup)
            except Exception as e:
                logger.error(f"❌ Не удалось удалить временный бэкап: {e}")


def register_backup_handler(application):
    """Регистрирует обработчик /backup"""
    application.add_handler(CommandHandler("backup", backup_command))
    logger.info("✅ Команда /backup зарегистрирована")


def get_help_text() -> str:
    """Возвращает текст помощи для этой команды"""
    return HELP_TEXT
