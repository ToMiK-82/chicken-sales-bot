"""
🚀 Основной файл запуска бота — v4.9.5 (production-ready + test mode + startup fix)
✅ Полная поддержка админ-панели
✅ Группы обработчиков:
   - group=-1 — автозапуск (первым!)
   - group=0  — админ-команды
   - group=1  — клиентские диалоги
   - group=2  — админские диалоги
   - group=3  — системные команды
✅ /start и /back регистрируются ПОСЛЕ инициализации БД
✅ Автоматический запуск при любом первом сообщении/действии — даже до post_init
✅ Кнопка '⬅️ Назад' ведёт в главное меню
✅ Нет избыточного перехвата команд в диалогах
✅ Персистентность отключена: состояние НЕ сохраняется между перезапусками
✅ Совместимо с python-telegram-bot v22.5
✅ Добавлен режим тестирования: python main.py --test
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    Application,
    ContextTypes,
    CommandHandler,
)

# --- 🚀 Версия бота — ЕДИНСТВЕННОЕ место определения ---
BOT_VERSION = "v4.9.5"  # 🔼 Увеличили версию

print("📍 Python executable:", sys.executable)
try:
    import telegram
    print("📍 python-telegram-bot version:", telegram.__version__)
except ImportError as e:
    print("❌ telegram не установлен:", e)
    sys.exit(1)

# 🔍 Дебаг: где Python ищет модули
print("📄 sys.path:", sys.path)

# --- Загрузка переменных окружения ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
DEVOPS_CHAT_ID = os.getenv("DEVOPS_CHAT_ID")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
DROP_PENDING_UPDATES = os.getenv("DROP_PENDING_UPDATES", "False").lower() in ("true", "1", "yes")  # False по умолчанию

if not TOKEN:
    raise ValueError("❌ Не задан TELEGRAM_TOKEN в .env")
if not DEVOPS_CHAT_ID:
    raise ValueError("❌ Не задан DEVOPS_CHAT_ID в .env")
try:
    DEVOPS_CHAT_ID = int(DEVOPS_CHAT_ID)
except ValueError:
    raise ValueError("❌ DEVOPS_CHAT_ID должен быть целым числом")

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG if DEBUG else logging.INFO
)
logger = logging.getLogger(__name__)

if DEBUG:
    logger.info("🔧 Режим DEBUG включён")
else:
    logger.info("🟢 Режим PRODUCTION")

# --- Импорты утилит ---
from utils.messaging import (
    safe_reply,
    send_daily_report,
    send_admin_shipment_reminder,
    send_pending_reminder_2_days,
    send_pending_reminder_1_day,
)
from utils.archive import auto_archive_old_stocks
from utils.reminder_reporter import send_unconfirmed_orders_report


# --- Глобальный обработчик ошибок ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("🚨 Критическая ошибка в боте", exc_info=context.error)

    if not context.bot:
        logger.warning("❌ context.bot отсутствует — не могу отправить уведомление")
        return

    devops_id = context.application.bot_data.get("DEVOPS_CHAT_ID")

    error_text = (
        "🚨 <b>Критическая ошибка в боте</b>\n\n"
        f"<code>{type(context.error).__name__}: {context.error}</code>"
    )

    # Уведомляем только DevOps
    if devops_id:
        try:
            await context.bot.send_message(
                chat_id=devops_id,
                text=f"🛠️ [DEVOPS]\n\n{error_text}",
                parse_mode="HTML",
                disable_notification=False
            )
            logger.info("✉️ Отчёт об ошибке отправлен в DevOps")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить в DevOps: {e}")


# --- Команда /status ---
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = context.application.bot_data.get("start_time")
    uptime = str(datetime.now() - start_time).split(".")[0] if start_time else "Неизвестно"
    db_status = "✅ Подключена"
    text = (
        "🔧 <b>Статус бота</b>\n\n"
        f"🟢 Состояние: <b>Работает</b>\n"
        f"📦 Версия: <code>{BOT_VERSION}</code>\n"
        f"⏱ Аптайм: <code>{uptime}</code>\n"
        f"🗄 База данных: {db_status}\n"
        f"📅 Запущен: <code>{start_time.strftime('%d.%m.%Y %H:%M:%S') if start_time else '—'}</code>"
    )
    await safe_reply(update, context, text, parse_mode="HTML", disable_cooldown=True)


# --- Команда /debug ---
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DEBUG:
        await safe_reply(update, context, "🔒 Режим debug выключен.", disable_cooldown=True)
        return

    user = update.effective_user
    chat = update.effective_chat
    bot_data = context.application.bot_data
    debug_info = (
        "🔍 <b>DEBUG-ИНФОРМАЦИЯ</b>\n\n"
        f"<b>Пользователь:</b> {user.full_name} (@{user.username or 'N/A'}, ID: <code>{user.id}</code>)\n"
        f"<b>Чат:</b> {chat.type} (ID: <code>{chat.id}</code>)\n\n"
        f"<b>user_data:</b>\n<code>{context.user_data}</code>\n\n"
        f"<b>bot_data.keys:</b> {list(bot_data.keys()) if bot_data else '—'}\n"
        f"<b>start_time:</b> {bot_data.get('start_time')}\n"
        f"<b>available_breeds:</b> {len(bot_data.get('available_breeds', []))} пород\n"
        f"<b>DEBUG:</b> {DEBUG}"
    )
    await safe_reply(update, context, debug_info, parse_mode="HTML", disable_cooldown=True)


# --- Временная команда /forcestart ---
async def force_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительный вызов /start — даже если обычный не работает."""
    try:
        from handlers.start import start
        await start(update, context)
        logger.info(f"🔧 /forcestart выполнен пользователем {update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в /forcestart: {e}", exc_info=True)
        await safe_reply(update, context, f"❌ Ошибка: {e}")


