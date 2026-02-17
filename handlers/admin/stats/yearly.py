"""
Модуль: Диалог выбора года → детальная статистика + графики.
Использует утилиты из charts.py.
✅ Точные кнопки — без clean_button_text
✅ Обработка команд и выхода
✅ Работает с group=2
✅ Использует единые константы из config/buttons.py
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from database.repository import db
from config.buttons import (
    # --- FULL-кнопки ---
    ADMIN_STATS_BUTTON_TEXT,  # ← псевдоним, но указывает на то же значение
    BTN_BACK_FULL,            # ← обычно = BTN_BACK
    # --- Клавиатуры ---
    get_admin_main_keyboard,
)
from states import SELECT_YEAR
from utils.admin_helpers import check_admin
from .charts import send_charts, predict_next_month, _format_month
from utils.messaging import safe_reply
from html import escape
import logging

logger = logging.getLogger(__name__)


async def handle_yearly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Точка входа: открывает меню выбора года.
    Проверяет права администратора.
    """
    if not await check_admin(update, context):
        await safe_reply(update, context, "❌ У вас нет доступа к статистике.")
        return ConversationHandler.END

    try:
        years_rows = await db.execute_read(
            "SELECT DISTINCT strftime('%Y', date) FROM orders WHERE date IS NOT NULL ORDER BY 1 DESC"
        )
        years = [row[0] for row in years_rows if row[0]]
        if not years:
            await safe_reply(
                update,
                context,
                "📅 Нет данных о заказах.",
                reply_markup=get_admin_main_keyboard()
            )
            return ConversationHandler.END

        # ✅ Формируем одну строку: максимум 3 года + "Назад"
        max_years = 3
        keyboard_row = []

        for year in years[:max_years]:
            keyboard_row.append(KeyboardButton(year))

        keyboard_row.append(KeyboardButton(BTN_BACK_FULL))  # ← в той же строке

        reply_markup = ReplyKeyboardMarkup([keyboard_row], resize_keyboard=True)

        await safe_reply(
            update,
            context,
            "📆 Выберите год для анализа:",
            reply_markup=reply_markup
        )
        return SELECT_YEAR

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке списка лет: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "❌ Не удалось загрузить данные.",
            reply_markup=get_admin_main_keyboard()
        )
        return ConversationHandler.END


async def select_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "🚪 Просмотр статистики отменён.",
            reply_markup=get_admin_main_keyboard()
        )
        return ConversationHandler.END

    if not text.isdigit() or len(text) != 4 or int(text) < 2000 or int(text) > 2100:
        # ✅ Улучшена клавиатура: только "Назад"
        reply_markup = ReplyKeyboardMarkup([[BTN_BACK_FULL]], resize_keyboard=True)
        await safe_reply(
            update,
            context,
            "❌ Введите корректный год (например, 2024).",
            reply_markup=reply_markup
        )
        return SELECT_YEAR

    context.user_data['selected_year'] = text
    await safe_reply(update, context, "⏳ Генерация отчёта...")
    return await show_yearly_stats(update, context)


