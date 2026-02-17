"""
📅 Обработчик 'График поставок' — показ ближайших партий.
Работает по кнопке '📅 График'.
✅ Удалена защита HANDLED_KEY — она мешает при быстрых кликах
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
)
from config.buttons import (
    SCHEDULE_BUTTON_TEXT,
    get_main_keyboard,
    SEPARATOR,
    # HANDLED_KEY — больше не используется
)
from utils.messaging import safe_reply
from database.repository import db
from html import escape
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает график поставок: порода, инкубатор, дата, доступное количество, цена.
    Без защиты от повторного вызова — пусть обрабатывает каждый клик.
    """
    try:
        today = date.today().isoformat()
        result = await db.execute_read(
            """
            SELECT breed, incubator, date, available_quantity, quantity, price 
            FROM stocks 
            WHERE quantity > 0 AND status = 'active' AND date >= ?
            ORDER BY date
            """,
            (today,)
        )

        if not result:
            await safe_reply(
                update,
                context,
                "📅 Нет активных поставок на ближайшее время.",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            return

        message_lines = ["📦 <b>График поставок:</b>", SEPARATOR]
        for record in result:
            breed, incubator, raw_date, avail_qty, total_qty, price = record
            try:
                avail = max(int(avail_qty or 0), 0)
                total = max(int(total_qty or 0), 1)
                percent = (avail / total) * 100
            except (ValueError, TypeError):
                continue

            icon = "🟢" if percent >= 50 else "🟡" if percent >= 10 else "🔴"

            try:
                price_value = int(float(price or 0))
            except (ValueError, TypeError):
                price_value = 0

            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d")
                formatted_date = dt.strftime("%d-%m-%Y")
            except ValueError:
                formatted_date = raw_date

            breed_safe = escape(breed)
            incubator_safe = escape(incubator) if incubator else "Не указан"

            message_lines.append(
                f"🐔 <b>Порода:</b> {breed_safe}\n"
                f"🏢 <b>Инкубатор:</b> {incubator_safe}\n"
                f"📅 <b>Поставка:</b> {formatted_date}\n"
                f"{icon} <b>Доступно:</b> {avail} шт.\n"
                f"💰 <b>Цена:</b> {price_value} руб."
            )
            message_lines.append(SEPARATOR)

        if message_lines and message_lines[-1] == SEPARATOR:
            message_lines.pop()

        message = "\n".join(message_lines).strip()

        await safe_reply(
            update,
            context,
            message,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки графика: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Ошибка при загрузке графика.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )


def register_schedule_handler(application):
    """Регистрирует обработчик 'График поставок' как простой MessageHandler."""
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Text([SCHEDULE_BUTTON_TEXT]),
            handle_schedule
        ),
        group=1
    )
    logger.info(f"✅ Обработчик 'График поставок' зарегистрирован: '{SCHEDULE_BUTTON_TEXT}' (group=1)")


__all__ = ["handle_schedule"]