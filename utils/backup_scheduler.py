"""
Автоматическое резервное копирование базы данных
✅ Горячая копия через sqlite3 .backup()
✅ Отправка в DevOps-чат
✅ Очистка бэкапов старше 7 дней
✅ Защита от больших файлов (>50 МБ)
✅ Логирование и уведомления об ошибках
"""

import os
import shutil
from datetime import datetime, time
from telegram.ext import Application, ContextTypes
from telegram import Document
import logging
import sqlite3

# ✅ Импорт из одного источника
from database.repository import DB_PATH
from main import BOT_VERSION  # Для имени файла

logger = logging.getLogger(__name__)

BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Настройки
BACKUP_RETENTION_DAYS = 7
MAX_FILE_SIZE_MB = 50


def create_backup() -> str:
    """
    Создаёт 'горячую' резервную копию БД с помощью SQLite .backup()
    Работает даже при активной записи.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Файл БД не найден: {DB_PATH}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")

    try:
        # Подключаемся к основной БД
        conn = sqlite3.connect(DB_PATH)
        # Создаём или подключаемся к файлу бэкапа
        with sqlite3.connect(backup_path) as bck:
            conn.backup(bck)
        conn.close()

        logger.info(f"✅ Горячая резервная копия создана: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"❌ Ошибка при создании бэкапа: {e}", exc_info=True)
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                logger.info(f"🧹 Временный файл удалён: {backup_path}")
            except Exception:
                pass
        raise


def cleanup_old_backups(keep_days: int = BACKUP_RETENTION_DAYS):
    """
    Удаляет файлы .db в папке backups/, старше keep_days дней
    """
    if not os.path.exists(BACKUP_DIR):
        return

    now = datetime.now().timestamp()
    cutoff = now - (keep_days * 24 * 3600)
    deleted_count = 0

    for file in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, file)
        if file.endswith(".db") and os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff:
                try:
                    os.remove(filepath)
                    logger.info(f"🗑️ Удалён старый бэкап: {file}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"❌ Не удалось удалить {file}: {e}")

    if deleted_count > 0:
        logger.info(f"🧹 Очистка завершена: удалено {deleted_count} старых бэкапов")


async def send_backup(context: ContextTypes.DEFAULT_TYPE):
    """
    Полный цикл: создание → отправка → очистка
    Запускается каждый день через JobQueue
    """
    devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
    if not devops_chat_id:
        logger.warning("⚠️ DEVOPS_CHAT_ID не найден — автобэкап отключён")
        return

    try:
        # 1. Создаём бэкап
        backup_path = create_backup()
        file_size_mb = os.path.getsize(backup_path) / (1024 * 1024)

        # 2. Проверяем размер
        if file_size_mb > MAX_FILE_SIZE_MB:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"📦 Бэкап создан, но <b>слишком большой</b> ({file_size_mb:.1f} MB) — не отправлен.",
                parse_mode="HTML"
            )
            logger.warning(f"📤 Бэкап не отправлен — слишком большой: {file_size_mb:.1f} MB")
            return

        # 3. Готовим имя файла с версией
        human_time = datetime.now().strftime("%d.%m %H.%M")
        filename = f"backup_v{BOT_VERSION}_{human_time}.db"

        # 4. Отправляем в DevOps
        with open(backup_path, "rb") as f:
            await context.bot.send_document(
                chat_id=devops_chat_id,
                document=f,
                filename=filename,
                caption=(
                    f"✅ <b>Ежедневный резервный бэкап</b>\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"📦 Версия бота: <code>{BOT_VERSION}</code>\n"
                    f"📊 Размер: {file_size_mb:.1f} MB"
                ),
                parse_mode="HTML"
            )

        logger.info(f"📤 Автобэкап успешно отправлен в чат {devops_chat_id}")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при автобэкапе: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"🔴 <b>Ошибка автобэкапа</b>\n\n<code>{type(e).__name__}: {e}</code>",
                parse_mode="HTML"
            )
        except Exception as send_error:
            logger.critical(f"❌ Не удалось отправить уведомление об ошибке: {send_error}")

    finally:
        # 5. Очищаем старые бэкапы (даже если была ошибка)
        cleanup_old_backups()


def setup_backup_job(application: Application):
    """
    Регистрирует задачу ежедневного резервного копирования
    Вызывается в post_init
    """
    job_queue = application.job_queue
    if not job_queue:
        logger.error("❌ JobQueue не доступен — автобэкап не установлен")
        return

    # Запуск каждый день в 02:00
    job_queue.run_daily(send_backup, time=time(hour=2, minute=0), name="daily_db_backup")
    logger.info("✅ Планировщик автобэкапа установлен: 02:00")
