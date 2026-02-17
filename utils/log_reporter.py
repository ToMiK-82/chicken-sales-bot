# utils/log_reporter.py
"""
Отправляет ежедневный отчёт по логам в DevOps-чат.
✅ Автоматически: каждый день в 6:00
✅ Ручная команда: /logreport (только для DEVOPS_CHAT_ID)
✅ Автоочистка старых логов (старше 7 дней)
"""

import re
import logging
import os
from datetime import datetime, timedelta
from collections import Counter
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

logger = logging.getLogger(__name__)

# --- Настройки ---
LOG_FILE = "bot.log"
LOG_MAX_AGE_DAYS = 7  # Удалять логи старше 7 дней

# --- Паттерны для анализа ---
# Пример лога: "📝 fallback: 'привет' → не найдено"
FALLBACK_PATTERN = re.compile(r"📝 fallback: '([^']+)' →")

# Пример: "❌ Ошибка при создании заказа: UNIQUE constraint failed"
ERROR_PATTERN = re.compile(r"(ERROR|CRITICAL|❌).*?(?=\s*\n|$)", re.IGNORECASE)

# Пример: "suggest_correction('цыплята') → 'Каталог'"
SUGGESTION_PATTERN = re.compile(r"suggest_correction\('([^']+)'\) → '([^']+)'")

# --- Основная функция: отправка отчёта ---
async def send_log_report(context: ContextTypes.DEFAULT_TYPE):
    """
    Анализирует логи за последние 24 часа и отправляет отчёт.
    """
    bot = context.bot
    devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")

    if not devops_chat_id:
        logger.warning("❌ Не задан DEVOPS_CHAT_ID для отчёта по логам")
        return

    # Очищаем старые логи
    await cleanup_old_logs()

    # Проверяем наличие основного файла
    if not os.path.exists(LOG_FILE):
        await bot.send_message(
            devops_chat_id,
            "❌ Файл логов не найден: <code>bot.log</code>",
            parse_mode="HTML"
        )
        return

    # Период анализа: последние 24 часа
    since_date = datetime.now() - timedelta(days=1)

    unknown_messages = []      # Что вводили вручную
    errors = []                # Ошибки
    suggestions = []           # Коррекции через suggest_correction
    hourly_activity = Counter()  # Активность по часам

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Извлекаем дату
                try:
                    dt_str = line.split(" - ")[0]
                    try:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S,%f")
                    except ValueError:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    dt = None

                # Фильтр по дате
                if dt and dt < since_date:
                    continue

                # Считаем активность
                if dt:
                    hourly_activity[dt.hour] += 1

                # Анализ необработанных сообщений
                fallback_match = FALLBACK_PATTERN.search(line)
                if fallback_match:
                    raw_text = fallback_match.group(1).strip()
                    if raw_text:
                        unknown_messages.append(raw_text.lower())

                # Ошибки (кроме тривиальных)
                if ERROR_PATTERN.search(line) and "fallback" not in line.lower():
                    errors.append(line.strip())

                # Статистика автокоррекции
                suggest_match = SUGGESTION_PATTERN.search(line)
                if suggest_match:
                    suggestion = suggest_match.group(2).strip()
                    if suggestion:
                        suggestions.append(suggestion)

    except Exception as e:
        error_msg = f"❌ Ошибка при чтении {LOG_FILE}: {e}"
        logger.error(error_msg)
        await bot.send_message(devops_chat_id, error_msg)
        return

    # --- Формируем отчёт ---
    top_unknown = Counter(unknown_messages).most_common(10)
    top_suggestions = Counter(suggestions).most_common(5)

    text = (
        "📊 <b>ОТЧЁТ ПО ЛОГАМ БОТА</b>\n"
        f"📅 <b>{since_date.strftime('%d.%m.%Y')}</b>\n\n"
    )

    text += f"💬 Введено вручную: <b>{len(unknown_messages)}</b>\n"
    text += f"🔔 Ошибок: <b>{len(errors)}</b>\n\n"

    # Топ-вводов
    if top_unknown:
        text += "<b>🔝 ТОП-10 фраз (не по кнопкам):</b>\n"
        for msg, count in top_unknown:
            text += f"   • <code>{msg}</code> — {count}x\n"
        text += "\n"

    # Частые коррекции
    if top_suggestions:
        text += "<b>🎯 Часто понимали как:</b>\n"
        for sug, count in top_suggestions:
            text += f"   • <code>{sug}</code> — {count}x\n"
        text += "\n"

    # Активность
    if hourly_activity:
        peak_hours = [f"{h}:00" for h, _ in hourly_activity.most_common(3)]
        text += "<b>📈 Пик активности:</b> " + ", ".join(peak_hours) + "\n\n"
    else:
        text += "<b>📈 Активность:</b> нет данных\n\n"

    # Последние ошибки
    if errors:
        text += "<b>🚨 Последние ошибки (2):</b>\n"
        for err in errors[-2:]:
            # Обрезаем длинные строки
            clean_err = err.replace(TOKEN, "TOKEN_HIDDEN") if (TOKEN := os.getenv("TELEGRAM_TOKEN")) else err
            text += f"   <code>{clean_err[:80]}...</code>\n"

    try:
        await bot.send_message(devops_chat_id, text, parse_mode="HTML")
        logger.info("✅ Отчёт по логам отправлен в DevOps")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить отчёт: {e}")


# --- Очистка старых логов ---
async def cleanup_old_logs():
    """
    Удаляет старые ротированные логи: bot.log.1, bot.log.2.gz и т.п.
    """
    cutoff = datetime.now() - timedelta(days=LOG_MAX_AGE_DAYS)
    deleted_count = 0

    for filename in os.listdir("."):
        if not (
            filename.startswith("bot.log.") or
            (filename.endswith(".log") and filename != "bot.log")
        ):
            continue

        filepath = os.path.join(".", filename)
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mod_time < cutoff:
                os.remove(filepath)
                logger.info(f"🗑 Удалён старый лог: {filename}")
                deleted_count += 1
        except Exception as e:
            logger.error(f"❌ Не удалось удалить {filename}: {e}")

    if deleted_count:
        logger.info(f"✅ Очистка логов: удалено {deleted_count} файлов")


# --- Команда: /logreport ---
async def log_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ручной запуск отчёта. Доступен только DEVOPS_CHAT_ID.
    """
    user_id = update.effective_user.id
    devops_id = context.application.bot_data.get("DEVOPS_CHAT_ID")

    if user_id != devops_id:
        await update.message.reply_text("🔒 Команда доступна только DevOps.")
        return

    await update.message.reply_text("📨 Запуск анализа логов...")
    await send_log_report(context)


# --- Регистрация ---
def register_log_reporter(application):
    """
    Подключает:
    - команду /logreport
    - ежедневный отчёт в 6:00
    """
    application.add_handler(CommandHandler("logreport", log_report_command))
    logger.info("✅ Команда /logreport зарегистрирована (доступ: DevOps)")

    from datetime import time
    application.job_queue.run_daily(
        send_log_report,
        time=time(hour=6, minute=0),
        name="daily_log_report"
    )
    logger.info("✅ Ежедневный отчёт по логам запланирован (6:00)")