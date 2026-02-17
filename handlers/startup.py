"""
🚀 Автоматический /start при любом первом взаимодействии после перезапуска
✅ Срабатывает на ЛЮБОЕ текстовое сообщение (включая ЛЮБЫЕ кнопки)
✅ Не мешает дальнейшей обработке (например, catalog_handler сам обработает '🐔 Каталог')
✅ Сбрасывает все диалоги и временные данные
✅ Отправляет главное меню
✅ Работает ДО всех других обработчиков (group=-1)

💡 Использование:
- Пользователь пишет "Привет", "Тест", "⬅️ Назад", "✅ Подтвердить" — всё подходит
- Бот отправляет приветствие и клавиатуру
- Все старые диалоги принудительно завершаются
- Повторные сообщения не вызывают реакцию
"""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters, Application
import logging

# Импортируем только get_main_keyboard — остальное не нужно
from config.buttons import get_main_keyboard

logger = logging.getLogger(__name__)

# 🔑 Ключ для отслеживания активации после перезапуска
FIRST_INTERACTION_KEY = "auto_start_done"


async def auto_start_if_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выполняется первым (group=-1).
    Если пользователь ещё не активен после перезапуска —
    сбрасывает состояние и возвращает в главное меню.
    ВАЖНО: НЕ останавливает цепочку обработки!
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    text = update.message.text

    # --- 1. Проверяем, есть ли доступ к bot_data ---
    if not context.application.bot_data:
        logger.warning("⚠️ bot_data недоступен — невозможно отслеживать автозапуск")
        return

    # --- 2. Инициализируем хранилище активаций ---
    try:
        auto_start_done = context.application.bot_data.setdefault(FIRST_INTERACTION_KEY, {})
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации {FIRST_INTERACTION_KEY}: {e}")
        return

    # --- 3. Проверяем, уже ли активировался пользователь ---
    if user_id in auto_start_done:
        logger.debug(f"⏭️ Пользователь {user_id} (@{username}) уже прошёл автозапуск — выходим")
        return

    # --- 🚀 Это ПЕРВОЕ взаимодействие после перезапуска! ---
    logger.info(
        f"🔄 Автозапуск активирован пользователем {user_id} "
        f"(@{username}) через '{text}'"
    )

    # --- 4. Отмечаем, что автозапуск выполнен ---
    try:
        auto_start_done[user_id] = True
    except Exception as e:
        logger.error(f"❌ Не удалось отметить автозапуск для {user_id}: {e}")
        return

    # --- 5. Принудительно завершаем ВСЕ активные диалоги ---
    try:
        for group_id, handler_group in context.application.handlers.items():
            for handler in handler_group:
                if hasattr(handler, 'conversations') and isinstance(handler.conversations, dict):
                    conv_keys_to_delete = []
                    for key in list(handler.conversations):  # Копия ключей на случай изменения
                        if (isinstance(key, tuple) and user_id in key) or key == user_id:
                            conv_keys_to_delete.append(key)
                    for key in conv_keys_to_delete:
                        logger.debug(
                            f"🛑 Прерван диалог {getattr(handler, 'name', 'unknown')} "
                            f"(group={group_id}) для пользователя {user_id}"
                        )
                        del handler.conversations[key]
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке диалогов: {e}")

    # --- 6. Очищаем user_data от известных временных ключей ---
    keys_to_clear = {
        "awaiting_action", "dialog_state", "in_active_dialog",
        "selected_breed", "selected_date", "quantity", "cart",
        "phone", "current_handler", "conversation",
        "cancel_order_id", "cancel_breed", "cancel_date",
        "cancel_quantity", "cancel_price", "cancel_created_at",
        "cancel_stock_id", "cancel_phone", "cancel_order_num",
        "in_conversation", "navigation_stack",
        "promo_code", "promo_discount", "promo_expires", "promo_creator",
        "broadcast_stage", "broadcast_content", "broadcast_preview",
        "admin_state", "last_menu", "temp_data",
        "awaiting_phone", "awaiting_confirmation", "order_in_progress",
        "edit_mode", "current_promo", "stats_filter", "shipment_data",
    }

    cleared_keys = [key for key in keys_to_clear if key in context.user_data]
    for key in cleared_keys:
        context.user_data.pop(key, None)
    if cleared_keys:
        logger.debug(f"🧹 Очищены ключи user_data: {cleared_keys}")

    # --- 7. Отправляем приветствие и главное меню ---
    try:
        await update.message.reply_text(
            "👋 Бот был перезапущен.\n\n"
            "Выберите нужный раздел:",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        logger.info(f"✅ Главное меню отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить главное меню {user_id}: {e}")

    # --- 8. Логируем событие ---
    logger.info(f"[LOG] User {user_id} - Автоматический старт после перезапуска")

    # ❗ ВАЖНО: НЕ останавливаем цепочку!
    # Позволяем другим обработчикам (например, catalog_handler) обработать исходное сообщение
    # Например: если пользователь написал "🐔 Каталог" — пусть следующий обработчик его обработает


def register_auto_start_handler(application: Application):
    """
    Регистрирует обработчик автозапуска в группе -1 (высший приоритет).
    Выполняется ДО всех других обработчиков.
    """
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT,
            callback=auto_start_if_needed
        ),
        group=-1
    )
    logger.info("✅ Автоматический /start активирован (group=-1)")