# === show_yearly_stats, get_*, fallbacks — остаются без изменений ===
# (они и так хороши)
async def show_yearly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = context.user_data.get('selected_year')
    if not year:
        await safe_reply(update, context, "❌ Год не выбран.")
        return ConversationHandler.END

    try:
        breed_sales = await get_breed_sales(year)
        total_orders = await get_total_orders(year)
        rejections = await get_rejections(year)
        unique_clients = await get_unique_clients(year)

        message = f"📊 <b>Статистика за {escape(year)}</b>\n\n"

        if breed_sales:
            message += "<b>🐔 Продажи по породам:</b>\n"
            current_month = None
            for month, breed, qty in breed_sales:
                month_label = _format_month(month)
                if month != current_month:
                    message += f"\n🗓️ <b>{escape(month_label)}</b>:\n"
                    current_month = month
                message += f"  • {escape(breed)}: <b>{qty}</b> шт.\n"
        else:
            message += "🐔 Нет данных о продажах по породам.\n"

        if total_orders:
            message += "\n<b>📦 Общие заказы:</b>\n"
            prev = 0
            for month, cnt in total_orders:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> {arrow}\n"
                prev = cnt
        else:
            message += "\n📦 Заказы: нет данных\n"

        if rejections:
            message += "\n<b>❌ Отказы:</b>\n"
            prev = 0
            for month, cnt in rejections:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> {arrow}\n"
                prev = cnt
        else:
            message += "\n❌ Отказы: нет данных\n"

        if unique_clients:
            message += "\n<b>👥 Уникальные клиенты:</b>\n"
            prev = 0
            for month, cnt in unique_clients:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> {arrow}\n"
                prev = cnt
        else:
            message += "\n👥 Клиенты: нет данных\n"

        total_qty = sum(qty for _, _, qty in breed_sales) if breed_sales else 0
        total_orders_count = sum(cnt for _, cnt in total_orders) if total_orders else 0
        total_clients = sum(cnt for _, cnt in unique_clients) if unique_clients else 0

        message += "\n<b>📈 ИТОГИ:</b>\n"
        message += f"• Продано кур: <b>{total_qty}</b>\n"
        message += f"• Всего заказов: <b>{total_orders_count}</b>\n"
        if total_clients > 0:
            avg_orders_per_client = total_orders_count / total_clients
            message += f"• Среднее на клиента: <b>{avg_orders_per_client:.1f}</b>\n"

        if len(total_orders) >= 2:
            forecast = predict_next_month(total_orders)
            message += f"• 🔮 Прогноз заказов: <b>{max(0, round(forecast))}</b>\n"
        if total_clients > 1:
            forecast = predict_next_month(unique_clients)
            message += f"• 🔮 Прогноз клиентов: <b>{max(0, round(forecast))}</b>\n"

        await safe_reply(update, context, message, parse_mode="HTML")

        try:
            buf = await send_charts(breed_sales, total_orders, rejections, unique_clients, year)
            if buf:
                await update.message.reply_photo(photo=buf, caption="📈 Динамика за год")
                buf.close()
            else:
                await safe_reply(update, context, "📉 График не построен — недостаточно данных.")
        except Exception as e:
            logger.error(f"❌ Ошибка при построении графика: {e}", exc_info=True)
            await safe_reply(update, context, "⚠️ Не удалось построить график.")

        await safe_reply(
            update,
            context,
            "✅ Просмотр статистики завершён.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при генерации статистики: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "❌ Произошла ошибка при создании отчёта.",
            reply_markup=get_admin_main_keyboard()
        )

    context.user_data.pop('selected_year', None)
    return ConversationHandler.END


# === Запросы ===
async def get_breed_sales(year: str):
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), breed, SUM(quantity)
        FROM orders 
        WHERE status = 'active' AND strftime('%Y', date) = ?
        GROUP BY 1, 2
        ORDER BY 1
    """, (year,))


async def get_total_orders(year: str):
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(*)
        FROM orders 
        WHERE status = 'active' AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_rejections(year: str):
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(*)
        FROM orders 
        WHERE status = 'cancelled' AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_unique_clients(year: str):
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(DISTINCT phone)
        FROM orders 
        WHERE strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


# === Fallback: выход ===
async def fallback_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(
        update,
        context,
        "🚪 Просмотр статистики отменён.",
        reply_markup=get_admin_main_keyboard()
    )
    context.user_data.pop('selected_year', None)
    return ConversationHandler.END


# === Fallback: некорректный ввод ===
async def invalid_year_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    logger.warning(f"📊 invalid_year_input: invalid input '{text}'")
    await safe_reply(
        update,
        context,
        "📌 Введите год в формате <code>2024</code> или нажмите «Назад».",
        reply_markup=ReplyKeyboardMarkup([[BTN_BACK_FULL]], resize_keyboard=True),
        parse_mode="HTML"
    )
    return SELECT_YEAR


# === Регистрация обработчика ===
def get_yearly_stats_handler():
    """Возвращает ConversationHandler"""
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Text([ADMIN_STATS_BUTTON_TEXT]),  # ✅ Работает, если кнопка в интерфейсе
                handle_yearly_stats
            )
        ],
        states={
            SELECT_YEAR: [
                # ✅ Сначала проверяем "Назад", чтобы не попасть в select_year
                MessageHandler(filters.Text([BTN_BACK_FULL]), fallback_to_main),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_year),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, fallback_to_main),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_yearly_stats"
    )


def register_yearly_stats_handler(application):
    """Регистрирует обработчик в group=2"""
    handler = get_yearly_stats_handler()
    application.add_handler(handler, group=2)
    logger.info("✅ Обработчик 'Годовая статистика' зарегистрирован (group=2)")