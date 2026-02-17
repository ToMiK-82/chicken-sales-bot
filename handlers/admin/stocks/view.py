"""
Обработчик просмотра остатков.
✅ Поддержка: поиск <запрос>
✅ Кнопка 'Назад' — возвращает в меню
✅ Редактирование через 'Изменить' (через ConversationHandler)
✅ Нет дублирования сообщений
✅ Группа: group=2
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from config.buttons import (
    get_admin_main_keyboard,
    get_stock_action_keyboard,
    ADMIN_STOCKS_BUTTON_TEXT,
    BTN_BACK_FULL,
    SEPARATOR,
)
from database.repository import db
from utils.messaging import safe_reply, log_action
from utils.admin_helpers import check_admin, exit_to_admin_menu
from html import escape
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# === Состояния ===
VIEW_STOCKS = 0

# === Ключи для очистки ===
STOCK_VIEW_KEYS = [
    "current_conversation",
    "HANDLED",
]


def _format_date(date_str: str) -> str:
    if not date_str:
        return "Не указана"
    try:
        clean_date = date_str.split()[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return date_str


# === Поиск партий ===
async def _search_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    search_query = f"%{query}%"
    try:
        stocks = await db.execute_read(
            """
            SELECT breed, incubator, date, quantity, available_quantity, price
            FROM stocks
            WHERE quantity > 0
              AND (breed LIKE ? OR incubator LIKE ? OR date LIKE ?)
            ORDER BY date
            """,
            (search_query, search_query, search_query)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при поиске: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Ошибка при поиске партий.")

    if not stocks:
        return await exit_to_admin_menu(update, context, f"🔍 Ничего не найдено: <b>{escape(query)}</b>")

    message = f"🔍 <b>Результаты по «{escape(query)}»:</b>\n\n"
    for stock in stocks:
        breed, incubator, date, qty, avail, price = stock
        qty_int = int(qty or 0)
        if qty_int <= 0:
            continue
        try:
            price_int = int(float(price or 0))
        except (TypeError, ValueError):
            price_int = 0

        delivery_date = _format_date(date)
        breed_safe = escape(breed)
        incubator_safe = escape(incubator) if incubator else "Не указан"

        message += (
            f"🐔 <b>Порода:</b> {breed_safe}\n"
            f"🏢 <b>Инкубатор:</b> {incubator_safe}\n"
            f"📦 <b>Начально:</b> {qty_int} шт.\n"
            f"📅 <b>Поставка:</b> {delivery_date}\n"
            f"🟢 <b>Доступно:</b> {int(avail or 0)} шт.\n"
            f"💰 <b>Цена:</b> {price_int} руб.\n"
            f"{SEPARATOR}"
        )

    await safe_reply(
        update,
        context,
        message.strip(),
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
    )
    context.user_data["HANDLED"] = True
    return ConversationHandler.END


# === Главный экран ===
async def start_stock_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, context):
        return await exit_to_admin_menu(update, context, "❌ У вас нет доступа.")

    text = update.effective_message.text.strip()
    user_id = update.effective_user.id

    logger.info(f"Админ {user_id} запросил 'Остатки'")
    log_action(user_id, "Кнопка", "Остатки")

    if text.lower().startswith("поиск "):
        query = text[6:].strip()
        if not query:
            return await exit_to_admin_menu(update, context, "❌ Укажите слово для поиска.")
        return await _search_stocks(update, context, query)

    try:
        stocks = await db.execute_read(
            "SELECT breed, incubator, date, quantity, available_quantity, price FROM stocks WHERE quantity > 0 ORDER BY date"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке остатков: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Ошибка при загрузке партий.")

    if not stocks:
        return await exit_to_admin_menu(update, context, "📭 Нет активных партий.")

    message = (
        "📦 <b>Текущие остатки:</b>\n\n"
        "🔍 Чтобы найти — введите: <code>поиск &lt;слово&gt;</code>\n\n"
    )
    for stock in stocks:
        breed, incubator, date, qty, avail, price = stock
        qty_int = int(qty or 0)
        if qty_int <= 0:
            continue
        try:
            price_int = int(float(price or 0))
        except (TypeError, ValueError):
            price_int = 0

        delivery_date = _format_date(date)
        breed_safe = escape(breed)
        incubator_safe = escape(incubator) if incubator else "Не указан"

        message += (
            f"🐔 <b>Порода:</b> {breed_safe}\n"
            f"🏢 <b>Инкубатор:</b> {incubator_safe}\n"
            f"📦 <b>Начально:</b> {qty_int} шт.\n"
            f"📅 <b>Поставка:</b> {delivery_date}\n"
            f"🟢 <b>Доступно:</b> {int(avail or 0)} шт.\n"
            f"💰 <b>Цена:</b> {price_int} руб.\n"
            f"{SEPARATOR}"
        )

    await safe_reply(
        update,
        context,
        message.strip(),
        reply_markup=get_stock_action_keyboard(),  # Только "Назад" и "Изменить"
        parse_mode="HTML"
    )
    context.user_data["HANDLED"] = True
    context.user_data["current_conversation"] = "stock_view"

    return VIEW_STOCKS


# === Обработка действий ===
async def handle_stock_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()

    # 🔥 КРИТИЧЕСКАЯ ПРОВЕРКА: если мы не в этом диалоге — выходим
    if context.user_data.get("current_conversation") != "stock_view":
        return

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(
            update,
            context,
            "🚪 Вы вышли из просмотра остатков.",
            keys_to_clear=STOCK_VIEW_KEYS
        )

    if text.lower().startswith("поиск "):
        query = text[6:].strip()
        if not query:
            return await exit_to_admin_menu(update, context, "❌ Укажите слово для поиска.")
        return await _search_stocks(update, context, query)

    # Только если мы всё ещё в состоянии просмотра — показываем подсказку
    await safe_reply(
        update,
        context,
        "📌 Выберите действие ниже или введите: <code>поиск &lt;слово&gt;</code>",
        reply_markup=get_stock_action_keyboard(),
        parse_mode="HTML"
    )
    context.user_data["HANDLED"] = True
    return VIEW_STOCKS


# === Регистрация ===
def register_stock_view_handler(application):
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ADMIN_STOCKS_BUTTON_TEXT]),
                start_stock_view
            ),
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Regex(r"^поиск .+"),
                start_stock_view
            ),
        ],
        states={
            VIEW_STOCKS: [
                MessageHandler(filters.Text([BTN_BACK_FULL]), handle_stock_action),
                # Убрали BTN_EDIT_FULL — пусть edit.py сам ловит
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_action),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, exit_to_admin_menu),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_stock_view",
    )

    application.add_handler(conv_handler, group=2)
    logger.info("✅ Обработчик 'Остатки' зарегистрирован (group=2)")