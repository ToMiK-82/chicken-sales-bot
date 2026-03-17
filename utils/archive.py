"""
Модуль для автоматического архивирования старых партий.
✅ Отмена заказов
✅ Уведомление клиентов
✅ Отчёт в DevOps
✅ Запуск через job_queue
"""

from datetime import datetime, date
from telegram.constants import ParseMode
from database.repository import db
from utils.messaging import safe_reply
from html import escape
import logging

logger = logging.getLogger(__name__)


async def auto_archive_old_stocks(context):
    """
    Ежедневная задача:
    1. Архивирует старые партии (date < today)
    2. Отменяет активные заказы на них
    3. Уведомляет клиентов
    4. Отправляет отчёт в DevOps
    """
    try:
        today = date.today().isoformat()
        devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
        if not devops_chat_id:
            logger.warning("🔧 DEVOPS_CHAT_ID не задан — не смогу отправить отчёт.")
            return

        # 1️⃣ Найти старые активные партии
        old_stocks = await db.execute_read(
            "SELECT id, breed, available_quantity, date FROM stocks WHERE status = 'active' AND date < ?",
            (today,)
        )

        if not old_stocks:
            logger.info("📅 Нет старых партий для архивации.")
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text="🟢 <b>Автоархив</b>\nНет старых партий для архивации.",
                parse_mode=ParseMode.HTML
            )
            return

        archived_count = 0
        cancelled_orders_count = 0
        total_chicks_returned = 0

        for stock in old_stocks:
            stock_id, breed, avail_qty, stock_date = stock

            try:
                # 🔹 2️⃣ Найти активные заказы на эту партию
                orders = await db.execute_read(
                    "SELECT id, user_id, quantity FROM orders WHERE stock_id = ? AND status = 'active'",
                    (stock_id,)
                )

                for order in orders:
                    order_id, user_id, qty = order
                    try:
                        # 🔄 Отмена заказа
                        await db.execute_write(
                            "UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,)
                        )
                        cancelled_orders_count += 1
                        total_chicks_returned += qty

                        # ✉️ Уведомление пользователю
                        await safe_reply(
                            None,
                            context,
                            f"❌ Ваш заказ на <b>{qty}</b> шт. <i>{escape(breed)}</i> отменён.\n"
                            f"Партия от <code>{stock_date}</code> больше недоступна.\n"
                            "Спасибо за понимание! 🙏",
                            reply_markup=None,
                            disable_cooldown=True,
                            chat_id=user_id,
                            parse_mode=ParseMode.HTML
                        )

                        logger.info(f"🔁 Отменён заказ {order_id} (пользователь {user_id}) на партию {stock_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отменить заказ {order_id}: {e}")

                # 🔹 3️⃣ Архивируем партию
                await db.execute_write(
                    "UPDATE stocks SET status = 'archived' WHERE id = ?", (stock_id,)
                )
                logger.info(f"📦 Архивирована партия: {breed}, ID={stock_id}, остаток={avail_qty}")
                archived_count += 1

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке партии {stock_id}: {e}")

        # 4️⃣ Отправляем отчёт в DevOps
        report = (
            "📦 <b>Отчёт об автоархиве</b>\n"
            f"📅 Дата: <code>{today}</code>\n"
            f"🗂️ Архивировано партий: <b>{archived_count}</b>\n"
            f"🔁 Отменено заказов: <b>{cancelled_orders_count}</b>\n"
            f"🔁 Всего цыплят: <b>{total_chicks_returned}</b>\n"
            f"✅ Статус: <b>Готово</b>"
        )

        await context.bot.send_message(
            chat_id=devops_chat_id,
            text=report,
            parse_mode=ParseMode.HTML,
            disable_notification=False
        )
        logger.info(f"📬 Отчёт об архивации отправлен в DevOps: {archived_count} партий")

    except Exception as e:
        error_msg = f"❌ Ошибка в автоархиве: {e}"
        logger.error(error_msg, exc_info=True)

        if devops_chat_id:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=f"🚨 <b>Критическая ошибка в автоархиве</b>\n<code>{escape(str(e))}</code>",
                parse_mode=ParseMode.HTML
            )
