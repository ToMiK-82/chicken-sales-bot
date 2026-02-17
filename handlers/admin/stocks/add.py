"""
Обработчики добавления новой партии в админке.
Диалог: порода → дата → количество → цена → инкубатор → подтверждение.

✅ Работает с единым источником кнопок
✅ Точные фильтры: filters.Text(BREED_BUTTONS)
✅ Кнопки «Назад» и «Отмена» — работают везде
✅ После отмены — нет fallback-падений
✅ Группа: group=0 (высокий приоритет)
✅ Мусор блокируется фильтрами
✅ Хранит в БД чистые значения (без эмодзи)
✅ Использует exit_to_admin_menu — унифицированный выход
✅ Удалены with_emoji, BREED_EMOJI и другие ручные манипуляции
✅ Улучшено: HANDLED и current_conversation
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config.buttons import (
    # --- Клавиатуры ---
    get_breeds_keyboard,
    get_incubator_keyboard,
    get_confirmation_keyboard,
    get_back_only_keyboard,
    get_admin_main_keyboard,
    # --- Кнопки с эмодзи ---
    ADMIN_ADD_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    BTN_CONFIRM_FULL,
    # --- Списки с эмодзи ---
    BREED_BUTTONS,
    INCUBATOR_BUTTONS,
    # --- Чистые списки ---
    BREEDS,
    INCUBATORS,
)
from database.repository import db
from utils.admin_helpers import check_admin, exit_to_admin_menu
from utils.messaging import safe_reply
from html import escape

logger = logging.getLogger(__name__)

# === Состояния ===
ADMIN_BREED = 0
ADMIN_DATE = 1
ADMIN_QUANTITY = 2
ADMIN_PRICE = 3
ADMIN_INCUBATOR = 4
CONFIRM_ADD = 5

# === Ключи для очистки при выходе ===
ADD_STOCK_KEYS = [
    'breed', 'date', 'quantity', 'price', 'incubator',
    'current_conversation', 'HANDLED'
]


# === Fallback: выход по команде или BTN_CANCEL_FULL ===
async def fallback_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /start, /admin, BTN_CANCEL_FULL — выход с очисткой."""
    return await exit_to_admin_menu(
        update,
        context,
        "🚪 Вы вышли из добавления партии.",
        keys_to_clear=ADD_STOCK_KEYS
    )


