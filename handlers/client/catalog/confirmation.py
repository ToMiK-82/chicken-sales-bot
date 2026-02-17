"""
Подтверждение заказа и его создание.
✅ Убрано преждевременное доверие номеру
✅ Заказ создаётся со статусом 'pending'
✅ Доверие будет добавлено только при подтверждении
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
    """Создание заказа в БД. Статус = 'pending'. Не доверяем номер сразу."""
    if context.user_data.get("_order_in_progress"):
        await safe_reply(update, context, "⏳ Заказ уже обрабатывается...")
        return ConversationHandler.END

    context.user_data["_order_in_progress"] = True
    try:
        user_id = update.effective_user.id
        breed = context.user_data["selected_breed"]
        incubator = context.user_data["selected_incubator"]
        date = context.user_data["selected_date"]
        qty = context.user_data["selected_quantity"]
        price = context.user_data["selected_price"]
        phone = context.user_data["phone"]

        # ✅ Получаем stock_id
        stock_id = await db.get_stock_id(breed, incubator, date)
        if not stock_id:
            await safe_reply(update, context, "❌ Партия не найдена.", reply_markup=get_main_keyboard())
            return ConversationHandler.END

        # ✅ ШАГ 1: Проверяем текущий остаток
        stock = await db.execute_read(
            "SELECT available_quantity FROM stocks WHERE id = ?", (stock_id,)
        )
        if not stock:
            await safe_reply(update, context, "❌ Партия не существует.", reply_markup=get_main_keyboard())
            return ConversationHandler.END

        available_quantity = stock[0][0]
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

        # ✅ ШАГ 2: Выполняем транзакцию
        async with db.semaphore:
            success = await db.execute_transaction([
                # 1. Создаём заказ со статусом 'pending'
                ("INSERT INTO orders (user_id, phone, breed, date, quantity, price, stock_id, incubator, status, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'), datetime('now'))",
                 (user_id, phone, breed, date, qty, price, stock_id, incubator)),

                # 2. Уменьшаем остаток ТОЛЬКО если хватает
                ("UPDATE stocks SET available_quantity = available_quantity - ? "
                 "WHERE id = ? AND available_quantity >= ?",
                 (qty, stock_id, qty)),

                # 3. Меняем статус на 'inactive' ТОЛЬКО если реально ≤ 0
                ("UPDATE stocks SET status = 'inactive' "
                 "WHERE id = ? AND (SELECT available_quantity FROM stocks WHERE id = ?) <= 0",
                 (stock_id, stock_id)),
            ])

        if not success:
            # 🔍 Редкий случай: кто-то успел выкупить между проверкой и транзакцией
            await safe_reply(
                update, context,
                "❌ К сожалению, количество изменилось. Попробуйте ещё раз — возможно, осталось меньше.",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END

        # ✅ Успешно создан — СТАТУС = pending
        # ❌ НЕ ВЫЗЫВАЕМ trust_phone(phone, user_id) — это сделаем позже!

        delivery_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        await safe_reply(update, context,
            f"✅ <b>Заказ оформлен!</b> 🎉\n\n"
            f"🐔 <b>Порода:</b> {escape(breed)}\n"
            f"🏭 <b>Инкубатор:</b> {escape(incubator)}\n"
            f"📅 <b>Поставка:</b> {delivery_date}\n"
            f"📦 <b>Кол-во:</b> {qty} шт.\n"
            f"📞 <b>Телефон:</b> {phone}\n\n"
            f"Спасибо за заказ! 🙏\n\n"
            f"Ожидайте подтверждения. Мы свяжемся с вами за день до поставки.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        from logging import getLogger
        logger = getLogger(__name__)
        logger.error(f"❌ Ошибка при создании заказа: {e}", exc_info=True)
        await safe_reply(update, context, "⚠️ Ошибка. Попробуйте позже.", reply_markup=get_main_keyboard())
    finally:
        clear_catalog_data(context)
        context.user_data.pop("_order_in_progress", None)

    return ConversationHandler.END