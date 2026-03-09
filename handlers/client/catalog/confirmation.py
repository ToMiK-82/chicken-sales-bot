"""
Подтверждение заказа и его создание.
✅ Убрано преждевременное доверие номеру
✅ Заказ создаётся со статусом 'pending'
✅ Поддержка: админ создаёт заказ за клиента
✅ Поле customer_phone — настоящий номер клиента
✅ created_by_admin = 1 для админ-заказов
"""

from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# --- Импорты ---
from config.buttons import (
    get_confirmation_keyboard,
    BTN_BACK_FULL,
    BTN_CONFIRM_FULL,
    BTN_CANCEL_FULL,
    get_main_keyboard,
)
from utils.messaging import safe_reply
from .navigation import handle_back_button
from .utils import clear_catalog_data
from states import CONFIRM_ORDER, CHOOSE_QUANTITY
from database.repository import db
import logging

logger = logging.getLogger(__name__)


async def _back_to_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подтверждение заказа."""
    user_data = context.user_data
    breed = user_data.get("selected_breed")
    incubator = user_data.get("selected_incubator")
    date = user_data.get("selected_date")
    quantity = user_data.get("selected_quantity")
    price = user_data.get("selected_price")
    phone = user_data.get("phone", "не указан")

    if not all([breed, incubator, date, quantity, price]):
        clear_catalog_data(context)
        await safe_reply(update, context, "🏠 Главное меню", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    try:
        delivery_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        delivery_date = date

    total = int(quantity * price)
    message = (
        "📄 <b>Подтверждение заказа</b>\n\n"
        f"<b>Порода:</b> {escape(breed)}\n"
        f"<b>Инкубатор:</b> {escape(incubator)}\n"
        f"<b>Поставка:</b> {delivery_date}\n"
        f"<b>Кол-во:</b> {quantity} шт.\n"
        f"<b>Цена:</b> {int(price)} руб.\n"
        f"<b>Сумма:</b> {int(total)} руб.\n"
        f"<b>Телефон:</b> {escape(phone)}\n\n"
        "Подтвердите заказ?"
    )

    await safe_reply(update, context, message, reply_markup=get_confirmation_keyboard(), parse_mode="HTML")
    return CONFIRM_ORDER


async def handle_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подтверждения или отмены."""
    text = update.message.text.strip()

    if text == BTN_BACK_FULL:
        return await handle_back_button(update, context)

    if text in (BTN_CANCEL_FULL, "отменить", "cancel"):
        clear_catalog_data(context)
        await safe_reply(update, context, "❌ Заказ отменён", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    if text in (BTN_CONFIRM_FULL, "подтвердить", "confirm"):
        return await _create_order(update, context)

    await safe_reply(update, context, "📌 Нажмите ✅ Подтвердить или ❌ Отменить", reply_markup=get_confirmation_keyboard())
    return CONFIRM_ORDER


async def _create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание заказа в БД. Поддержка заказов от лица клиента админом."""
    if context.user_data.get("_order_in_progress"):
        await safe_reply(update, context, "⏳ Заказ уже обрабатывается...")
        return ConversationHandler.END

    context.user_data["_order_in_progress"] = True
    try:
        user_id = update.effective_user.id
        full_name = update.effective_user.full_name
        username = update.effective_user.username

        breed = context.user_data["selected_breed"]
        incubator = context.user_data["selected_incubator"]
        date = context.user_data["selected_date"]
        qty = context.user_data["selected_quantity"]
        price = context.user_data["selected_price"]
        phone = context.user_data["phone"]

        # Определяем: админ ли?
        is_admin = user_id in context.application.bot_data.get("ADMIN_IDS", [])
        customer_name = None
        customer_phone = None

        if is_admin:
            # Админ вводит данные клиента → сохраняем как реального клиента
            customer_name = context.user_data.get("admin_client_name") or "Клиент (админ)"
            customer_phone = phone
            # ❌ Не доверяем номер админу!
            logger.info(f"🛠️ Админ {user_id} оформил заказ за клиента: {customer_name} ({customer_phone})")
        else:
            # Обычный пользователь
            customer_name = full_name
            customer_phone = phone
            # ✅ Доверим номер позже при подтверждении (в админке)
            logger.info(f"🛍️ Пользователь {user_id} оформил заказ: {full_name} ({phone})")

        # Получаем stock_id
        stock_id = await db.get_stock_id(breed, incubator, date)
        if not stock_id:
            await safe_reply(update, context, "❌ Партия не найдена.", reply_markup=get_main_keyboard())
            return ConversationHandler.END

        # Проверяем остаток
        stock = await db.execute_read("SELECT available_quantity FROM stocks WHERE id = ?", (stock_id,))
        if not stock:
            await safe_reply(update, context, "❌ Партия не существует.", reply_markup=get_main_keyboard())
            return ConversationHandler.END

        available_quantity = stock[0]["available_quantity"]
        if qty > available_quantity:
            await safe_reply(
                update, context,
                f"❌ Невозможно оформить заказ.\n\n"
                f"📦 Доступно: <b>{available_quantity} шт.</b>\n"
                f"🛒 Вы запрашиваете: <b>{qty} шт.</b>\n\n"
                f"Пожалуйста, измените количество.",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END

        # Транзакция
        async with db.semaphore:
            success = await db.execute_transaction([
                ("INSERT INTO orders "
                 "(user_id, phone, breed, date, quantity, price, stock_id, incubator, status, "
                 "created_at, updated_at, customer_name, customer_phone, created_by_admin) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'), datetime('now'), ?, ?, ?)",
                 (user_id, phone, breed, date, qty, price, stock_id, incubator,
                  customer_name, customer_phone, int(is_admin))),

                ("UPDATE stocks SET available_quantity = available_quantity - ? "
                 "WHERE id = ? AND available_quantity >= ?",
                 (qty, stock_id, qty)),

                ("UPDATE stocks SET status = 'inactive' "
                 "WHERE id = ? AND (SELECT available_quantity FROM stocks WHERE id = ?) <= 0",
                 (stock_id, stock_id)),
            ])

        if not success:
            await safe_reply(
                update, context,
                "❌ К сожалению, количество изменилось. Попробуйте ещё раз.",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END

        delivery_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        await safe_reply(update, context,
            f"✅ <b>Заказ оформлен!</b> 🎉\n\n"
            f"🐔 <b>Порода:</b> {escape(breed)}\n"
            f"📅 <b>Поставка:</b> {delivery_date}\n"
            f"📦 <b>Кол-во:</b> {qty} шт.\n"
            f"📞 <b>Телефон:</b> {escape(customer_phone)}\n\n"
            f"Спасибо за заказ! Ожидайте подтверждения. Мы свяжемся с вами за день до поставки.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

        # Лог
        logger.info(f"✅ Заказ на {qty} шт. {breed} от {customer_phone} (админ={is_admin}) успешно создан")

    except Exception as e:
        logger.error(f"❌ Ошибка при создании заказа: {e}", exc_info=True)
        await safe_reply(update, context, "⚠️ Ошибка. Попробуйте позже.", reply_markup=get_main_keyboard())
    finally:
        clear_catalog_data(context)
        context.user_data.pop("_order_in_progress", None)

    return ConversationHandler.END
