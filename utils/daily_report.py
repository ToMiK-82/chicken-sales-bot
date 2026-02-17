# utils/daily_report.py

"""
Планировщик: каждый день в 09:00 отправляет отчёт в DevOps-чат.
Читает DEVOPS_CHAT_ID из context.application.bot_data — не зависит от .env.
"""

from telegram.ext import Application, ContextTypes
from database.repository import db
from utils.messaging import safe_reply
import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)


async def send_daily_report(context):
    """Отправляет ежедневный отчёт в 09:00"""
    # ✅ Читаем ID из bot_data
    devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")

    if not devops_chat_id:
        logger.warning("⚠️ DEVOPS_CHAT_ID не найден в bot_data — отчёт не отправлен")
        return

    try:
        today = datetime.now().strftime("%Y-%m-%d")

        # Запросы к БД
        new_today = await db.execute_read(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?",
            (today,)
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

        def fmt(n): return f"{n:,}".replace(",", " ")

        message = (
            f"📌 <b>Ежедневный отчёт</b> 📅 {today}\n"
            f"⏰ Отправлен в 09:00\n\n"

            f"✅ <b>Новых заказов:</b> {new_today[0][0] if new_today else 0}\n"
            f"👤 <b>Новых клиентов:</b> {new_clients_today[0][0] if new_clients_today else 0}\n"
            f"💰 <b>Оборот:</b> {fmt(revenue)} ₽\n\n"

            f"📊 <b>Активно:</b> {active[0][0] if active else 0}\n"
            f"🚚 <b>Выдано:</b> {issued[0][0] if issued else 0}\n\n"

            f"📈 <i>Отчёт сгенерирован автоматически</i>"
        )

        await context.bot.send_message(
            chat_id=devops_chat_id,
            text=message,
            parse_mode="HTML",
            disable_notification=False  # Чтобы админы точно увидели
        )
        logger.info(f"✅ Ежедневный отчёт отправлен в чат {devops_chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при генерации или отправке ежедневного отчёта: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"🔴 <b>Ошибка при отправке ежедневного отчёта:</b>\n<code>{e}</code>",
                parse_mode="HTML"
            )
        except Exception as send_error:
            logger.critical(f"❌ Не удалось отправить сообщение об ошибке в чат {devops_chat_id}: {send_error}")


def setup_daily_report(application: Application):
    """
    Настраивает отправку отчёта каждый день в 09:00 по времени сервера.
    """
    job_queue = application.job_queue

    if not job_queue:
        logger.warning("⚠️ JobQueue не доступен — отчёты отключены")
        return

    # 🕰 Время: 09:00 по серверу
    report_time = time(hour=9, minute=0, second=0)

    job_queue.run_daily(
        send_daily_report,
        time=report_time,
        name="daily_report"
    )
    logger.info("✅ Планировщик: ежедневный отчёт в 09:00 установлен")
