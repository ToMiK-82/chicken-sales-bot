"""
Команда /stats — краткая статистика за день.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
# ✅ Исправлено: используем существующий декоратор
from utils.admin_helpers import admin_required
from database.repository import db
from utils.messaging import safe_reply
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@admin_required  # ✅ Правильный декоратор
async def daily_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        total_orders = await db.execute_read("SELECT COUNT(*) FROM orders")
        total_clients = await db.execute_read("SELECT COUNT(DISTINCT phone) FROM orders")

        new_today = await db.execute_read(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?", (today,)
        )

        new_clients_today = await db.execute_read("""
            SELECT COUNT(*) FROM (
                SELECT phone FROM orders
                WHERE DATE(created_at) = ?
                GROUP BY phone
                HAVING COUNT(*) = 1
            )
        """, (today,))

        revenue_result = await db.execute_read("""
            SELECT SUM(price * quantity)
            FROM orders
            WHERE status IN ('active', 'issued')
        """)
        revenue = int(revenue_result[0][0] or 0)

        active = await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'active'")
        issued = await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'issued'")
        cancelled = await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'")

        def fmt(n): return f"{n:,}".replace(",", " ")

        message = (
            f"📊 <b>Статистика за день</b>\n"
            f"📅 {today}\n\n"

            f"📌 <b>Общее</b>\n"
            f"🧮 Всего заказов: <b>{fmt(total_orders[0][0])}</b>\n"
            f"👥 Всего клиентов: <b>{fmt(total_clients[0][0])}</b>\n\n"

            f"📌 <b>Сегодня</b>\n"
            f"✅ Новых: <b>{new_today[0][0]}</b>\n"
            f"👤 Новых клиентов: <b>{new_clients_today[0][0]}</b>\n"
            f"💰 Оборот: <b>{fmt(revenue)} ₽</b>\n\n"

            f"📌 <b>Статусы</b>\n"
            f"📈 Активные: <b>{active[0][0]}</b>\n"
            f"🚚 Выдано: <b>{issued[0][0]}</b>\n"
            f"🚫 Отменено: <b>{cancelled[0][0]}</b>"
        )

        # ✅ Фикс: disable_cooldown=True → всегда новое сообщение
        await safe_reply(update, context, message, parse_mode="HTML", disable_cooldown=True)
        logger.info(f"📊 /stats — админ {update.effective_user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка /stats: {e}", exc_info=True)
        # ✅ Фикс: чтобы и ошибка не редактировала старое
        await safe_reply(update, context, "❌ Не удалось загрузить статистику.", disable_cooldown=True)


def register_daily_stats(application):
    application.add_handler(CommandHandler("stats", daily_stats_command))
    logger.info("✅ /stats зарегистрирована")