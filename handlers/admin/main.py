"""
Админ-панель: команды, проверка прав, выход.
✅ /admin — умное приветствие + запрос пароля
✅ Кнопки: Выход, Справка
✅ Группировка: group=0 — команды, group=1 — кнопки, group=2 — fallback (пароль)
✅ Список команд при входе
✅ Удаление сообщения с паролем — безопасность
✅ /trust +79123456789 123456789 — помечает номер как доверенный для пользователя
✅ /untrust +79123456789 — удаляет доверенный статус
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
    Если пользователь уже авторизован — показывает меню и список команд.
    Иначе — запрашивает пароль.
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
        commands_text = (
            "📌 <b>Добро пожаловать!</b>\n\n"
            "📋 Воспользуйтесь меню ниже или командами:\n\n"
            "📘 <code>/adminhelp</code> — подробная справка\n"
            "🛠️ <code>/me</code> — ваш профиль\n"
            "🔧 <code>/status</code> — состояние\n"
            "📊 <code>/stats</code> — статистика\n"
            "📤 <code>/export</code> — выгрузка заказов\n"
            "📦 <code>/backup</code> — резервная копия\n"
            "🔍 <code>/checkstocks</code> — проверить партии\n"
            "🧩 <code>/debug</code> — отладка (вкл: <b>" + ("✅" if debug_mode else "❌") + "</b>)\n"
            "📝 <code>/listadmins</code> — все админы\n"
            "🛠️ <code>/addadmin ID</code> — добавить\n"
            "🗑️ <code>/rmadmin ID</code> — удалить\n"
            "🔐 <code>/trust НОМЕР USER_ID</code> — доверить номер клиенту\n"
            "🔓 <code>/untrust НОМЕР</code> — снять доверие"
        )

        welcome_text = (
            f"🔐 <b>Админ-панель</b> | Готов к работе ✅\n\n"
            f"{commands_text}"
        )

        await safe_reply(
            update, context,
            welcome_text,
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    # Пароль не задан — пускаем без проверки
    if not ADMIN_PASSWORD:
        context.user_data["is_admin_authenticated"] = True

        commands_text = (
            "📌 <b>Добро пожаловать!</b>\n\n"
            "📋 Воспользуйтесь меню ниже или командами:\n\n"
            "📘 <code>/adminhelp</code> — подробная справка\n"
            "🛠️ <code>/me</code> — ваш профиль\n"
            "🔧 <code>/status</code> — состояние\n"
            "📊 <code>/stats</code> — статистика\n"
            "📤 <code>/export</code> — выгрузка заказов\n"
            "📦 <code>/backup</code> — резервная копия\n"
            "🔍 <code>/checkstocks</code> — проверить партии\n"
            "🧩 <code>/debug</code> — отладка (вкл: <b>" + ("✅" if debug_mode else "❌") + "</b>)\n"
            "📝 <code>/listadmins</code> — все админы\n"
            "🛠️ <code>/addadmin ID</code> — добавить\n"
            "🗑️ <code>/rmadmin ID</code> — удалить\n"
            "🔐 <code>/trust НОМЕР USER_ID</code> — доверить номер клиенту\n"
            "🔓 <code>/untrust НОМЕР</code> — снять доверие"
        )

        welcome_text = (
            f"⚠️ Пароль отключён. Доступ разрешён.\n\n"
            f"🔐 <b>Админ-панель</b> | Готов к работе ✅\n\n"
            f"{commands_text}"
        )

        await safe_reply(
            update, context,
            welcome_text,
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
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

    # 🔽 ВАЖНО: УБИРАЕМ КЛАВИАТУРУ, ЧТОБЫ НЕЛЬЗЯ БЫЛО НАЖАТЬ КНОПКИ
    await safe_reply(
        update, context,
        welcome_text,
        parse_mode="HTML",
        reply_markup=None  # ← скрываем клавиатуру
    )


@admin_required
async def handle_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод пароля.
    ❌ Если не ждём пароль — передаёт дальше.
    ✅ Удаляет сообщение с паролем — безопасность.
    ✅ При ошибке — возврат в клиентское меню.
    """
    if not update or not update.effective_user:
        logger.warning("⚠️ Пропуск: update или effective_user отсутствует")
        return

    user_id = update.effective_user.id
    message = update.effective_message

    if context.user_data is None:
        context.user_data = {}

    # ❌ Если не ждём пароль — передаём дальше
    if not context.user_data.get("awaiting_admin_password"):
        return

    if not message or not message.text:
        return

    text = message.text.strip()
    ADMIN_PASSWORD = context.application.bot_data.get("ADMIN_PASSWORD")
    debug_mode = context.application.bot_data.get("DEBUG", False)

    try:
        # 🔐 Удаляем сообщение с паролем
        await message.delete()
        logger.debug(f"🗑️ Сообщение с паролем удалено: {user_id}")
    except Exception as e:
        logger.warning(f"🔧 Не удалось удалить сообщение с паролем: {e}")

    if text == ADMIN_PASSWORD:
        # ✅ Успешный вход
        context.user_data["is_admin_authenticated"] = True
        context.user_data["awaiting_admin_password"] = False
        context.user_data.pop("admin_first_time", None)

        commands_text = (
            "📌 <b>Добро пожаловать!</b>\n\n"
            "📋 Воспользуйтесь меню ниже или командами:\n\n"
            "📘 <code>/adminhelp</code> — подробная справка\n"
            "🛠️ <code>/me</code> — ваш профиль\n"
            "🔧 <code>/status</code> — состояние\n"
            "📊 <code>/stats</code> — статистика\n"
            "📤 <code>/export</code> — выгрузка заказов\n"
            "📦 <code>/backup</code> — резервная копия\n"
            "🔍 <code>/checkstocks</code> — проверить партии\n"
            "🧩 <code>/debug</code> — отладка (вкл: <b>" + ("✅" if debug_mode else "❌") + "</b>)\n"
            "📝 <code>/listadmins</code> — все админы\n"
            "🛠️ <code>/addadmin ID</code> — добавить\n"
            "🗑️ <code>/rmadmin ID</code> — удалить\n"
            "🔐 <code>/trust НОМЕР USER_ID</code> — доверить номер клиенту\n"
            "🔓 <code>/untrust НОМЕР</code> — снять доверие"
        )

        welcome_text = (
            f"✅ Доступ разрешён.\n\n"
            f"🔐 <b>Админ-панель</b> | Готов к работе ✅\n\n"
            f"{commands_text}"
        )

        await safe_reply(
            update, context,
            welcome_text,
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        logger.info(f"🔓 Успешный вход в админку: {user_id}")

    else:
        # ❌ Ошибка — очищаем состояние и возвращаем в клиентку
        context.user_data.pop("awaiting_admin_password", None)
        context.user_data.pop("admin_first_time", None)

        logger.warning(f"🔐 Ошибка входа: {user_id}")

        # 🏠 Возвращаем в главное меню
        await safe_reply(
            update, context,
            "❌ Неверный пароль. Доступ отклонён.\n\n"
            "🏠 Вы возвращены в главное меню.",
            reply_markup=get_main_keyboard()  # ← клиентская клавиатура
        )


# === ОСТАЛЬНЫЕ КОМАНДЫ — БЕЗ ИЗМЕНЕНИЙ ===
@admin_required
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет админа: /addadmin 123456789"""
    if not update.effective_user:
        return
    user_id = update.effective_user.id

    if not context.args or len(context.args) != 1:
        await safe_reply(
            update, context,
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
        await safe_reply(
            update, context,
            f"✅ Пользователь <code>{new_admin_id}</code> уже админ.",
            parse_mode="HTML"
        )
        return

    if not await context.application.bot_data["db"].add_admin(new_admin_id, added_by=user_id):
        await safe_reply(update, context, "❌ Ошибка при добавлении в БД.")
        return

    # Обновляем список админов
    context.application.bot_data["ADMIN_IDS"] = [
        admin[0] for admin in await context.application.bot_data["db"].get_all_admins()
    ]

    logger.info(f"🛠️ Админ {user_id} добавил: {new_admin_id}")

    await safe_reply(
        update, context,
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
            update, context,
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
        await safe_reply(
            update, context,
            f"❌ Пользователь <code>{remove_id}</code> не админ.",
            parse_mode="HTML"
        )
        return

    if not await context.application.bot_data["db"].remove_admin(remove_id):
        await safe_reply(update, context, "❌ Ошибка БД.")
        return

    # Обновляем список админов
    context.application.bot_data["ADMIN_IDS"] = [
        admin[0] for admin in await context.application.bot_data["db"].get_all_admins()
    ]

    logger.info(f"🛠️ Админ {user_id} удалил: {remove_id}")

    await safe_reply(
        update, context,
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
            f" ➕ Добавлен: <code>{added_by}</code>\n"
            f" ⏰ {formatted_time}"
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


# === НОВАЯ КОМАНДА: /checkstocks ===
@admin_required
async def checkstocks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔍 Ручная проверка всех партий: сверяет available_quantity с реальными заказами.
    Показывает расхождения.
    """
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    db = context.application.bot_data.get("db")
    if not db:
        await safe_reply(update, context, "❌ База данных недоступна.")
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
            await safe_reply(update, context, "📭 Нет активных партий.")
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
        await safe_reply(update, context, "❌ Ошибка при проверке данных.")


# === НОВАЯ КОМАНДА: /trust ===
@admin_required
async def trust_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Помечает номер телефона как доверенный для указанного пользователя.
    Это даёт клиенту возможность войти по номеру и оформлять крупные заказы.

    Использование: /trust <номер> <user_id>
    Пример: /trust +79123456789 123456789

    ⚠️ Только для реальных клиентов. Нельзя делать доверенным номер администратора.
    """
    if not update.effective_user:
        return

    admin_id = update.effective_user.id
    db = context.application.bot_data["db"]

    if not context.args or len(context.args) != 2:
        await safe_reply(
            update, context,
            "📌 Использование:\n"
            "<code>/trust &lt;номер&gt; &lt;user_id&gt;</code>\n\n"
            "Пример:\n"
            "<code>/trust +79123456789 123456789</code>",
            parse_mode="HTML"
        )
        return

    phone = context.args[0].strip()
    try:
        target_user_id = int(context.args[1])
    except ValueError:
        await safe_reply(update, context, "❌ user_id должен быть числом")
        return

    # Проверяем, существует ли пользователь
    user_row = await db.execute_read("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,))
    if not user_row:
        await safe_reply(update, context, f"❌ Пользователь с ID <b>{target_user_id}</b> не найден", parse_mode="HTML")
        return

    # Запрещаем делать доверенным номер админа
    if await db.is_admin(target_user_id):
        await safe_reply(update, context, "❌ Нельзя сделать доверенным номер администратора")
        return

    # Помечаем номер как доверенный
    try:
        await db.mark_phone_as_trusted(phone=phone, admin_id=admin_id, user_id=target_user_id)
        logger.info(f"🔐 Админ {admin_id} пометил номер {phone} как доверенный для {target_user_id}")
        await safe_reply(
            update, context,
            f"✅ Номер <code>{escape(phone)}</code> помечен как доверенный для пользователя <b>{target_user_id}</b>.\n\n"
            "Теперь клиент сможет войти по этому номеру и получить полный доступ.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при доверии номера {phone} для {target_user_id}: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Ошибка при сохранении")


# === НОВАЯ КОМАНДА: /untrust ===
@admin_required
async def untrust_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет доверенный статус у номера телефона.
    Клиент больше не сможет использовать этот номер для входа.

    Использование: /untrust <номер>
    Пример: /untrust +79123456789
    """
    if not update.effective_user:
        return

    admin_id = update.effective_user.id
    db = context.application.bot_data["db"]

    if not context.args or len(context.args) != 1:
        await safe_reply(update, context, "📌 Использование: <code>/untrust &lt;номер&gt;</code>", parse_mode="HTML")
        return

    phone = context.args[0].strip()

    try:
        await db.unmark_trusted_phone(phone)
        logger.info(f"🔓 Админ {admin_id} удалил доверенный статус у номера {phone}")
        await safe_reply(
            update, context,
            f"📞 Номер <code>{escape(phone)}</code> больше не доверенный.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении доверенного номера {phone}: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Ошибка при удалении")


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
        update, context,
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
    app.add_handler(CommandHandler("checkstocks", checkstocks_command), group=0)
    app.add_handler(CommandHandler("trust", trust_command), group=0)
    app.add_handler(CommandHandler("untrust", untrust_command), group=0)

    # Подключаем другие модули
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
        group=2
    )

    logger.info("✅ Админ-панель: все команды, диалоги и кнопки зарегистрированы")