# --- Команда /checkstocks ---
async def checkstocks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔍 Ручная проверка всех партий: сверяет available_quantity с реальными заказами.
    Доступно только админам.
    """
    user_id = update.effective_user.id
    admin_ids = context.application.bot_data.get("ADMIN_IDS", [])
    if user_id not in admin_ids:
        await safe_reply(update, context, "🔒 Доступно только администраторам.", disable_cooldown=True)
        return

    db = context.application.bot_data.get("db")
    if not db:
        await safe_reply(update, context, "❌ База данных не инициализирована.", disable_cooldown=True)
        return

    query = """
        SELECT 
            s.id, s.breed, s.incubator, s.date, s.quantity, s.available_quantity,
            COALESCE(SUM(o.quantity), 0) AS total_ordered
        FROM stocks s
        LEFT JOIN orders o ON s.id = o.stock_id AND o.status IN ('pending', 'active')
        WHERE s.status = 'active'
        GROUP BY s.id
        ORDER BY s.date, s.breed
    """
    try:
        rows = await db.execute_read(query)
        if not rows:
            await safe_reply(update, context, "📭 Нет активных партий.", disable_cooldown=True)
            return

        report_lines = ["📋 <b>Состояние партий</b> (сравнение с заказами)\n"]

        for row in rows:
            correct_avail = row['quantity'] - row['total_ordered']
            current_avail = row['available_quantity']
            incubator_text = f" | 🏢 {row['incubator']}" if row['incubator'] else ""
            status = "✅" if current_avail == correct_avail else "❌"

            report_lines.append(
                f"{status} <b>{row['breed']}</b> <code>({row['date']})</code>{incubator_text}\n"
                f"   📦 Всего: {row['quantity']} шт\n"
                f"   🟥 Заказано: {row['total_ordered']} шт\n"
                f"   🟢 Доступно: {current_avail} шт (должно быть: {correct_avail})"
            )

        await safe_reply(
            update, context,
            "\n".join(report_lines),
            parse_mode="HTML",
            disable_cooldown=True
        )
        logger.info(f"🔧 /checkstocks выполнен пользователем {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в /checkstocks: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Произошла ошибка при проверке данных.")


# --- Инициализация при запуске ---
async def post_init(application: Application):
    from config.buttons import get_main_keyboard
    from database.repository import init_db

    logger.info("🔄 Начало инициализации post_init...")

    # === 1. Инициализация базы данных ===
    try:
        db = await init_db()
        application.bot_data["db"] = db
        logger.info("✅ База данных инициализирована и сохранена в bot_data['db']")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        raise

    # === 1.1 Проверка и исправление available_quantity ===
    async def check_and_fix_stock_consistency():
        logger.info("🔍 Проверка согласованности available_quantity по всем партиям...")
        try:
            query = """
                SELECT 
                    s.id,
                    s.quantity,
                    s.available_quantity,
                    COALESCE(SUM(o.quantity), 0) AS total_ordered
                FROM stocks s
                LEFT JOIN orders o ON s.id = o.stock_id AND o.status IN ('pending', 'active')
                WHERE s.status = 'active'
                GROUP BY s.id
            """
            rows = await db.execute_read(query)

            fixes = []
            for row in rows:
                correct_avail = row['quantity'] - row['total_ordered']
                current_avail = row['available_quantity']

                if abs(current_avail - correct_avail) > 0:
                    logger.warning(
                        f"⚠️ Расхождение в stock_id={row['id']}: "
                        f"available={current_avail}, должно быть {correct_avail}"
                    )
                    fixes.append((correct_avail, row['id']))

            if fixes:
                logger.info(f"🔧 Применяем исправления к {len(fixes)} партиям...")
                for avail, stock_id in fixes:
                    success = await db.execute_write(
                        "UPDATE stocks SET available_quantity = ? WHERE id = ?",
                        (avail, stock_id)
                    )
                    if success:
                        logger.info(f"✅ Исправлено: stock_id={stock_id}, available_quantity = {avail}")
                    else:
                        logger.error(f"❌ Не удалось обновить stock_id={stock_id}")

                if DEVOPS_CHAT_ID:
                    fix_report = (
                        "🔧 <b>Автоисправление данных</b>\n"
                        f"📦 Исправлено <b>{len(fixes)}</b> партий\n"
                        "⚙️ Причина: расхождение между available_quantity и реальными заказами.\n"
                        "📅 Это могло произойти из-за сбоя при создании заказов."
                    )
                    try:
                        await application.bot.send_message(
                            chat_id=DEVOPS_CHAT_ID,
                            text=fix_report,
                            parse_mode="HTML"
                        )
                        logger.info("📬 Уведомление об исправлении отправлено в DevOps")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить уведомление об исправлении: {e}")
            else:
                logger.info("🟢 Все значения available_quantity согласованы — исправления не требуются.")

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке согласованности партий: {e}", exc_info=True)

    # Запускаем проверку при старте
    await check_and_fix_stock_consistency()

    # === 2. Создание папки экспорта ===
    os.makedirs("exports", exist_ok=True)
    logger.info("📁 Папка 'exports' создана/проверена")

    # === 3. Загрузка доступных пород ===
    try:
        result = await db.execute_read("""
            SELECT DISTINCT breed
            FROM stocks
            WHERE available_quantity > 0 AND status = 'active'
        """)
        available_breeds = sorted({row[0] for row in result}) if result else []
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пород: {e}")
        available_breeds = []

    # === 4. Инициализация флагов ===
    application.bot_data.setdefault("auto_start_done", {})
    application.bot_data["DEVOPS_CHAT_ID"] = DEVOPS_CHAT_ID
    application.bot_data["BOT_VERSION"] = BOT_VERSION

    # === 5. Удаление устаревших ключей ===
    if "started_users" in application.bot_data:
        old_count = len(application.bot_data["started_users"])
        logger.info(f"🧹 Удалён устаревший started_users: {old_count} пользователей")
        del application.bot_data["started_users"]

    # === 6. Принудительная очистка всех активных диалогов ===
    cleared_handlers = 0
    for group_id, handler_group in application.handlers.items():
        for handler in handler_group:
            if hasattr(handler, 'conversations') and isinstance(handler.conversations, dict):
                if handler.conversations:
                    logger.debug(f"🧹 Очищен словарь диалогов у {getattr(handler, 'name', 'unnamed')} (group={group_id})")
                handler.conversations.clear()
                cleared_handlers += 1
    logger.info(f"✅ Принудительно очищено {cleared_handlers} словарей диалогов")

    # === 7. Регистрация /start и /back ПОСЛЕ инициализации ===
    try:
        from handlers.start import register_start_handler
        register_start_handler(application)
        logger.info("✅ Обработчики /start и /back зарегистрированы (после инициализации)")
    except Exception as e:
        logger.critical(f"🔴 Ошибка регистрации /start: {e}", exc_info=True)
        raise

    # === 8. Планирование фоновых задач ===
    job_queue = application.job_queue

    def schedule_job(job_name: str, callback, job_time: time):
        try:
            existing_jobs = job_queue.jobs()
            existing_names = [job.name for job in existing_jobs]
            if job_name in existing_names:
                logger.debug(f"⚠️ Задача '{job_name}' уже существует — пропущено")
                return
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить существующие задачи: {e}")

        job_queue.run_daily(callback, time=job_time, name=job_name)
        logger.info(f"✅ Задача '{job_name}' запланирована")

    schedule_job("daily_report", send_daily_report, time(9, 0))
    schedule_job("admin_shipment_reminder", send_admin_shipment_reminder, time(10, 0))
    schedule_job("reminder_2_days", send_pending_reminder_2_days, time(8, 0))
    schedule_job("reminder_1_day", send_pending_reminder_1_day, time(8, 0))
    schedule_job("unconfirmed_orders_report", send_unconfirmed_orders_report, time(12, 30))
    schedule_job("auto_archive_old_stocks", auto_archive_old_stocks, time(0, 10))

    # === 8.5 Ежедневная проверка согласованности (автоматически в 01:00) ===
    job_queue.run_daily(
        check_and_fix_stock_consistency,
        time=time(1, 0),
        name="daily_stock_consistency_check"
    )
    logger.info("✅ Задача 'daily_stock_consistency_check' запланирована (ежедневно в 01:00)")

    # === 9. Уведомление в DevOps ===
    bot = application.bot
    mode_emoji = "🟢" if not DEBUG else "🟠"
    mode_text = "PRODUCTION" if not DEBUG else "DEBUG"
    formatted_start_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    startup_text = (
        f"{mode_emoji} <b>Бот успешно запущен</b>\n\n"
        f"📦 Версия: <code>{BOT_VERSION}</code>\n"
        f"📅 Время старта: <code>{formatted_start_time}</code>\n"
        f"🔧 Состояние: все модули инициализированы\n"
        f"⚙️ Режим: <b>{mode_text}</b>"
    )

    try:
        await bot.send_message(
            chat_id=DEVOPS_CHAT_ID,
            text=startup_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logger.info("📬 Стартовое сообщение отправлено в DevOps")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить в DevOps: {e}")

    # === 10. Загрузка админов ===
    try:
        admins = await db.get_all_admins()
        admin_ids = [admin[0] for admin in admins] if admins else []
        application.bot_data["ADMIN_IDS"] = admin_ids
        logger.info(f"✅ ADMIN_IDS сохранён в bot_data: {admin_ids}")
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке админов: {e}")

    # === 11. Несериализуемые данные ===
    application.bot_data["ADMIN_PASSWORD"] = ADMIN_PASSWORD
    application.bot_data["available_breeds"] = available_breeds
    application.bot_data["start_time"] = datetime.now()
    application.bot_data["INITIALIZED"] = True

    logger.info("✅ Готов к работе. Никаких автоматических сообщений не отправлено.")


# --- Завершение работы ---
async def post_shutdown(application: Application):
    try:
        from database.repository import db
        if hasattr(db, "close"):
            await db.close()
        logger.info("✅ Бот остановлен. БД закрыта.")
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии БД: {e}", exc_info=True)


# === Регистрация всех обработчиков ===
def register_handlers(application: Application):
    logger.info("🔧 Регистрация всех обработчиков...")

    # === 1. АВТОЗАПУСК — ДО ВСЕХ ОСТАЛЬНЫХ ОБРАБОТЧИКОВ (group=-1) ===
    try:
        from handlers.startup import register_auto_start_handler
        logger.debug("📌 Регистрация auto_start_handler (должна быть первой!)")
        register_auto_start_handler(application)
        if DEBUG:
            logger.info("✅ Автоматический /start активирован (group=-1)")
        else:
            logger.debug("✅ Автоматический /start активирован")
    except Exception as e:
        logger.error(f"❌ Ошибка при регистрации автозапуска: {e}", exc_info=True)

    # === 2. Админ-команды ===
    try:
        from handlers.admin.main import register_admin_handlers
        register_admin_handlers(application)
        if DEBUG:
            logger.info("✅ Админ-панель (/admin, /me и др.) зарегистрирована (group=0)")
        else:
            logger.debug("✅ Админ-панель зарегистрирована")
    except Exception as e:
        logger.critical(f"🔴 Ошибка при регистрации админ-панели: {e}", exc_info=True)
        raise

    # === 3. Клиентские диалоги ===
    client_modules = [
        ("catalog", "Каталог"),
        ("schedule", "График"),
        ("contacts", "Контакты"),
        ("help", "Справка"),
        ("my_orders", "Мои заказы"),
        ("promotions", "Акции"),
        ("order_confirmation", "Подтверждение заказа"),
    ]
    for module, name in client_modules:
        try:
            handler = getattr(__import__(f"handlers.client.{module}", fromlist=[""]), f"register_{module}_handler")
            handler(application)
            if DEBUG:
                logger.info(f"✅ Обработчик '{name}' зарегистрирован (group=1)")
            else:
                logger.debug(f"✅ Обработчик '{name}' зарегистрирован")
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации '{name}': {e}", exc_info=True)

    # === 4. Админские диалоги ===
    try:
        from handlers.admin.issue_handler import register_admin_issue_handler
        register_admin_issue_handler(application)
        if DEBUG:
            logger.info("✅ Обработчик 'Выдача' зарегистрирован (group=2)")
        else:
            logger.debug("✅ Обработчик 'Выдача' зарегистрирован")
    except Exception as e:
        logger.error(f"❌ Ошибка при регистрации 'Выдача': {e}", exc_info=True)

    # === 5. Системные команды ===
    application.add_handler(CommandHandler("status", status_command), group=3)

    if DEBUG:
        application.add_handler(CommandHandler("debug", debug_command), group=3)
        application.add_handler(CommandHandler("forcestart", force_start), group=3)
        logger.info("🔧 Системные команды (/status, /debug, /forcestart, /checkstocks) зарегистрированы (group=3)")
    else:
        application.add_handler(CommandHandler("forcestart", force_start), group=3)
        logger.debug("🔧 Системные команды зарегистрированы")

    # === 6. Админ-утилиты ===
    try:
        from handlers.admin.stats.daily import register_daily_stats
        register_daily_stats(application)
        logger.info("✅ Команда /stats зарегистрирована")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации /stats: {e}")

    try:
        from handlers.admin.backup import register_backup_handler
        register_backup_handler(application)
        logger.info("✅ Команда /backup зарегистрирована")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации /backup: {e}")

    # ✅ /getib — Получение параметров ИБ из 1С
    try:
        from utils.erp import get_ib_parameters

        async def getib_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            admin_ids = context.application.bot_data.get("ADMIN_IDS", [])
            if user_id not in admin_ids:
                await safe_reply(update, context, "🔒 Доступно только администраторам.", disable_cooldown=True)
                return

            await safe_reply(update, context, "🔍 Запрашиваем параметры информационной базы...", disable_cooldown=True)
            success, result = await get_ib_parameters()
            if success:
                if len(result) > 4096:
                    parts = [result[i:i+4096] for i in range(0, len(result), 4096)]
                    for part in parts:
                        await safe_reply(update, context, f"<pre>{part}</pre>", parse_mode="HTML", disable_cooldown=True)
                else:
                    await safe_reply(update, context, f"<pre>{result}</pre>", parse_mode="HTML", disable_cooldown=True)
            else:
                await safe_reply(update, context, f"❌ Ошибка: {result}", disable_cooldown=True)

        application.add_handler(CommandHandler("getib", getib_command), group=3)
        logger.info("✅ Команда /getib зарегистрирована — для диагностики 1С")
    except Exception as e:
        logger.error(f"❌ Ошибка при регистрации /getib: {e}", exc_info=True)

    # === 7. Отладочная команда /report (только в DEBUG) ===
    async def debug_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔧 Вручную запустить ежедневный отчёт"""
        await send_daily_report(context)
        await update.message.reply_text("📤 Отчёт отправлен в DevOps", disable_notification=True)

    if DEBUG:
        application.add_handler(CommandHandler("report", debug_report), group=3)
        logger.info("🔧 Команда /report доступна (DEBUG)")


