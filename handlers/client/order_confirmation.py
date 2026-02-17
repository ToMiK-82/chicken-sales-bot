"""
Обработчик подтверждения заказа клиентом.
✅ Защита от устаревших подтверждений (TTL)
✅ Чёткая привязка к order_id и user_id
✅ Нет дублирования trust_phone
✅ Сохраняет чистоту UX
"""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
)
from utils.order_utils import cancel_order_by_id
from utils.messaging import safe_reply
from config.buttons import (
    BTN_CONFIRM_FULL,
    BTN_CANCEL_FULL,
    get_confirmation_keyboard,
    get_main_keyboard,
)
from database.repository import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CONFIRMATION_KEY = "awaiting_client_confirmation"
CONFIRMATION_TTL_HOURS = 24  # часов


async def request_client_confirmation(
    context: ContextTypes.DEFAULT_TYPE,
    order_id: int,
    user_id: int,
    breed: str,
    quantity: int,
    price: int,
    delivery_date: str,
):
    try:
        total = quantity * price
        date_str = datetime.strptime(delivery_date, "%Y-%m-%d").strftime("%d-%m-%Y")

        message = (
            f"📌 <b>Подтвердите, что заберёте заказ</b>\n\n"
            f"🐔 Порода: <b>{breed}</b>\n"
            f"📦 Количество: <b>{quantity} шт.</b>\n"
            f"💰 Цена: <b>{price} × {quantity} = {total} руб.</b>\n"
            f"📅 Поставка: <b>{date_str}</b>\n\n"
            f"<i>Пожалуйста, подтвердите или отмените заказ.</i>"
        )

        user_data = context.application.user_data.setdefault(user_id, {})
        user_data[CONFIRMATION_KEY] = {
            "order_id": order_id,
            "timestamp": datetime.now().isoformat(),
        }

        await safe_reply(
            None,
            context,
            message,
            chat_id=user_id,
            reply_markup=get_confirmation_keyboard(),
            parse_mode="HTML",
            disable_cooldown=True,
        )

        logger.info(f"📩 Запрос подтверждения отправлен: order_id={order_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке запроса подтверждения {order_id}: {e}", exc_info=True)


async def handle_client_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()
    user_id = update.effective_user.id
    user_data = context.application.user_data.get(user_id, {})

    pending = user_data.get(CONFIRMATION_KEY)
    if not pending:
        return

    order_id = pending["order_id"]

    # ✅ Проверка TTL
    timestamp = pending.get("timestamp")
    if not timestamp:
        user_data.pop(CONFIRMATION_KEY, None)
        return

    try:
        dt = datetime.fromisoformat(timestamp)
        if datetime.now() - dt > timedelta(hours=CONFIRMATION_TTL_HOURS):
            await safe_reply(
                update,
                context,
                "❌ Время подтверждения истекло. Свяжитесь с админом.",
                reply_markup=get_main_keyboard()
            )
            user_data.pop(CONFIRMATION_KEY, None)
            return
    except Exception as e:
        logger.warning(f"Ошибка парсинга timestamp: {e}")
        user_data.pop(CONFIRMATION_KEY, None)
        return

    try:
        order = await db.get_order_by_id(order_id)
        if not order or order["user_id"] != user_id:
            await safe_reply(update, context, "❌ Заказ не найден или недоступен.")
            return

        if text == BTN_CONFIRM_FULL:
            logger.info(f"✅ Клиент подтвердил получение: order_id={order_id}, user_id={user_id}")

            success = await db.execute_write(
                "UPDATE orders SET status = 'active', confirmed_at = datetime('now') WHERE id = ? AND status = 'pending'",
                (order_id,)
            )

            if success:
                await db.trust_phone(order["phone"], order["user_id"])
                await safe_reply(
                    update,
                    context,
                    "✅ Спасибо! Ваш заказ подтверждён. Ждём вас на выдаче!",
                    reply_markup=get_main_keyboard()
                )
            else:
                await safe_reply(
                    update,
                    context,
                    "❌ Заказ уже был изменён. Свяжитесь с админом.",
                    reply_markup=get_main_keyboard()
                )

        elif text == BTN_CANCEL_FULL:
            logger.info(f"❌ Клиент отменил заказ: order_id={order_id}, user_id={user_id}")

            success = await cancel_order_by_id(order_id, context=context, user_id=user_id)
            if success:
                await safe_reply(
                    update,
                    context,
                    "❌ Заказ отменён. Количество возвращено в остатки.",
                    reply_markup=get_main_keyboard()
                )
            else:
                await safe_reply(
                    update,
                    context,
                    "❌ Не удалось отменить заказ. Возможно, он уже выдан.",
                    reply_markup=get_main_keyboard()
                )

        else:
            await safe_reply(
                update,
                context,
                "📌 Пожалуйста, нажмите одну из кнопок ниже.",
            )
            return

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке подтверждения заказа {order_id}: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Произошла ошибка. Попробуйте позже или свяжитесь с админом.",
            reply_markup=get_main_keyboard()
        )
    
    finally:
        user_data.pop(CONFIRMATION_KEY, None)


# === Регистрация обработчика ===
def register_order_confirmation_handler(application):
    """
    ✅ Теперь имя совпадает с ожидаемым в main.py
    Регистрирует обработчик подтверждения заказа клиентом.
    """
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Text([BTN_CONFIRM_FULL, BTN_CANCEL_FULL]),
            handle_client_confirmation
        ),
        group=1
    )
    logger.info("✅ Обработчик подтверждения заказа клиентом зарегистрирован (group=1)")