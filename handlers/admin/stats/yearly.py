"""
Модуль: Диалог выбора года → детальная статистика + графики.
✅ Показывает:
   - 🐔 Продажи: только issued
   - 📦 Заказано: active + pending
   - ✅ Подтверждено: active + issued
   - ❌ Отказы: cancelled
   - 👥 Клиенты: кто делал confirmed заказ
✅ График с несколькими трендами
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
    ADMIN_STATS_BUTTON_TEXT,
    BTN_BACK_FULL,
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

        # Формируем одну строку: максимум 3 года + "Назад"
        max_years = 3
        keyboard_row = [KeyboardButton(year) for year in years[:max_years]]
        keyboard_row.append(KeyboardButton(BTN_BACK_FULL))

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


async def show_yearly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = context.user_data.get('selected_year')
    if not year:
        await safe_reply(update, context, "❌ Год не выбран.")
        return ConversationHandler.END

    try:
        # 1. Продажи по породам — только issued
        breed_sales = await get_breed_sales(year)

        # 2. Заказано: active + pending
        ordered = await get_ordered_orders(year)

        # 3. Подтверждено: active + issued
        confirmed = await get_confirmed_orders(year)

        # 4. Отмены
        rejections = await get_rejections(year)

        # 5. Уникальные клиенты (подтверждённые заказы)
        unique_clients = await get_unique_clients(year)

        # 6. Выдано в штуках (issued)
        issued_qty_data = await get_issued_quantity(year)

        # Формируем сообщение
        message = f"📊 <b>Статистика за {escape(year)}</b>\n\n"

        # 🐔 Продажи по породам
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
            message += "🐔 Нет данных о продажах.\n"

        # 📥 Заказано (active + pending)
        if ordered:
            message += "\n<b>📥 Заказано (ожидает подтверждения):</b>\n"
            prev = 0
            for month, cnt in ordered:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> заказов {arrow}\n"
                prev = cnt
        else:
            message += "\n📥 Заказано: нет данных\n"

        # ✅ Подтверждено (active + issued)
        if confirmed:
            message += "\n<b>✅ Подтверждённые заказы:</b>\n"
            prev = 0
            for month, cnt in confirmed:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> заказов {arrow}\n"
                prev = cnt
        else:
            message += "\n✅ Подтверждено: нет данных\n"

        # ❌ Отказы
        if rejections:
            message += "\n<b>❌ Отказы:</b>\n"
            prev = 0
            for month, cnt in rejections:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> заказов {arrow}\n"
                prev = cnt
        else:
            message += "\n❌ Отказы: нет данных\n"

        # 👥 Уникальные клиенты
        if unique_clients:
            message += "\n<b>👥 Уникальные клиенты:</b>\n"
            prev = 0
            for month, cnt in unique_clients:
                diff = cnt - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{cnt}</b> чел. {arrow}\n"
                prev = cnt
        else:
            message += "\n👥 Клиенты: нет данных\n"

        # 🚚 Выдано (в штуках)
        if issued_qty_data:
            message += "\n<b>🚚 Выдано (реальные продажи, шт):</b>\n"
            prev = 0
            for month, qty in issued_qty_data:
                diff = qty - prev
                arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
                month_label = _format_month(month)
                message += f"  • {month_label}: <b>{qty}</b> шт {arrow}\n"
                prev = qty
        else:
            message += "\n🚚 Выдано: нет данных\n"

        # 📈 ИТОГИ
        total_sold = sum(qty for _, _, qty in breed_sales) if breed_sales else 0
        total_confirmed = sum(cnt for _, cnt in confirmed) if confirmed else 0
        total_clients = sum(cnt for _, cnt in unique_clients) if unique_clients else 0

        message += "\n<b>📈 ИТОГИ:</b>\n"
        message += f"• Продано: <b>{total_sold}</b>\n"
        message += f"• Подтверждённых заказов: <b>{total_confirmed}</b>\n"
        if total_clients > 0:
            avg_orders_per_client = total_confirmed / total_clients
            message += f"• Среднее на клиента: <b>{avg_orders_per_client:.1f}</b>\n"

        if len(confirmed) >= 2:
            forecast = predict_next_month(confirmed)
            message += f"• 🔮 Прогноз заказов: <b>{max(0, round(forecast))}</b>\n"
        if total_clients > 1:
            forecast = predict_next_month(unique_clients)
            message += f"• 🔮 Прогноз клиентов: <b>{max(0, round(forecast))}</b>\n"

        await safe_reply(update, context, message, parse_mode="HTML")

        # 📊 Отправляем график
        try:
            buf = await send_charts(
                ordered=ordered,
                confirmed=confirmed,
                issued_qty=issued_qty_data,
                rejections=rejections,
                unique_clients=unique_clients,
                year=year
            )
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
    """Продажи по породам: только issued"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), breed, SUM(quantity)
        FROM orders 
        WHERE status = 'issued' AND strftime('%Y', date) = ?
        GROUP BY 1, 2
        ORDER BY 1
    """, (year,))


async def get_ordered_orders(year: str):
    """Заказано: active + pending"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(*)
        FROM orders 
        WHERE status IN ('active', 'pending') AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_confirmed_orders(year: str):
    """Подтверждённые: active + issued"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(*)
        FROM orders 
        WHERE status IN ('active', 'issued') AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_rejections(year: str):
    """Отмены"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(*)
        FROM orders 
        WHERE status = 'cancelled' AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_unique_clients(year: str):
    """Уникальные клиенты: кто делал подтверждённые заказы"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), COUNT(DISTINCT phone)
        FROM orders 
        WHERE status IN ('active', 'issued') AND strftime('%Y', date) = ?
        GROUP BY 1
        ORDER BY 1
    """, (year,))


async def get_issued_quantity(year: str):
    """Суммарное количество выданных цыплят по месяцам"""
    return await db.execute_read("""
        SELECT strftime('%Y-%m', date), SUM(quantity)
        FROM orders 
        WHERE status = 'issued' AND strftime('%Y', date) = ?
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
                filters.ChatType.PRIVATE & filters.Text([ADMIN_STATS_BUTTON_TEXT]),
                handle_yearly_stats
            )
        ],
        states={
            SELECT_YEAR: [
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
