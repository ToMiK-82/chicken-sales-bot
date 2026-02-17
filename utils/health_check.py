# utils/health_check.py

"""
Проверка работоспособности бота: БД, админы, кэш.
"""

from telegram import Update
from telegram.ext import ContextTypes
from utils.admin_helpers import check_admin, refresh_admin_cache, is_admin
from database.repository import db
import logging

logger = logging.getLogger(__name__)


async def health_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет отчёт о состоянии бота"""
    if not await check_admin(update, context):
        return

    report = ["🔧 <b>Состояние бота</b> 🧪\n"]

    # Проверка: БД доступна
    try:
        await db.execute_read("SELECT 1")
        report.append("✅ База данных: <b>работает</b>")
    except Exception as e:
        report.append(f"❌ База данных: недоступна ({e})")
        logger.error(f"Health check — DB error: {e}")

    # Проверка: админы
    try:
        admins = await db.get_all_admins()
        admin_ids = [a[0] for a in admins]
        report.append(f"🛠️ Администраторов в БД: <b>{len(admins)}</b>")
        if not admin_ids:
            report.append("⚠️ <b>Нет ни одного админа!</b>")
    except Exception as e:
        report.append(f"❌ Не удалось получить админов: {e}")

    # Проверка: кэш админов
    try:
        # Принудительно обновим кэш
        await refresh_admin_cache(context.application)
        current_cache = [uid for uid in admin_ids if await is_admin(uid)]
        report.append(f"🧠 Кэш админов: обновлён, {len(current_cache)} админов")
    except Exception as e:
        report.append(f"❌ Ошибка кэша: {e}")

    # Проверка: собственный доступ
    my_id = update.effective_user.id
    if await is_admin(my_id, context.application):
        report.append("🟢 Вы: <b>администратор</b>")
    else:
        report.append("🔴 Вы: не в кэше админов (ошибка?)")

    # Отправляем
    await update.message.reply_text("\n".join(report), parse_mode="HTML")


def register_health_check(application):
    """Регистрирует команду /health"""
    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler("health", health_check_command))
    logger.info("✅ Команда /health зарегистрирована")
