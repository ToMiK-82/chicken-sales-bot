# scripts/log_analyzer.py
"""
Анализирует логи бота и отправляет отчёт в Telegram.
Запуск: python scripts/log_analyzer.py
Использует .env для TELEGRAM_TOKEN и DEVOPS_CHAT_ID.
"""

import re
import logging
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Bot
import asyncio

# --- Загрузка переменных окружения ---
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEVOPS_CHAT_ID = os.getenv("DEVOPS_CHAT_ID")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ Не задан TELEGRAM_TOKEN в .env")
if not DEVOPS_CHAT_ID:
    try:
        DEVOPS_CHAT_ID = int(DEVOPS_CHAT_ID)
    except (TypeError, ValueError):
        raise ValueError("❌ DEVOPS_CHAT_ID должен быть целым числом")

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Паттерны для анализа ---
DEBUG_PATTERN = re.compile(r"📝 fallback: '([^']+)' →")  # fallback.py
ERROR_PATTERN = re.compile(r"(ERROR|CRITICAL|❌).*?(?=\s*\n|$)", re.IGNORECASE)
HANDLER_PATTERN = re.compile(r"✅ Обработчик '(.*?)' зарегистрирован")
WARNING_PATTERN = re.compile(r"(WARNING|⚠️)")
FALLBACK_SUGGESTION = re.compile(r"suggest_correction\('([^']+)'\) → '([^']+)'")

def analyze_logs(log_file="bot.log", days_back=1):
    """Анализирует логи за последние N дней."""
    if not os.path.exists(log_file):
        logger.error(f"Файл логов не найден: {log_file}")
        return None

    unknown_messages = []
    errors = []
    warnings = []
    suggestions = []
    handlers = set()
    hourly_activity = Counter()
    users = set()

    # Определяем дату начала анализа
    since_date = datetime.now() - timedelta(days=days_back)

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Парсим дату
            try:
                dt_str = line.split(" - ")[0]
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S,%f")
                except ValueError:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = None

            # Фильтруем по дате
            if dt and dt < since_date:
                continue

            if dt:
                hourly_activity[dt.hour] += 1

            # Поиск необработанных сообщений (из fallback)
            debug_match = DEBUG_PATTERN.search(line)
            if debug_match:
                raw_text = debug_match.group(1)
                cleaned = raw_text.lower()
                unknown_messages.append({"raw": raw_text, "cleaned": cleaned})
                users.add("unknown_user")  # fallback не всегда логирует юзернейм

            # Ошибки
            if ERROR_PATTERN.search(line) and "fallback" not in line.lower():
                errors.append(line)

            # Предупреждения
            if WARNING_PATTERN.search(line):
                warnings.append(line)

            # Предложения коррекции
            suggest_match = FALLBACK_SUGGESTION.search(line)
            if suggest_match:
                suggestions.append({"raw": suggest_match.group(1), "suggest": suggest_match.group(2)})

            # Обработчики
            handler_match = HANDLER_PATTERN.search(line)
            if handler_match:
                handlers.add(handler_match.group(1))

    # Анализ
    cleaned_texts = [msg["cleaned"] for msg in unknown_messages]
    top_unknown = Counter(cleaned_texts).most_common(15)
    top_suggestions = Counter([s["suggest"] for s in suggestions]).most_common(10)

    # Формируем отчёт
    report_text = (
        "📊 <b>ЕЖЕДНЕВНЫЙ ОТЧЁТ ПО ЛОГАМ</b>\n"
        f"📅 За: {since_date.strftime('%d.%m.%Y')}\n\n"
    )

    if users:
        report_text += f"👥 Пользователей активно: <b>{len(users)}</b>\n"
    report_text += f"🧠 Обработчиков: {len(handlers)}\n"
    report_text += f"🔔 Ошибок: <b>{len(errors)}</b>\n"
    report_text += f"⚠️ Предупреждений: {len(warnings)}\n"
    report_text += f"💬 Необработанных вводов: {len(unknown_messages)}\n\n"

    if top_unknown:
        report_text += "<b>🔝 ТОП-10 частых фраз (не по кнопкам):</b>\n"
        for text, count in top_unknown[:10]:
            report_text += f"   • <code>{text}</code> — {count}x\n"
        report_text += "\n"

    if top_suggestions:
        report_text += "<b>🎯 Часто предлагали:</b>\n"
        for sug, count in top_suggestions:
            report_text += f"   • <code>{sug}</code> — {count}x\n"
        report_text += "\n"

    report_text += "<b>📈 Активность по часам:</b>\n"
    active_hours = [f"{h:02d}:00" for h in range(24) if hourly_activity[h] > 0]
    if active_hours:
        report_text += "   " + ", ".join(active_hours) + "\n\n"
    else:
        report_text += "   Нет активности\n\n"

    if errors:
        report_text += f"<b>🚨 Последние ошибки (3):</b>\n"
        for err in errors[-3:]:
            report_text += f"   <code>{err[:80]}...</code>\n"

    # Сохраняем JSON
    report_data = {
        "date": datetime.now().isoformat(),
        "users": len(users),
        "errors": len(errors),
        "warnings": len(warnings),
        "unknown_count": len(unknown_messages),
        "top_unknown": top_unknown,
        "top_suggestions": top_suggestions,
        "hourly_activity": dict(hourly_activity),
        "handlers": list(handlers),
        "last_errors": errors[-5:],
    }

    json_path = "log_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Отчёт сохранён: {json_path}")
    return report_text, json_path


async def send_telegram_report(report_text: str, json_path: str):
    """Отправляет отчёт в Telegram."""
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.send_message(
            chat_id=DEVOPS_CHAT_ID,
            text=report_text,
            parse_mode="HTML"
        )
        await bot.send_document(
            chat_id=DEVOPS_CHAT_ID,
            document=open(json_path, "rb"),
            caption="📄 Полный отчёт в JSON"
        )
        logger.info("📤 Отчёт отправлен в Telegram")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить отчёт: {e}")


def main():
    logger.info("🔍 Запуск анализа логов...")
    result = analyze_logs(LOG_FILE, days_back=1)

    if result:
        report_text, json_path = result
        print(report_text)  # в консоль

        # Асинхронная отправка
        asyncio.run(send_telegram_report(report_text, json_path))
    else:
        logger.warning("Нечего анализировать")


if __name__ == "__main__":
    main()