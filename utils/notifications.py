"""
Модуль уведомлений клиентам: выдача, изменение, подтверждение заказа.
Использует кэширование phone → user_id.
✅ Использует safe_reply из utils.safe_send
✅ Нет from main import bot
✅ Все сообщения проходят через retry, cooldown, обработку ошибок
"""

from database.repository import db
from html import escape
from datetime import datetime
import logging

# ✅ Импортируем safe_reply из нового модуля
from utils.safe_send import safe_reply

logger = logging.getLogger(__name__)

# Кэш: phone → user_id (в памяти)
_user_cache = {}


async def _get_user_id_by_phone(phone: str) -> int | None:
    """
    Получает user_id по телефону.
    Использует кэш для уменьшения запросов к БД.
    """
    if not phone:
        return None

    if phone in _user_cache:
        return _user_cache[phone]

    try:
        result = await db.execute_read(
            "SELECT user_id FROM users WHERE phone = ?", (phone,)
        )
        user_id = result[0]["user_id"] if result else None
        _user_cache[phone] = user_id
        return user_id
    except Exception as e:
        logger.error(f"❌ Ошибка при получении user_id для {phone}: {e}", exc_info=True)
        return None


def _format_date(date_str: str) -> str:
    """Форматирует строку даты 'YYYY-MM-DD' в 'ДД-ММ-ГГГГ'"""
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return date_str


def _format_price(value) -> int:
    """Безопасное преобразование цены в int"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


# === Уведомления ===

async def notify_client_issue(context, order_data: dict) -> bool:
    """
    Уведомляет клиента о выдаче заказа.
    :param context: ContextTypes.DEFAULT_TYPE — для safe_reply
    :param order_data: {'phone', 'id', 'breed', 'quantity', 'date', 'incubator', 'stock_id', 'price'}
    """
    phone = order_data.get("phone")
    if not phone:
        logger.warning("❌ В order_data отсутствует phone")
        return False

    user_id = await _get_user_id_by_phone(phone)
    if not user_id:
        logger.warning(f"❌ Не найден user_id для телефона {phone}")
        return False

    try:
        breed = order_data["breed"]
        order_id = order_data["id"]
        quantity = order_data["quantity"]
        incubator = order_data.get("incubator", "—")
        stock_id = order_data.get("stock_id")
        price = _format_price(order_data.get("price"))
        total = quantity * price if isinstance(quantity, int) and price > 0 else "—"
        formatted_date = _format_date(order_data["date"])

        stock_info = f" | 🏷️<code>{stock_id}</code>" if stock_id else ""

        message = (
            "✅ <b>Ваш заказ выдан!</b>\n\n"
            f"🔢 <b>Заказ №{order_id}</b>\n"
            f"🐔 <b>{escape(breed)}</b>{stock_info}\n"
            f"📅 <b>Поставка:</b> {formatted_date}\n"
            f"🏢 <b>Инкубатор:</b> {escape(incubator)}\n"
            f"📦 <b>{quantity} шт.</b> × <b>{price} руб.</b> = <b>{total} руб.</b>\n"
            f"📞 <b>Телефон:</b> {escape(phone)}\n"
            "────────────────\n"
            "Спасибо за доверие! До новых поставок 🙏"
        )

        success = await safe_reply(
            update=None,
            context=context,
            text=message,
            chat_id=user_id,
            disable_cooldown=True  # Приоритетное уведомление
        )

        if success:
            logger.info(f"✉️ Уведомление о выдаче отправлено клиенту: {phone}")
        return success

    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления о выдаче клиенту {phone}: {e}", exc_info=True)
        return False


async def notify_client_order_updated(context, order: dict) -> bool:
    """
    Уведомляет клиента об изменении заказа.
    :param context: ContextTypes.DEFAULT_TYPE
    :param order: словарь с полями заказа
    """
    phone = order.get("phone")
    if not phone:
        logger.warning("❌ В order отсутствует phone")
        return False

    user_id = await _get_user_id_by_phone(phone)
    if not user_id:
        logger.warning(f"❌ Не найден user_id для телефона {phone} (изменение заказа)")
        return False

    try:
        changes = []
        order_id = order["id"]

        if "breed" in order and order["breed"]:
            changes.append(f"• Порода: <b>{escape(order['breed'])}</b>")
        if "quantity" in order:
            try:
                qty = int(order["quantity"])
                changes.append(f"• Кол-во: <b>{qty} шт.</b>")
            except (TypeError, ValueError):
                pass
        if "incubator" in order and order["incubator"]:
            changes.append(f"• Инкубатор: <b>{escape(order['incubator'])}</b>")
        if "date" in order:
            formatted = _format_date(order["date"])
            changes.append(f"• Поставка: <b>{formatted}</b>")

        if not changes:
            changes.append("• Заказ обновлён")

        changes_text = "\n".join(changes)

        message = (
            "🔄 <b>Ваш заказ изменён!</b>\n\n"
            f"🔢 <b>Заказ №{order_id}</b>\n\n"
            f"{changes_text}\n\n"
            "Если есть вопросы — свяжитесь с менеджером.\n"
            "Спасибо за доверие! 🙏"
        )

        success = await safe_reply(
            update=None,
            context=context,
            text=message,
            chat_id=user_id,
            disable_cooldown=True
        )

        if success:
            logger.info(f"✉️ Уведомление об изменении заказа отправлено клиенту: {phone}")
        return success

    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления об изменении заказа {order.get('id')}: {e}", exc_info=True)
        return False


async def notify_client_order_confirmed(context, user_id: int, order_id: int, breed: str, quantity: int, date: str) -> bool:
    """
    Уведомляет клиента о подтверждении заказа.
    :param context: ContextTypes.DEFAULT_TYPE
    :param user_id: ID пользователя в Telegram
    :param order_id: номер заказа
    :param breed: порода
    :param quantity: количество
    :param date: дата поставки
    """
    try:
        formatted_date = _format_date(date)

        message = (
            "✅ <b>Ваш заказ подтверждён!</b>\n\n"
            f"📌 Порода: <b>{escape(breed)}</b>\n"
            f"📦 Количество: <b>{quantity} шт.</b>\n"
            f"📅 Поставка: <b>{formatted_date}</b>\n\n"
            "Ожидайте дальнейших инструкций.\n"
            "Спасибо за доверие! 🙏"
        )

        success = await safe_reply(
            update=None,
            context=context,
            text=message,
            chat_id=user_id,
            disable_cooldown=True
        )

        if success:
            logger.info(f"📨 Уведомление о подтверждении отправлено клиенту {user_id}, заказ {order_id}")
        return success

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о подтверждении заказа {order_id}: {e}", exc_info=True)
        return False


# === Опционально: очистка кэша ===
def clear_user_cache():
    """Очистка кэша user_id (например, при перезапуске или обновлении БД)"""
    _user_cache.clear()
    logger.info("🗑️ Кэш user_id очищен")
