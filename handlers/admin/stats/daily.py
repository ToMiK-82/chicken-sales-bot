"""
Команда /stats — краткая статистика за день.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.admin_helpers import admin_required
from database.repository import db
from utils.messaging import safe_reply
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def safe_count(result) -> int:
    """Безопасное извлечение COUNT(*) из результата execute_read"""
    return result[0][0] if result and result[0] else 0


def fmt(n: int) -> str:
    """Форматирует число с пробелами как разделителем"""
    return f"{n:,}".replace(",", " ")


@admin_required
async def daily_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        total_orders = safe_count(await db.execute_read("SELECT COUNT(*) FROM orders"))
        total_clients = safe_count(await db.execute_read("SELECT COUNT(DISTINCT phone) FROM orders"))

        new_today = safe_count(await db.execute_read(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?", (today,)
        ))

        new_clients_today = safe_count(await db.execute_read("""
            SELECT COUNT(*) FROM (
                SELECT phone FROM orders
                WHERE DATE(created_at) = ?
                GROUP BY phone
                HAVING COUNT(*) = 1
            )
        """, (today,)))

        revenue_result = await db.execute_read("""
            SELECT SUM(price * quantity)
            FROM orders
            WHERE status IN ('active', 'issued')
        """)
        revenue = int(float(revenue_result[0][0]) if revenue_result and revenue_result[0][0] is not None else 0)

        active = safe_count(await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'active'"))
        issued = safe_count(await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'issued'"))
        cancelled = safe_count(await db.execute_read("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"))

        message = (
            f"📊 <b>Статистика за день</b>\n"
            f"📅 {today}\n\n"

            f"📌 <b>Общее</b>\n"
            f"🧮 Всего заказов: <b>{fmt(total_orders)}</b>\n"
            f"👥 Всего клиентов: <b>{fmt(total_clients)}</b>\n\n"

            f"📌 <b>Сегодня</b>\n"
            f"✅ Новых: <b>{new_today}</b>\n"
            f"👤 Новых клиентов: <b>{new_clients_today}</b>\n"
            f"💰 Оборот: <b>{fmt(revenue)} ₽</b>\n\n"

            f"📌 <b>Статусы</b>\n"
            f"📈 Активные: <b>{active}</b>\n"
            f"🚚 Выдано: <b>{issued}</b>\n"
            f"🚫 Отменено: <b>{cancelled}</b>"
        )

        await safe_reply(update, context, message, parse_mode="HTML", disable_cooldown=True)
        logger.info(f"📊 /stats — админ {update.effective_user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка /stats: {e}", exc_info=True)
        await safe_reply(update, context, "❌ Не удалось загрузить статистику.", disable_cooldown=True)


def register_daily_stats(application):
    application.add_handler(CommandHandler("stats", daily_stats_command))
    logger.info("✅ /stats зарегистрирована")