# === Начало: "Добавить партию" ===
async def handle_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск диалога добавления партии."""
    if not await check_admin(update, context):
        return await exit_to_admin_menu(update, context, "❌ У вас нет прав.")

    logger.info("👤 Админ начал добавление партии")

    # ✅ Без await, передаём все породы через bot_data
    keyboard = get_breeds_keyboard({"available_breeds": BREEDS})

    await safe_reply(
        update,
        context,
        "🐔 <b>Выберите породу:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    context.user_data['current_conversation'] = 'add_stock'
    context.user_data['HANDLED'] = True
    return ADMIN_BREED


# === 1. Выбор породы ===
async def handle_breed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора породы."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        return await exit_to_admin_menu(
            update,
            context,
            "🚪 Вы отменили добавление партии.",
            keys_to_clear=ADD_STOCK_KEYS
        )

    # Сопоставляем: "🍗 Бройлер" → "Бройлер"
    breed = next((b for btn, b in zip(BREED_BUTTONS, BREEDS) if btn == text), None)
    if not breed:
        # ✅ Без await, передаём все породы
        keyboard = get_breeds_keyboard({"available_breeds": BREEDS})
        await safe_reply(
            update,
            context,
            "❌ Выберите породу из списка.",
            reply_markup=keyboard,
        )
        context.user_data['HANDLED'] = True
        return ADMIN_BREED

    context.user_data['breed'] = breed
    logger.info(f"✅ Порода выбрана: {breed}")

    await safe_reply(
        update,
        context,
        "📅 Введите дату поставки в формате: <b>ГГГГ-ММ-ДД</b>",
        reply_markup=get_back_only_keyboard(),
        parse_mode="HTML"
    )
    context.user_data['HANDLED'] = True
    return ADMIN_DATE


# === 2. Ввод даты ===
async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода даты."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        # ✅ Без await, возврат к выбору породы
        keyboard = get_breeds_keyboard({"available_breeds": BREEDS})
        await safe_reply(
            update,
            context,
            "🐔 Выберите породу:",
            reply_markup=keyboard,
        )
        context.user_data['HANDLED'] = True
        return ADMIN_BREED

    if len(text) != 10 or text[4] != '-' or text[7] != '-':
        await safe_reply(
            update,
            context,
            "❌ Неверный формат даты.\nИспользуйте: <b>ГГГГ-ММ-ДД</b>",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        context.user_data['HANDLED'] = True
        return ADMIN_DATE

    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await safe_reply(
            update,
            context,
            "❌ Неверная дата.",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        context.user_data['HANDLED'] = True
        return ADMIN_DATE

    context.user_data['date'] = text
    logger.info(f"📅 Дата поставки: {text}")

    await safe_reply(
        update,
        context,
        "🔢 Введите количество цыплят:",
        reply_markup=get_back_only_keyboard(),
    )
    context.user_data['HANDLED'] = True
    return ADMIN_QUANTITY


# === 3. Ввод количества ===
async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода количества."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "📅 Введите дату поставки в формате: <b>ГГГГ-ММ-ДД</b>",
            reply_markup=get_back_only_keyboard(),
            parse_mode="HTML"
        )
        context.user_data['HANDLED'] = True
        return ADMIN_DATE

    if not text.isdigit() or int(text) <= 0:
        await safe_reply(
            update,
            context,
            "❌ Введите корректное количество.",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return ADMIN_QUANTITY

    context.user_data['quantity'] = int(text)
    logger.info(f"🔢 Количество: {text}")

    await safe_reply(
        update,
        context,
        "💰 Введите цену за одного цыплёнка (в рублях):",
        reply_markup=get_back_only_keyboard(),
    )
    context.user_data['HANDLED'] = True
    return ADMIN_PRICE


# === 4. Ввод цены ===
async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода цены."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "🔢 Введите количество цыплят:",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return ADMIN_QUANTITY

    try:
        price = float(text.replace(',', '.'))
        if price <= 0:
            raise ValueError
    except ValueError:
        await safe_reply(
            update,
            context,
            "❌ Введите корректную цену.",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return ADMIN_PRICE

    context.user_data['price'] = round(price, 2)
    logger.info(f"💰 Цена: {price}")

    # ✅ Передаём все инкубаторы, без await
    keyboard = get_incubator_keyboard(INCUBATORS)
    await safe_reply(
        update,
        context,
        "📍 Выберите инкубатор:",
        reply_markup=keyboard,
    )
    context.user_data['HANDLED'] = True
    return ADMIN_INCUBATOR


# === 5. Выбор инкубатора ===
async def handle_incubator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора инкубатора."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        await safe_reply(
            update,
            context,
            "💰 Введите цену за одного цыплёнка:",
            reply_markup=get_back_only_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return ADMIN_PRICE

    incubator = next((i for btn, i in zip(INCUBATOR_BUTTONS, INCUBATORS) if btn == text), None)
    if not incubator:
        keyboard = get_incubator_keyboard(INCUBATORS)
        await safe_reply(
            update,
            context,
            "❌ Выберите инкубатор из списка.",
            reply_markup=keyboard,
        )
        context.user_data['HANDLED'] = True
        return ADMIN_INCUBATOR

    context.user_data['incubator'] = incubator
    logger.info(f"🏭 Инкубатор: {incubator}")

    breed = escape(context.user_data['breed'])
    incubator_display = next((btn for btn, inc in zip(INCUBATOR_BUTTONS, INCUBATORS) if inc == incubator), incubator)
    date = context.user_data['date']
    quantity = context.user_data['quantity']
    price = context.user_data['price']

    await safe_reply(
        update,
        context,
        f"✅ Проверьте данные:\n\n"
        f"🐔 <b>{breed}</b>\n"
        f"🏢 <b>{incubator_display}</b>\n"
        f"📅 <b>{date}</b>\n"
        f"📦 <b>{quantity}</b> шт.\n"
        f"💰 <b>{price:.2f}</b> руб.\n\n"
        f"Нажмите <b>✅ Подтвердить</b>, чтобы добавить партию.",
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    context.user_data['HANDLED'] = True
    return CONFIRM_ADD


# === 6. Подтверждение ===
async def confirm_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальное подтверждение и сохранение в БД."""
    if not update.effective_message or not update.effective_message.text:
        return await fallback_to_main(update, context)

    text = update.effective_message.text.strip()

    if text == BTN_BACK_FULL:
        keyboard = get_incubator_keyboard(INCUBATORS)
        await safe_reply(
            update,
            context,
            "📍 Выберите инкубатор:",
            reply_markup=keyboard,
        )
        context.user_data['HANDLED'] = True
        return ADMIN_INCUBATOR

    if text != BTN_CONFIRM_FULL:
        await safe_reply(
            update,
            context,
            "📌 Пожалуйста, используйте кнопки.",
            reply_markup=get_confirmation_keyboard(),
        )
        context.user_data['HANDLED'] = True
        return CONFIRM_ADD

    breed: Optional[str] = context.user_data.get('breed')
    incubator: Optional[str] = context.user_data.get('incubator')
    date: Optional[str] = context.user_data.get('date')
    quantity: Optional[int] = context.user_data.get('quantity')
    price: Optional[float] = context.user_data.get('price')

    if not all([breed, incubator, date, quantity is not None, price is not None]):
        return await exit_to_admin_menu(update, context, "❌ Ошибка данных.", keys_to_clear=ADD_STOCK_KEYS)

    try:
        await db.execute_write(
            """
            INSERT INTO stocks (breed, incubator, date, quantity, available_quantity, price, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (breed, incubator, date, quantity, quantity, price)
        )
        logger.info(f"✅ Партия добавлена: breed='{breed}', incubator='{incubator}', date='{date}', quantity={quantity}, price={price:.2f}")
        await safe_reply(
            update,
            context,
            f"✅ Партия «<b>{escape(breed)}</b>» добавлена: <b>{quantity}</b> шт.",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении партии: {e}", exc_info=True)
        return await exit_to_admin_menu(update, context, "❌ Не удалось добавить партию.", keys_to_clear=ADD_STOCK_KEYS)

    # Успешное завершение
    for key in ADD_STOCK_KEYS:
        context.user_data.pop(key, None)
    context.user_data["HANDLED"] = True
    return ConversationHandler.END


# === Регистрация обработчика ===
def register_add_stock_handler(application):
    """Регистрирует обработчик добавления партии с высоким приоритетом."""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Text([ADMIN_ADD_BUTTON_TEXT]),
                handle_add_stock
            )
        ],
        states={
            ADMIN_BREED: [
                MessageHandler(
                    filters.Text(BREED_BUTTONS + [BTN_BACK_FULL]),
                    handle_breed
                ),
            ],
            ADMIN_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_date
                ),
            ],
            ADMIN_QUANTITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_quantity
                ),
            ],
            ADMIN_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_price
                ),
            ],
            ADMIN_INCUBATOR: [
                MessageHandler(
                    filters.Text(INCUBATOR_BUTTONS + [BTN_BACK_FULL]),
                    handle_incubator
                ),
            ],
            CONFIRM_ADD: [
                MessageHandler(
                    filters.Text([BTN_CONFIRM_FULL, BTN_BACK_FULL]),
                    confirm_add_stock
                ),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Text([BTN_CANCEL_FULL]), fallback_to_main),
            MessageHandler(filters.COMMAND, fallback_to_main),
        ],
        per_user=True,
        allow_reentry=True,
        name="admin_add_stock_handler",
    )

    application.add_handler(conv_handler, group=0)
    logger.info("✅ Обработчик 'Добавить партию' зарегистрирован (group=0)")
