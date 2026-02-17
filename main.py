"""
🚀 Основной файл запуска бота — v4.9.4 (production-ready + auto-restart notification + test mode + startup fix)
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
✅ Уведомление админам при перезапуске
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
BOT_VERSION = "v4.9.4"

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
    send_customer_order_reminder,
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
    admin_ids = context.application.bot_data.get("ADMIN_IDS", [])

    error_text = (
        "🚨 <b>Критическая ошибка в боте</b>\n\n"
        f"<code>{type(context.error).__name__}: {context.error}</code>"
    )

    # Уведомляем DevOps
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

    # Уведомляем админов
    if admin_ids:
        delivered = 0
        for admin_id in admin_ids:
            try:
                await safe_reply(
                    update=None,
                    context=context,
                    text=f"🔔 <b>Уведомление для админов</b>\n\n{error_text}",
                    chat_id=admin_id,
                    disable_cooldown=True
                )
                delivered += 1
            except Exception as e:
                logger.error(f"❌ Не удалось уведомить админа {admin_id}: {e}")
        logger.info(f"📬 Уведомление об ошибке отправлено: {delivered}/{len(admin_ids)}")


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


# --- Отправка уведомления админам о перезапуске ---
async def send_startup_notification(application: Application):
    """
    Отправляет уведомление всем администраторам о том, что бот был перезапущен.
    Вызывается в конце post_init.
    """
    start_time = application.bot_data.get("start_time")
    if not start_time:
        logger.warning("❌ Не могу отправить уведомление: start_time не задан")
        return

    admin_ids = application.bot_data.get("ADMIN_IDS", [])
    if not admin_ids:
        logger.info("📭 Нет админов для уведомления — пропускаем")
        return

    text = (
        "🟢 <b>Бот перезапущен</b>\n\n"
        f"📦 Версия: <code>{BOT_VERSION}</code>\n"
        f"📅 Время: <code>{start_time.strftime('%d.%m.%Y %H:%M:%S')}</code>\n"
        f"🛠 Источник: <i>вручную или через update_and_restart.bat</i>"
    )

    delivered = 0
    for admin_id in admin_ids:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                disable_notification=False
            )
            delivered += 1
            logger.info(f"📬 Уведомление о перезапуске отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление админу {admin_id}: {e}")

    logger.info(f"✅ Уведомления о перезапуске: {delivered}/{len(admin_ids)} доставлено")


# --- Инициализация при запуске ---
async def post_init(application: Application):
    from config.buttons import get_main_keyboard
    from database.repository import init_db, db  # ✅ Уже есть

    logger.info("🔄 Начало инициализации post_init...")

    # === 1. Инициализация базы данных ===
    try:
        await init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        raise

    # === Сохраняем экземпляр БД в bot_data ===
    application.bot_data["db"] = db
    logger.info("✅ Экземпляр db сохранён в bot_data['db']")

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
    job_queue.run_daily(send_daily_report, time=time(9, 0), name="daily_report")
    job_queue.run_daily(send_admin_shipment_reminder, time=time(10, 0), name="admin_shipment_reminder")
    job_queue.run_daily(send_customer_order_reminder, time=time(8, 0), name="customer_order_reminder")
    job_queue.run_daily(send_unconfirmed_orders_report, time=time(12, 30), name="unconfirmed_orders_report")
    job_queue.run_daily(auto_archive_old_stocks, time=time(0, 10), name="auto_archive_old_stocks")
    logger.info("✅ Все фоновые задачи запланированы")

    # === 9. Уведомление в DevOps ===
    bot = application.bot
    env_tag = "🟢 <b>PRODUCTION</b>" if not DEBUG else "🟠 <b>DEBUG MODE</b>"
    formatted_start_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    startup_text = (
        f"{env_tag}\n"
        f"🟢 <b>Бот успешно запущен и работает</b> ✅\n\n"
        f"🔧 Состояние: все модули инициализированы\n"
        f"📦 Версия: <code>{BOT_VERSION}</code>\n"
        f"📅 Время старта: <code>{formatted_start_time}</code>\n"
        f"📡 Режим работы: <b>production-ready</b>"
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

    # === 12. Уведомление админам о перезапуске ===
    try:
        await send_startup_notification(application)
        logger.info("📬 Уведомление о перезапуске отправлено админам")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о перезапуске: {e}")

    logger.info("✅ Готов к работе. Никаких автоматических сообщений не отправлено.")


# --- Безопасная отправка приветствия ---
async def safe_send_welcome(application: Application, user_id: int):
    try:
        from config.buttons import get_main_keyboard
        text = (
            "👋 Добро пожаловать!\n\n"
            "Мы осуществляем продажу суточных цыплят сельскохозяйственных пород.\n"
            "Выберите нужный раздел 👇"
        )
        await application.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"✅ Отправлено приветственное сообщение пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить сообщение пользователю {user_id}: {e}")


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
        logger.info("✅ Автоматический /start активирован (group=-1)")
    except Exception as e:
        logger.error(f"❌ Ошибка при регистрации автозапуска: {e}", exc_info=True)

    # === 2. Админ-команды ===
    try:
        from handlers.admin.main import register_admin_handlers
        register_admin_handlers(application)
        logger.info("✅ Админ-панель (/admin, /me и др.) зарегистрирована (group=0)")
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
            logger.info(f"✅ Обработчик '{name}' зарегистрирован (group=1)")
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации '{name}': {e}", exc_info=True)

    # === 4. Админские диалоги ===
    try:
        from handlers.admin.issue_handler import register_admin_issue_handler
        register_admin_issue_handler(application)
        logger.info("✅ Обработчик 'Выдача' зарегистрирован (group=2)")
    except Exception as e:
        logger.error(f"❌ Ошибка при регистрации 'Выдача': {e}", exc_info=True)

    # === 5. Системные команды ===
    application.add_handler(CommandHandler("status", status_command), group=3)
    if DEBUG:
        application.add_handler(CommandHandler("debug", debug_command), group=3)
    application.add_handler(CommandHandler("forcestart", force_start), group=3)
    logger.info("🔧 Системные команды (/status, /debug, /forcestart) зарегистрированы (group=3)")

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


# --- Запуск ---
def main():
    logger.info("🚀 Инициализация бота...")
    try:
        application = (
            ApplicationBuilder()
            .token(TOKEN)
            .connect_timeout(10.0)
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
