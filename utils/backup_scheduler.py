# utils/backup_scheduler.py

import os
import shutil
from datetime import datetime, time
from telegram.ext import Application, ContextTypes
from telegram import Document
import logging

# ✅ Импорт из одного источника
from database.repository import DB_PATH

logger = logging.getLogger(__name__)

BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup() -> str:
    """Создаёт копию БД с меткой времени"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Файл БД не найден: {DB_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    logger.info(f"✅ Резервная копия создана: {backup_path}")
    return backup_path


async def send_backup(context: ContextTypes.DEFAULT_TYPE):
    devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
    if not devops_chat_id:
        logger.warning("⚠️ DEVOPS_CHAT_ID не найден — автобэкап отключён")
        return

    try:
        backup_path = create_backup()
        file_size = os.path.getsize(backup_path) / (1024 * 1024)

        if file_size > 50:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"📦 Бэкап создан, но <b>слишком большой</b> ({file_size:.1f} MB) — не отправлен.",
                parse_mode="HTML"
            )
            return

        with open(backup_path, "rb") as f:
            await context.bot.send_document(
                chat_id=devops_chat_id,
                document=f,
                filename=f"backup_{datetime.now().strftime('%d.%m %H.%M')}.db",
                caption=f"✅ <b>Ежедневный бэкап</b>\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📊 Размер: {file_size:.1f} MB",
                parse_mode="HTML"
            )
        logger.info(f"📤 Автобэкап отправлен в чат {devops_chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при автобэкапе: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"🔴 <b>Ошибка автобэкапа</b>\n\n<code>{e}</code>",
                parse_mode="HTML"
            )
        except Exception as send_error:
            logger.critical(f"❌ Не удалось отправить уведомление: {send_error}")


def setup_backup_job(application: Application):
    job_queue = application.job_queue
    if not job_queue:
        logger.error("❌ JobQueue не доступен — автобэкап не установлен")
        return

    job_queue.run_daily(send_backup, time=time(hour=2, minute=0), name="daily_db_backup")
    logger.info("✅ Планировщик автобэкапа установлен: 02:00")