# --- Запуск ---
def main():
    logger.info("🚀 Инициализация бота...")
    try:
        application = (
            ApplicationBuilder()
            .token(TOKEN)
            .
connect_timeout(10.0)
            .read_timeout(20.0)
            .write_timeout(20.0)
            .pool_timeout(5.0)
            .post_init(post_init)
            .post_shutdown(post_shutdown)
            .build()
        )

        application.add_error_handler(error_handler)
        register_handlers(application)

        logger.info(f"🟢 Бот запущен в {'DEBUG' if DEBUG else 'PRODUCTION'} режиме.")

        try:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=DROP_PENDING_UPDATES,
                poll_interval=0.5,
            )
        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен пользователем (Ctrl+C)")
        finally:
            logger.info("✅ Работа завершена корректно")

    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)


# === ТЕСТИРОВАНИЕ ===
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("🧪 Запуск тестов...\n")

        try:
            from config.buttons import (
                CATALOG_BUTTON_TEXT, ORDERS_BUTTON_TEXT, SCHEDULE_BUTTON_TEXT,
                BTN_BACK_FULL, BTN_ADMIN_EXIT_FULL, ADMIN_EXIT_BUTTON_TEXT, BREED_BUTTONS
            )
            print("✅ Импорт кнопок: OK")
            print("   Пример: BREED_BUTTONS[0] =", BREED_BUTTONS[0])
        except Exception as e:
            print(f"❌ Ошибка импорта config/buttons.py: {e}")
            sys.exit(1)

        try:
            from handlers.startup import register_auto_start_handler
            print("✅ handlers/startup: OK")
            print("   Функция register_auto_start_handler доступна")
        except Exception as e:
            print(f"❌ Ошибка импорта handlers/startup.py: {e}")
            sys.exit(1)

        try:
            from handlers.start import register_start_handler
            print("✅ handlers/start: OK")
        except Exception as e:
            print(f"❌ Ошибка импорта handlers/start.py: {e}")
            sys.exit(1)

        try:
            from database.repository import init_db
            print("✅ database/repository: OK")
        except Exception as e:
            print(f"❌ Ошибка импорта database/repository.py: {e}")
            sys.exit(1)

        print(f"🔑 TELEGRAM_TOKEN: {'✅ задан' if TOKEN else '❌ не задан'}")
        print(f"📞 DEVOPS_CHAT_ID: {'✅ задан' if DEVOPS_CHAT_ID else '❌ не задан'}")

        print("\n🎉 Все тесты пройдены! Готов к запуску.")
        sys.exit(0)

    # Обычный запуск
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()


__all__ = ["BOT_VERSION", "main"]
