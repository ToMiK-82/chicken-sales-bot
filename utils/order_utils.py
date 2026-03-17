# utils/order_utils.py
"""
Утилиты для работы с заказами.
✅ Общая логика отмены заказа
✅ Возврат количества в партию
✅ Уведомление клиента
✅ Логирование
✅ Работает с таблицей 'stocks'
✅ Добавлено: check_stock_availability
"""

from database.repository import db
from utils.messaging import safe_reply
from utils.notifications import _get_user_id_by_phone
from html import escape
from datetime import datetime
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


async def cancel_order_by_id(order_id: int, context=None, user_id=None, admin_initiated=False) -> bool:
    """
    Отменяет заказ по ID.
    Для заказов со статусом 'active' или 'pending' возвращает количество в партию, если она указана.
    Возвращает True при успешной отмене, иначе False.
    """
    try:
        order_data = await db.execute_read(
            """
            SELECT 
                o.id, o.breed, o.quantity, o.date, o.incubator, o.stock_id,
                o.phone, o.status, o.price, o.user_id
            FROM orders o
            WHERE o.id = ?
            """,
            (order_id,)
        )

        if not order_data:
            logger.warning(f"⚠️ Заказ {order_id} не найден")
            return False

        row = order_data[0]
        status = row["status"]

        if status not in ('active', 'pending'):
            logger.info(f"ℹ️ Заказ {order_id} не может быть отменён: статус {status}")
            return False

        stock_id = row["stock_id"]
        quantity = row["quantity"]

        if stock_id:
            await db.execute_write(
                "UPDATE stocks SET available_quantity = available_quantity + ? WHERE id = ?",
                (quantity, stock_id)
            )
            logger.info(f"🔁 {quantity} шт. возвращены в партию {stock_id}")

        await db.execute_write("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        logger.info(f"✅ Заказ {order_id} отменён")

        # Отправка уведомления клиенту
        try:
            client_user_id = row["user_id"]
            if not client_user_id:
                client_user_id = await _get_user_id_by_phone(row["phone"])

            if client_user_id and context and context.bot:
                notification_data = {
                    "id": row["id"],
                    "breed": row["breed"],
                    "quantity": row["quantity"],
                    "date": row["date"],
                    "incubator": row["incubator"],
                    "stock_id": row["stock_id"],
                    "phone": row["phone"],
                    "price": row["price"],
                    "issue_date": datetime.now().strftime("%Y-%m-%d"),
                }
                await _send_cancellation_notification(
                    bot=context.bot,
                    user_id=client_user_id,
                    order_data=notification_data,
                    admin_initiated=admin_initiated
                )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления клиенту для заказа {order_id}: {e}", exc_info=True)

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при отмене заказа {order_id}: {e}", exc_info=True)
        if context and user_id:
            await safe_reply(
                None,
                context,
                "❌ Ошибка при отмене заказа. Попробуйте позже.",
                chat_id=user_id,
                disable_cooldown=True
            )
        return False


async def check_stock_availability(breed: str, incubator: str, delivery_date: str, requested_qty: int) -> Tuple[bool, int]:
    """
    Проверяет, достаточно ли остатков для заказа.
    Учитывает: порода, инкубатор, дата поставки.
    Возвращает: (достаточно: bool, текущий_остаток: int)
    """
    try:
        row = await db.execute_read(
            """
            SELECT available_quantity 
            FROM stocks 
            WHERE breed = ? 
              AND incubator = ? 
              AND date = ?
              AND available_quantity > 0
            """,
            (breed, incubator, delivery_date)
        )
        current_stock = row[0]["available_quantity"] if row else 0
        return current_stock >= requested_qty, current_stock
    except Exception as e:
        logger.error(f"❌ Ошибка проверки остатков для {breed} в {incubator} на {delivery_date}: {e}", exc_info=True)
        return False, 0


async def _send_cancellation_notification(bot, user_id: int, order_data: Dict[str, Any], admin_initiated: bool = False) -> bool:
    """
    Отправляет клиенту уведомление об отмене заказа.
    Принимает готовый user_id.
    """
    if not user_id:
        logger.error("❌ _send_cancellation_notification: user_id не передан")
        return False

    try:
        date_str = order_data.get("date", "")
        formatted_date = "—"
        if date_str:
            try:
                dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                formatted_date = dt.strftime("%d-%m-%Y")
            except Exception:
                formatted_date = str(date_str).split()[0]

        try:
            qty = int(order_data["quantity"])
            price_raw = order_data["price"]
            price = int(float(price_raw)) if price_raw not in (None, '') else 0
            total = qty * price
        except (TypeError, ValueError):
            qty = order_data["quantity"]
            price = "—"
            total = "—"

        stock_info = f" | 🏷️<code>{order_data['stock_id']}</code>" if order_data.get("stock_id") else ""
        phone_safe = escape(str(order_data["phone"]))
        incubator = escape(order_data.get("incubator") or "—")

        title = "ℹ️ Заказ отменён администратором" if admin_initiated else "✅ Заказ отменён"
        reason = "Администратор отменил ваш заказ." if admin_initiated else "Вы отменили заказ. Количество возвращено в продажу."

        message = (
            f"{title}\n\n"
            f"🔢 <b>Заказ №{order_data['id']}</b>\n"
            f"🐔 <b>{escape(order_data['breed'])}</b>{stock_info}\n"
            f"📅 <b>Поставка:</b> {formatted_date}\n"
            f"🏢 <b>Инкубатор:</b> {incubator}\n"
            f"📦 <b>{qty} шт.</b> × <b>{price} руб.</b> = <b>{total} руб.</b>\n"
            f"📞 <b>Телефон:</b> {phone_safe}\n"
            "────────────────\n"
            f"{reason}\n"
            "Спасибо за доверие! До новых поставок 🙏"
        )

        await bot.send_message(chat_id=user_id, text=message, parse_mode="HTML")
        logger.info(f"✉️ Уведомление об отмене отправлено клиенту {user_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления об отмене пользователю {user_id}: {e}", exc_info=True)
        return False
