"""
🚀 Автоматический /start при первом взаимодействии после перезапуска
✅ Срабатывает на ЛЮБОЕ текстовое сообщение (включая кнопки)
✅ Не мешает дальнейшей обработке — например, catalog_handler сам обработает '🐔 Каталог'
✅ Принудительно завершает все активные диалоги
✅ Очищает временные данные пользователя
✅ Отправляет главное меню
✅ Работает ДО всех других обработчиков (group=-1)

💡 Использование:
- Пользователь пишет "Привет", "Тест", "⬅️ Назад", "✅ Подтвердить" — всё подходит
- Бот отправляет приветствие и клавиатуру
- Все старые диалоги сбрасываются
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
    text = update.message.text if update.message and update.message.text else "<не текст>"
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
                conv = getattr(handler, 'conversations', None)
                if not isinstance(conv, dict):
                    continue  # Пропускаем, если нет словаря диалогов
                try:
                    keys_to_delete = []
                    for key in list(conv.keys()):  # копируем ключи
                        if (isinstance(key, tuple) and user_id in key) or key == user_id:
                            keys_to_delete.append(key)
                    # Удаляем
                    for key in keys_to_delete:
                        logger.debug(
                            f"🛑 Прерван диалог {getattr(handler, 'name', 'unknown')} "
                            f"(group={group_id}) для пользователя {user_id}"
                        )
                        del conv[key]
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось очистить диалог у {handler}: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при обходе handlers: {e}")

    # --- 6. Очищаем user_data от известных временных ключей ---
    keys_to_clear = {
        # Ключи клиентских диалогов
        "awaiting_action", "dialog_state", "in_active_dialog",
        "selected_breed", "selected_date", "quantity", "cart",
        "phone", "current_handler", "conversation",
        "order_in_progress", "navigation_stack", "temp_data",
        "awaiting_phone", "awaiting_confirmation",
        "promo_code", "promo_discount", "promo_expires", "promo_creator",
        "broadcast_stage", "broadcast_content", "broadcast_preview",
        "admin_state", "last_menu", "stats_filter", "shipment_data",
        # Ключи админских потоков
        "edit_stock_id", "edit_flow_history", "stock_list",
        "view_stock_id", "issue_step", "selected_order",
        "edit_order_id", "edit_field", "edit_new_value", "edit_old_value",
        "client_phone", "issue_order", "issue_phone_orders", "issue_batch_orders",
        "cancel_order_id", "cancel_breed", "cancel_date",
        "cancel_quantity", "cancel_price", "cancel_created_at",
        "cancel_stock_id", "cancel_phone", "cancel_order_num",
        # Универсальные флаги
        "HANDLED", "current_conversation", "in_conversation", "edit_mode", "current_promo",
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


def register_startup_handler(application: Application):
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
    logger.info("✅ Обработчик автозапуска активирован (group=-1)")
