"""
Админ-панель: команды, проверка прав, выход.
✅ /admin — умное приветствие + запрос пароля
✅ Кнопки: Выход, Справка
✅ Группировка: group=0 — команды, group=1 — кнопки, group=2 — fallback (пароль)
"""

from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import logging

from utils.messaging import safe_reply
from utils.admin_helpers import admin_required, exit_to_admin_menu
from config.buttons import (
    ADMIN_EXIT_BUTTON_TEXT,
    ADMIN_HELP_BUTTON_TEXT,
    get_admin_main_keyboard,
    get_main_keyboard,
)
from .help import admin_help_command, HELP_TEXT

logger = logging.getLogger(__name__)


# === 1. КОМАНДЫ: group=0 ===

@admin_required
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Открывает админ-панель.
    Если пользователь ещё не аутентифицирован — запрашивает пароль.
    После ввода правильного пароля показывает меню.
    """
    if not update or not update.effective_user:
        logger.warning("❌ update или effective_user отсутствует в start_admin")
        return

    user = update.effective_user
    db = context.application.bot_data["db"]
    debug_mode = context.application.bot_data.get("DEBUG", False)
    ADMIN_PASSWORD = context.application.bot_data.get("ADMIN_PASSWORD")

    if context.user_data is None:
        context.user_data = {}

    # Уже авторизован?
    if context.user_data.get("is_admin_authenticated"):
        await safe_reply(
            update,
            context,
            "🔐 <b>Админ-панель</b> | Готов к работе.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        return

    # Пароль не задан — пускаем без проверки
    if not ADMIN_PASSWORD:
        context.user_data["is_admin_authenticated"] = True
        await safe_reply(
            update,
            context,
            "⚠️ Пароль отключён. Доступ разрешён.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        return

    # Запрашиваем пароль
    context.user_data["awaiting_admin_password"] = True
    first_time_key = "admin_first_time"

    if context.user_data.get(first_time_key) is None:
        context.user_data[first_time_key] = False
        env_tag = "🟢 <b>PRODUCTION</b>" if not debug_mode else "🟠 <b>DEBUG MODE</b>"
        welcome_text = (
            f"{env_tag}\n"
            "🔐 <b>Админ-панель</b> ✅\n\n"
            "📌 Для доступа введите пароль:"
        )
    else:
        welcome_text = "🔐 <b>Админ-панель</b>\n\nВведите пароль для входа."

    await safe_reply(update, context, welcome_text, parse_mode="HTML")


async def handle_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод пароля.
    ВАЖНО: работает ТОЛЬКО если awaiting_admin_password == True.
    Не должен мешать другим обработчикам.
    Регистрируется в group=2, чтобы НЕ перехватывать кнопки.
    """
    if not update or not update.effective_user:
        logger.warning("⚠️ Пропуск: update или effective_user отсутствует")
        return

    user_id = update.effective_user.id

    if context.user_data is None:
        context.user_data = {}

    # ❌ Если не ждём пароль — передаём дальше (не блокируем)
    if not context.user_data.get("awaiting_admin_password"):
        return

    if not update.effective_message or not update.effective_message.text:
        return

    text = update.effective_message.text.strip()
    ADMIN_PASSWORD = context.application.bot_data.get("ADMIN_PASSWORD")

    if text == ADMIN_PASSWORD:
        context.user_data["is_admin_authenticated"] = True
        context.user_data["awaiting_admin_password"] = False
        await safe_reply(
            update,
            context,
            "✅ Доступ разрешён.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"🔓 Успешный вход в админку: {user_id}")
    else:
        await safe_reply(update, context, "❌ Неверный пароль. Попробуйте ещё раз.")
        logger.warning(f"🔐 Ошибка входа: {user_id}")


@admin_required
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет админа: /addadmin 123456789"""
    if not update.effective_user:
        return
    user_id = update.effective_user.id

    if not context.args or len(context.args) != 1:
        await safe_reply(
            update,
            context,
            "📌 Использование: <code>/addadmin 123456789</code>",
            parse_mode="HTML"
        )
        return

    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await safe_reply(update, context, "❌ ID должно быть целым числом.")
        return

    if new_admin_id <= 0:
        await safe_reply(update, context, "❌ Некорректный ID.")
        return
    if new_admin_id == context.bot.id:
        await safe_reply(update, context, "❌ Нельзя назначить админом бота.")
        return
    if new_admin_id == user_id:
        await safe_reply(update, context, "⚠️ Вы уже админ.")
        return

    if await context.application.bot_data["db"].is_admin(new_admin_id):
        await safe_reply(update, context, f"✅ Пользователь <code>{new_admin_id}</code> уже админ.", parse_mode="HTML")
        return

    if not await context.application.bot_data["db"].add_admin(new_admin_id, added_by=user_id):
        await safe_reply(update, context, "❌ Ошибка при добавлении в БД.")
        return

    context.application.bot_data["ADMIN_IDS"] = [
        admin[0] for admin in await context.application.bot_data["db"].get_all_admins()
    ]

    logger.info(f"🛠️ Админ {user_id} добавил: {new_admin_id}")

    await safe_reply(
        update,
        context,
        f"✅ Администратор <b>{new_admin_id}</b> добавлен.\n"
        f"👤 Добавил: <code>{user_id}</code>",
        parse_mode="HTML"
    )

    try:
        await context.bot.send_message(
            chat_id=new_admin_id,
            text="🎉 Поздравляем! Вам выданы права администратора.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.debug(f"🔧 Не удалось уведомить {new_admin_id}: {e}")


@admin_required
async def rmadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет админа: /rmadmin 123456789"""
    if not update.effective_user:
        return
    user_id = update.effective_user.id

    if not context.args or len(context.args) != 1:
        await safe_reply(
            update,
            context,
            "📌 Использование: <code>/rmadmin 123456789</code>",
            parse_mode="HTML"
        )
        return

    try:
        remove_id = int(context.args[0])
    except ValueError:
        await safe_reply(update, context, "❌ ID должно быть целым числом.")
        return

    if remove_id == user_id:
        await safe_reply(update, context, "❌ Нельзя удалить себя.")
        return
    if not await context.application.bot_data["db"].is_admin(remove_id):
        await safe_reply(update, context, f"❌ Пользователь <code>{remove_id}</code> не админ.", parse_mode="HTML")
        return

    if not await context.application.bot_data["db"].remove_admin(remove_id):
        await safe_reply(update, context, "❌ Ошибка БД.")
        return

    context.application.bot_data["ADMIN_IDS"] = [
        admin[0] for admin in await context.application.bot_data["db"].get_all_admins()
    ]

    logger.info(f"🛠️ Админ {user_id} удалил: {remove_id}")

    await safe_reply(
        update,
        context,
        f"🗑️ Администратор <b>{remove_id}</b> удалён.",
        parse_mode="HTML"
    )


@admin_required
async def listadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех админов."""
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    logger.info(f"📋 Пользователь {user_id} вызвал /listadmins")

    admins = await context.application.bot_data["db"].get_all_admins()
    if not admins:
        await safe_reply(update, context, "📭 Нет администраторов.")
        return

    lines = ["📋 <b>Список администраторов</b> 🛠️\n"]
    for admin_id, added_by, added_at in admins:
        try:
            dt = datetime.fromisoformat(added_at.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            formatted_time = added_at

        tag = f"<b>{admin_id}</b>" if admin_id == user_id else f"<code>{admin_id}</code>"

        try:
            user_info = await context.bot.get_chat(admin_id)
            name = escape(user_info.full_name)
            if user_info.username:
                user_link = f'<a href="https://t.me/{user_info.username}">{name}</a>'
            else:
                user_link = name
            tag = f"{tag} ({user_link})"
        except Exception as e:
            logger.debug(f"❌ Не удалось получить данные о {admin_id}: {e}")

        lines.append(
            f"👤 {tag}\n"
            f"   ➕ Добавлен: <code>{added_by}</code>\n"
            f"   ⏰ {formatted_time}"
        )

    await safe_reply(update, context, "\n\n".join(lines), parse_mode="HTML")


@admin_required
async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль."""
    if not update.effective_user:
        return
    user = update.effective_user
    text = "👤 <b>Ваш профиль</b>\n\n"
    text += f"📛 <b>Имя:</b> {escape(user.full_name)}\n"
    text += f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
    if user.username:
        text += f"🔗 <b>Username:</b> @{escape(user.username)}\n"

    is_admin = await context.application.bot_data["db"].is_admin(user.id)
    user_type = "🛡️ Администратор" if is_admin else "👤 Клиент"
    text += f"🔖 <b>Тип:</b> {user_type}\n"

    if user.is_premium:
        text += "⭐ <b>Премиум-пользователь</b>\n"

    text += f"💬 <b>Чат:</b> {escape(update.effective_chat.type)}"

    await safe_reply(update, context, text, parse_mode="HTML", disable_cooldown=True)


# === КНОПКИ: group=1 ===

@admin_required
async def handle_admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из панели — очистка состояний."""
    if not update.effective_user:
        return
    if context.user_data is None:
        context.user_data = {}

    admin_keys = {
        'in_admin', 'admin_action', 'issue_step', 'edit_breed', 'cancel_breed',
        'broadcast_text', 'waiting_for_promo_title', 'current_state', 'issue_query',
        'admin_first_time', 'awaiting_admin_password', 'is_admin_authenticated'
    }
    for key in admin_keys:
        context.user_data.pop(key, None)

    await safe_reply(
        update,
        context,
        "🚪 Вы вышли из админ-панели.",
        reply_markup=get_main_keyboard()
    )


@admin_required
async def handle_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по админ-командам."""
    if not update.effective_user:
        return
    await safe_reply(update, context, HELP_TEXT, parse_mode="HTML")


# === РЕГИСТРАЦИЯ ВСЕГО ===
def register_admin_handlers(app: Application):
    """
    Регистрирует все админ-обработчики.
    ВАЖНО: handle_admin_password — в group=2, чтобы НЕ блокировать клиентские кнопки!
    """
    # === Команды: group=0 ===
    app.add_handler(CommandHandler("admin", start_admin), group=0)
    app.add_handler(CommandHandler("adminhelp", admin_help_command), group=0)
    app.add_handler(CommandHandler("me", me_command), group=0)
    app.add_handler(CommandHandler("addadmin", addadmin_command), group=0)
    app.add_handler(CommandHandler("rmadmin", rmadmin_command), group=0)
    app.add_handler(CommandHandler("listadmins", listadmins_command), group=0)

    from .stocks import register_stock_handlers
    register_stock_handlers(app)

    from .broadcast import register_admin_broadcast_handler
    from .promotions import register_admin_promotions_handler
    from .orders import register_admin_orders_handler
    from .export import register_export_handler
    from .health import register_health_handler
    from .stats.yearly import get_yearly_stats_handler

    register_admin_broadcast_handler(app)
    register_admin_promotions_handler(app)
    register_admin_orders_handler(app)
    register_export_handler(app)
    register_health_handler(app)

    yearly_handler = get_yearly_stats_handler()
    if yearly_handler:
        app.add_handler(yearly_handler, group=1)

    from .issue_handler import register_admin_issue_handler
    register_admin_issue_handler(app)

    # === Админ-кнопки: group=1 ===
    app.add_handler(
        MessageHandler(filters.Text([ADMIN_EXIT_BUTTON_TEXT]), handle_admin_exit),
        group=1
    )
    app.add_handler(
        MessageHandler(filters.Text([ADMIN_HELP_BUTTON_TEXT]), handle_admin_help),
        group=1
    )

    # === Обработчик ввода пароля: group=2 — ПОСЛЕ всех клиентских обработчиков ===
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_password),
        group=2  # ← Ключевое изменение: не мешает клиентам
    )

    logger.info("✅ Админ-панель: все команды, диалоги и кнопки зарегистрированы")
