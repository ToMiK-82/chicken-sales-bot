"""
Модуль диагностики: /health — показывает состояние бота.
Только для админов.
✅ Полный подсчёт обработчиков
✅ Экспорт времени запуска
✅ Поддержка /help
"""

import logging
import platform
import sys
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from utils.admin_helpers import check_admin
from utils.messaging import safe_reply

logger = logging.getLogger(__name__)

# 🕒 Время запуска бота (публичная функция ниже)
_bot_start_time = datetime.now(timezone.utc)

# 📚 Текст помощи
HELP_TEXT = "🏥 Проверить состояние бота: время работы, систему, обработчики"


def get_bot_start_time() -> datetime:
    """
    Возвращает время запуска бота.
    Можно использовать в других модулях (например, статистика, мониторинг).
    """
    return _bot_start_time


async def handle_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет диагностическую информацию о боте."""
    if not await check_admin(update, context):
        return

    try:
        # ⏱️ Время работы
        uptime = datetime.now(timezone.utc) - _bot_start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        # 🖥️ Информация о системе
        python_version = platform.python_version()
        system = platform.system()
        machine = platform.machine()

        # 🧩 Подсчёт всех обработчиков (по всем группам)
        handler_count = sum(
            len(handlers) for handlers in context.application.handlers.values()
        )

        # ⏲️ Задачи в планировщике
        job_count = len(context.application.job_queue.jobs()) if context.application.job_queue else 0

        # 📊 Формирование сообщения
        message = (
            "🏥 <b>Диагностика бота</b>\n\n"
            f"🟢 <b>Состояние:</b> работает\n"
            f"🕒 <b>Время работы:</b> {hours} ч {minutes} мин\n"
            f"📅 <b>Запущен:</b> {_bot_start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"

            f"⚙️ <b>Версия Python:</b> {python_version}\n"
            f"🖥️ <b>Платформа:</b> {system} {machine}\n\n"

            f"🧩 <b>Всего обработчиков:</b> {handler_count}\n"
            f"⏱️ <b>Планировщик (jobs):</b> {job_count}\n\n"

            f"👥 <b>Пользователь:</b> {update.effective_user.full_name} (ID: {update.effective_user.id})\n"
            f"💬 <b>Чат:</b> {update.effective_chat.id}\n\n"

            f"✅ <b>Проверка пройдена!</b>"
        )

        await safe_reply(update, context, message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка в /health: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Ошибка при сборе данных.")


def register_health_handler(application):
    """Регистрирует обработчик /health"""
    application.add_handler(CommandHandler("health", handle_health))
    logger.info("✅ Обработчик /health зарегистрирован")


def get_help_text() -> str:
    """Возвращает текст помощи для команды /health"""
    return HELP_TEXT