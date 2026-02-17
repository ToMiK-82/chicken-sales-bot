# utils/reminder_reporter.py
"""
Модуль для формирования и отправки отчёта админам:
«Кто не подтвердил заказ после напоминания»
Отправляется в DevOps-чат.
Содержит:
- HTML-список с ссылками в Telegram
- Экспорт в Excel (.xlsx)
"""

from datetime import datetime, timedelta
from database.repository import db
from utils.messaging import safe_reply
from telegram.constants import ParseMode
from html import escape  # ✅ Импорт добавлен — безопасное экранирование
import logging
import pandas as pd
from io import BytesIO

logger = logging.getLogger(__name__)

# Крайнее время подтверждения
CONFIRMATION_DEADLINE = "15:00"

# Отчёт отправляется в 15:30 — чтобы дать время на подтверждение до 15:00
REPORT_SEND_TIME = "15:30"


async def send_unconfirmed_orders_report(context):
    """
    Отправляет отчёт: кто не подтвердил заказ до 15:00.
    Содержит:
    - HTML-список с ссылками в Telegram
    - Excel-файл с деталями
    """
    try:
        devops_chat_id = context.application.bot_data.get("DEVOPS_CHAT_ID")
        if not devops_chat_id:
            logger.warning("🔧 DEVOPS_CHAT_ID не задан — не могу отправить отчёт.")
            return

        # Завтрашняя дата
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # SQL: активные заказы на завтра
        query = """
        SELECT 
            o.id AS order_id,
            o.user_id,
            o.breed,
            o.quantity,
            o.price,
            o.date AS delivery_date,
            o.stock_id,
            u.full_name,
            u.username,
            u.phone,
            o.created_at
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.status = 'active'
          AND o.date = ?
          AND o.created_at >= datetime('now', '-2 days')
          AND o.id NOT IN (
              SELECT target_id 
              FROM user_actions 
              WHERE action = 'confirmed_order' 
                AND target_id = o.id
          )
        ORDER BY o.created_at DESC
        """

        result = await db.execute_read(query, (tomorrow_date,))

        if not result:
            logger.info("✅ Все заказы на завтра подтверждены.")
            # Отправляем уведомление
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text="🟢 <b>Все заказы на завтра подтверждены!</b> 🎉\nНикто не требует обзвона.",
                parse_mode=ParseMode.HTML,
                disable_notification=False,
                disable_web_page_preview=True  # ✅ Без превью
            )
            return

        # Формируем HTML-сообщение
        message_lines = [
            f"📞 <b>Нужно подтвердить заказы!</b>\n"
            f"❗️Крайнее время: <b>до {CONFIRMATION_DEADLINE}</b>\n"
            f"После — требуется <b>обзвон</b>:\n"
        ]

        for row in result:
            order_id = row[0]
            user_id = row[1]
            breed = row[2]
            quantity = row[3]
            price = float(row[4])
            delivery_date = row[5]
            stock_id = row[6]
            full_name = row[7] or "Неизвестно"
            username = row[8]
            phone = row[9] or "Не указан"
            created_at = row[10]

            total = int(quantity) * int(price)

            user_link = f"<a href='tg://user?id={user_id}'>{escape(full_name)}</a>"
            username_text = f" (@{username})" if username else ""

            message_lines.append(
                f"🔹 <b>Заказ:</b> <code>{stock_id}</code>\n"
                f"👤 {user_link}{username_text}\n"
                f"📞 <code>{phone}</code>\n"
                f"🐔 <b>{escape(breed)}</b>\n"
                f"📦 <b>{quantity} шт.</b> × <b>{int(price)} руб.</b> = <b>{total} руб.</b>\n"
                f"📅 <b>Получение:</b> {delivery_date}\n"
                f"🕒 <b>Создан:</b> {created_at}\n"
                "──────────────────"
            )

        message = "\n".join(message_lines)

        # Отправка сообщения
        if len(message) > 4096:
            await safe_reply(None, context, "📞 Отчёт слишком большой — отправляю частями.")
            for i in range(0, len(message_lines), 6):
                part = "\n".join(message_lines[i:i+6])
                await context.bot.send_message(
                    chat_id=devops_chat_id,
                    text=part,
                    parse_mode=ParseMode.HTML,
                    disable_notification=False,
                    disable_web_page_preview=True  # ✅ Без превью
                )
        else:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_notification=False,
                disable_web_page_preview=True  # ✅ Без превью
            )

        # Создание Excel
        df_data = []
        for row in result:
            df_data.append({
                "ID заказа": row[6],  # stock_id
                "Цыплята": row[2],   # breed
                "Кол-во": row[3],
                "Цена": float(row[4]),
                "Итого": int(row[3]) * int(float(row[4])),
                "Получение": row[5],
                "Имя клиента": row[7] or "",
                "Юзернейм": f"@{row[8]}" if row[8] else "",
                "Телефон": row[9] or "",
                "Telegram ID": row[1],
                "Создан": row[10],
            })

        df = pd.DataFrame(df_data)
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Неподтверждённые")

        excel_buffer.seek(0)

        # Отправка файла
        await context.bot.send_document(
            chat_id=devops_chat_id,
            document=excel_buffer,
            filename=f"неподтверждённые_заказы_{tomorrow_date}.xlsx",
            caption="📎 <b>Excel-таблица</b> с неподтверждёнными заказами на завтра",
            parse_mode=ParseMode.HTML,
            disable_notification=False
        )

        logger.info(f"📬 Отчёт о {len(result)} неподтверждённых заказах отправлен: сообщение + Excel")

    except Exception as e:
        logger.error(f"❌ Ошибка при формировании отчёта: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=devops_chat_id,
                text="❌ Ошибка при создании отчёта. Проверьте логи.",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except:
            pass