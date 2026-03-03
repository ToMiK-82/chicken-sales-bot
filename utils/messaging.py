"""
Модуль для безопасной отправки и редактирования сообщений.
✅ Поддержка: message, callback, edited_message, job, chat_id
✅ Приоритет: редактирование последнего сообщения → новое сообщение
✅ Повторные попытки с экспоненциальной задержкой
✅ Разбивка длинных сообщений (>4096)
✅ parse_mode="HTML" по умолчанию
✅ Защита от Flood, RetryAfter, BadRequest, Forbidden
✅ Cooldown по user_id + хешу текста (стабильный)
✅ Исключения для навигационных кнопок: не блокируются
✅ Сообщения с reply_markup не попадают под cooldown
✅ Единая точка отправки: safe_reply
✅ Автоочистка last_message_id при ошибках
✅ Безопасная работа при context=None (например, при старте)
✅ Исправлено: <a href="tel:..."> работает корректно
✅ Напоминания клиентам: за 2 и 1 день до поставки (только pending, с записью в user_actions)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Set

from telegram import Update
from telegram.ext import ContextTypes
from html import escape

from config.buttons import get_back_only_keyboard
from database.repository import db
from utils.safe_send import safe_reply

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
COOLDOWN_SECONDS = 60

# ✅ Исключения: не блокируются по cooldown
SKIP_COOLDOWN_PREFIXES: Set[str] = {
    "Назад", "Отменить", "Нет", "Выход", "Отмена", "Назад в меню", "Назад к меню",
    "Выйти", "Готово", "Подтвердить", "✅", "❌", "⬅️", "📞", "📦", "📋", "📅", "🐔",
    "🎁", "📊", "📢", "📈", "Меню", "🏠 Главное меню", "📋 Мои заказы",
    "+7", "тел:", "поддержка", "контакт", "звонок", "версия", "техподдержка"
}

# Внутренние ключи user_data
COOLDOWN_KEY_PREFIX = "last_reply_"
LAST_MESSAGE_KEY = "last_bot_message_id"


def log_action(user_id: int, action: str, description: str):
    """Логирует действие пользователя."""
    logger.info(f"[LOG] User {user_id} - {action}: {description}")


# ──────────────────────────────────────────────────────────────
# Все функции safe_reply, _send_single_message_with_retry и т.д.
# уже определены в utils.safe_send.py
# Этот модуль их использует, но не переопределяет
# ──────────────────────────────────────────────────────────────


async def handle_error(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
    """Централизованная обработка ошибок."""
    update_id = getattr(update, "update_id", "unknown")
    logger.error(f"❌ Ошибка в обработчике (update_id={update_id}): {context.error}", exc_info=True)

    from httpx import RequestError
    from telegram.error import TimedOut, NetworkError, Forbidden

    ignored_errors = (RequestError, TimeoutError, TimedOut, NetworkError, Forbidden)
    if isinstance(context.error, ignored_errors):
        err_msg = str(context.error).lower()
        ignored_phrases = ["query is too old", "message is not modified", "retry after"]
        if any(phrase in err_msg for phrase in ignored_phrases):
            return

    try:
        target_chat_id = None
        if update and update.effective_chat:
            target_chat_id = update.effective_chat.id
        elif context.job:
            target_chat_id = context.job.chat_id

        if target_chat_id:
            await safe_reply(
                update=update,
                context=context,
                text="⚠️ Произошла ошибка. Попробуйте позже.",
                reply_markup=get_back_only_keyboard(),
                disable_cooldown=True,
                chat_id=target_chat_id
            )
    except Exception as e:
        logger.error(f"❌ Не удалось ответить пользователю: {e}")

    try:
        devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
        if not devops_chat_id:
            return

        error_text = (
            "🚨 <b>Критическая ошибка в боте</b>\n"
            f"<code>{escape(str(context.error))}</code>\n"
            f"<b>Update ID:</b> <code>{update_id}</code>"
        )

        await safe_reply(
            update=None,
            context=context,
            text=error_text,
            chat_id=devops_chat_id,
            disable_cooldown=True,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении в DevOps: {e}", exc_info=True)


# === ЕЖЕДНЕВНЫЙ ОТЧЁТ (исправленный) ===
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    try:
        devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
        if not devops_chat_id:
            logger.warning("🔧 DEVOPS_CHAT_ID не задан — не могу отправить ежедневный отчёт.")
            return

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 🛒 Все заказы за вчера (любой статус)
        total_orders_result = await db.execute_read(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?", (yesterday,)
        )
        total_orders = total_orders_result[0][0] if total_orders_result and total_orders_result[0] else 0

        # 💰 Выручка за день — все заказы, созданные вчера, с ценой
        revenue_result = await db.execute_read(
            "SELECT SUM(quantity * price) FROM orders WHERE DATE(created_at) = ?", (yesterday,)
        )
        new_revenue = int(revenue_result[0][0] or 0)

        # 📦 Активные заказы (на любой дате)
        active_result = await db.execute_read(
            "SELECT COUNT(*), SUM(quantity * price) FROM orders WHERE status = 'active'"
        )
        active_count = active_result[0][0] if active_result and active_result[0] else 0
        active_revenue = int(active_result[0][1] or 0)

        # 📅 Поставки в ближайшие 7 дней
        upcoming_result = await db.execute_read(
            """
            SELECT 
                COUNT(*), 
                SUM(quantity),           -- ✅ Всего цыплят
                SUM(available_quantity)  -- ✅ Доступно
            FROM stocks 
            WHERE status = 'active' 
              AND date >= DATE('now') 
              AND date <= DATE('now', '+7 days')
            """
        )
        row = upcoming_result[0]
        upcoming_shipments = row[0] or 0
        total_chicks = row[1] or 0      # ✅ Теперь quantity
        available_chicks = row[2] or 0

        report = (
            "📈 <b>Ежедневный отчёт</b>\n"
            f"📆 Дата: <code>{yesterday}</code>\n"
            f"🛒 <b>Новых заказов:</b> {total_orders}\n"
            f"💰 <b>Выручка за день:</b> {new_revenue} руб.\n"
            f"📦 <b>Активных заказов:</b> {active_count} на {active_revenue} руб.\n"
            f"📅 <b>Поставок в ближайшие 7 дней:</b> {upcoming_shipments}\n"
            f"🐥 <b>Всего цыплят:</b> {total_chicks}\n"
            f"🟢 <b>Доступно:</b> {available_chicks}\n"
            f"✅ <b>Статус:</b> Готов"
        )

        await safe_reply(
            update=None,
            context=context,
            text=report,
            chat_id=devops_chat_id,
            disable_cooldown=True,
            parse_mode="HTML"
        )
        logger.info("✅ Ежедневный отчёт отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации ежедневного отчёта: {e}", exc_info=True)


# === НАПОМИНАНИЕ АДМИНАМ ЗА 2 ДНЯ (исправлено) ===
async def send_admin_shipment_reminder(context: ContextTypes.DEFAULT_TYPE):
    try:
        devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
        if not devops_chat_id:
            return

        reminder_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        # 🔥 Берём ВСЕ активные партии на дату, даже если available_quantity = 0
        result = await db.execute_read(
            """
            SELECT breed, incubator, quantity, available_quantity, price
            FROM stocks
            WHERE date = ? AND status = 'active'
            ORDER BY breed
            """,
            (reminder_date,)
        )

        if not result:
            logger.info(f"📭 Нет поставок через 2 дня ({reminder_date})")
            return

        message_lines = [f"🔔 <b>Напоминание: поставки через 2 дня ({reminder_date})</b>"]

        for breed, incubator, qty, avail, price in result:
            sold = qty - avail
            incubator_text = f" | 🏢 <b>{escape(incubator)}</b>" if incubator else ""
            price_int = int(float(price or 0))

            message_lines.append(
                f"🐔 <b>{escape(breed)}</b>{incubator_text}\n"
                f"📦 <b>Всего:</b> {qty} шт.\n"
                f"🟢 <b>Доступно:</b> {avail} шт.\n"
                f"🔴 <b>Заказано:</b> {sold} шт.\n"
                f"💰 <b>Цена:</b> {price_int} руб.\n"
                "──────────────────"
            )

        await safe_reply(
            update=None,
            context=context,
            text="\n".join(message_lines),
            chat_id=devops_chat_id,
            disable_cooldown=True,
            parse_mode="HTML"
        )
        logger.info(f"✅ Напоминание о поставках отправлено: {len(result)} партий")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке напоминания админам: {e}", exc_info=True)


# === НАПОМИНАНИЕ КЛИЕНТУ ЗА 2 ДНЯ ===
async def send_pending_reminder_2_days(context: ContextTypes.DEFAULT_TYPE):
    """
    Первое напоминание клиентам с pending-заказами за 2 дня до поставки.
    """
    try:
        two_days_ahead = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        rows = await db.execute_read(
            """
            SELECT o.id, o.user_id, o.breed, o.quantity, o.price, o.date, o.phone
            FROM orders o
            WHERE o.status = 'pending'
              AND o.date = ?
              AND o.id NOT IN (
                  SELECT target_id FROM user_actions
                  WHERE action = 'reminder_sent_2_days' AND target_id = o.id
              )
            """,
            (two_days_ahead,)
        )

        if not rows:
            logger.info(f"📭 На {two_days_ahead} нет pending-заказов для напоминания (2 дня).")
            return

        for order_id, user_id, breed, quantity, price, order_date, phone in rows:
            try:
                target_user_id = user_id
                if not target_user_id:
                    from utils.notifications import _get_user_id_by_phone
                    target_user_id = await _get_user_id_by_phone(phone)
                if not target_user_id:
                    logger.warning(f"❌ Не найден user_id для заказа {order_id}, телефон {phone}")
                    continue

                total = quantity * int(price) if price else 0
                date_str = datetime.strptime(order_date, "%Y-%m-%d").strftime("%d-%m-%Y")

                message = (
                    f"📅 <b>Почти готово!</b>\n\n"
                    f"Через 2 дня ({date_str}) — получение:\n"
                    f"🐔 <b>{quantity} шт. {breed}</b>\n\n"
                    f"Пожалуйста, подтвердите, что сможете забрать заказ.\n"
                    f"Это поможет нам правильно спланировать поставку 🙏"
                )

                await safe_reply(
                    update=None,
                    context=context,
                    text=message,
                    chat_id=target_user_id,
                    disable_cooldown=True,
                    parse_mode="HTML"
                )

                await db.execute_write(
                    "INSERT INTO user_actions (user_id, action, target_id) VALUES (?, ?, ?)",
                    (target_user_id, 'reminder_sent_2_days', order_id)
                )
                logger.info(f"📨 [2 дня] Напоминание отправлено: заказ {order_id}, user_id {target_user_id}")

            except Exception as e:
                logger.error(f"❌ Не удалось отправить напоминание (2 дня) для заказа {order_id}: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке напоминаний за 2 дня: {e}", exc_info=True)


# === НАПОМИНАНИЕ КЛИЕНТУ ЗА 1 ДЕНЬ ===
async def send_pending_reminder_1_day(context: ContextTypes.DEFAULT_TYPE):
    """
    Финальное напоминание клиентам с pending-заказами за 1 день до поставки.
    """
    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        rows = await db.execute_read(
            """
            SELECT o.id, o.user_id, o.breed, o.quantity, o.price, o.date, o.phone
            FROM orders o
            WHERE o.status = 'pending'
              AND o.date = ?
              AND o.id NOT IN (
                  SELECT target_id FROM user_actions
                  WHERE action = 'reminder_sent_1_day' AND target_id = o.id
              )
            """,
            (tomorrow,)
        )

        if not rows:
            logger.info(f"📭 На {tomorrow} нет pending-заказов для финального напоминания.")
            return

        for order_id, user_id, breed, quantity, price, order_date, phone in rows:
            try:
                target_user_id = user_id
                if not target_user_id:
                    from utils.notifications import _get_user_id_by_phone
                    target_user_id = await _get_user_id_by_phone(phone)
                if not target_user_id:
                    logger.warning(f"❌ Не найден user_id для заказа {order_id}, телефон {phone}")
                    continue

                total = quantity * int(price) if price else 0
                date_str = datetime.strptime(order_date, "%Y-%m-%d").strftime("%d-%m-%Y")

                message = (
                    f"⏰ <b>Финальное напоминание!</b>\n\n"
                    f"Завтра ({date_str}) — получение:\n"
                    f"🐔 <b>{quantity} шт. {breed}</b>\n\n"
                    f"Если вы <b>не подтвердите</b> сегодня —\n"
                    f"мы рискуем отдать цыплят другим клиентам 😔\n\n"
                    f"Подтвердите, пожалуйста, что сможете забрать заказ!"
                )

                await safe_reply(
                    update=None,
                    context=context,
                    text=message,
                    chat_id=target_user_id,
                    disable_cooldown=True,
                    parse_mode="HTML"
                )

                await db.execute_write(
                    "INSERT INTO user_actions (user_id, action, target_id) VALUES (?, ?, ?)",
                    (target_user_id, 'reminder_sent_1_day', order_id)
                )
                logger.info(f"📨 [1 день] Финальное напоминание отправлено: заказ {order_id}, user_id {target_user_id}")

            except Exception as e:
                logger.error(f"❌ Не удалось отправить финальное напоминание для заказа {order_id}: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке финальных напоминаний: {e}", exc_info=True)


__all__ = [
    "safe_reply",
    "handle_error",
    "send_daily_report",
    "send_admin_shipment_reminder",
    "send_pending_reminder_2_days",
    "send_pending_reminder_1_day",
]
