"""
Утилиты для проверки прав администратора.
✅ Использует кэширование
✅ Поддерживает fallback через bot_data["ADMIN_IDS"] или bot_data["admin_ids"]
✅ Автоматически обновляется при изменении
✅ + exit_to_admin_menu — унифицированный выход из диалогов
✅ Поддержка log=False — для тихих проверок (например, в fallback)
"""

from functools import wraps
from typing import Optional, Set, List
from telegram import Update
from telegram.ext import ContextTypes, Application, ConversationHandler
from database.repository import db
from config.buttons import get_admin_main_keyboard
from .messaging import safe_reply
import logging

logger = logging.getLogger(__name__)

# --- Кэш для ID админов ---
_admin_cache: Set[int] = set()
_cache_initialized: bool = False


async def _ensure_admin_cache(application: Optional[Application] = None) -> None:
    """
    Загружает ID всех админов в кэш.
    Порядок приоритета:
    1. База данных
    2. bot_data["ADMIN_IDS"] (заглавными)
    3. bot_data["admin_ids"] (с маленькой буквы)
    """
    global _admin_cache, _cache_initialized

    if _cache_initialized:
        logger.debug("Кэш админов уже инициализирован — пропускаем")
        return

    # Поиск fallback-админов в bot_data
    admin_ids_fallback = None
    if application and isinstance(application.bot_data, dict):
        admin_ids_fallback = (
            application.bot_data.get("ADMIN_IDS") or
            application.bot_data.get("admin_ids")
        )
        if admin_ids_fallback:
            logger.debug(f"Найден fallback ADMIN_IDS: {admin_ids_fallback}")

    try:
        # Попытка загрузить из БД
        admins = await db.get_all_admins()
        if admins:
            _admin_cache = {admin[0] for admin in admins}
            logger.info(f"✅ Кэш админов загружен из БД: {_admin_cache}")
        else:
            logger.warning("⚠️ Нет админов в БД")

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки админов из БД: {e}", exc_info=True)
        if admin_ids_fallback:
            _admin_cache = set(admin_ids_fallback)
            logger.warning(f"⚠️ Используем fallback-админов: {_admin_cache}")
        else:
            logger.critical("❌ ADMIN_IDS не задан в bot_data — доступ закрыт для всех")
            _admin_cache = set()

    finally:
        _cache_initialized = True


async def is_admin(
    user_id: int,
    application: Optional[Application] = None,
    log: bool = True
) -> bool:
    """
    Проверяет, является ли пользователь админом.
    Args:
        user_id: Telegram ID пользователя
        application: Для доступа к fallback
        log: Логировать ли факт проверки (можно отключить в fallback)
    Returns:
        bool: True, если админ
    """
    await _ensure_admin_cache(application)
    result = user_id in _admin_cache
    if log:
        logger.debug(f"Проверка админа: {user_id} → {result}")
    return result


async def check_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    log: bool = True
) -> bool:
    """
    Проверяет, является ли пользователь админом.
    Если нет — отправляет сообщение об отказе.
    Args:
        update: Telegram Update
        context: ContextTypes.DEFAULT_TYPE
        log: Логировать ли результат (по умолчанию True)
    Returns:
        bool: True, если админ, иначе False
    """
    if not update.effective_user:
        if log:
            logger.warning("❌ Неизвестный пользователь (нет effective_user)")
        return False

    user_id = update.effective_user.id
    is_admin_result = await is_admin(user_id, context.application, log=log)

    if not is_admin_result:
        if log:
            logger.warning(f"🚫 Доступ запрещён: пользователь {user_id}")
        try:
            if update.message:
                await update.message.reply_text(
                    "❌ У вас нет прав администратора.",
                    parse_mode="HTML"
                )
            elif update.callback_query:
                await update.callback_query.answer("❌ Доступ запрещён", show_alert=True)
        except Exception as e:
            logger.debug(f"❌ Не удалось отправить сообщение пользователю {user_id}: {e}")

    return is_admin_result


def admin_required(func):
    """
    Декоратор: требует права администратора.
    Если пользователь не админ — отправляет ошибку и не вызывает функцию.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Передаём log=False, чтобы не засорять лог при каждом вызове
        if not await check_admin(update, context, log=False):
            return
        return await func(update, context)
    return wrapper


async def refresh_admin_cache(application: Optional[Application] = None) -> None:
    """
    Принудительно обновляет кэш админов.
    Полезно после добавления/удаления админов через /addadmin или /rmadmin.
    """
    global _cache_initialized
    _cache_initialized = False
    await _ensure_admin_cache(application)
    logger.info("🔄 Кэш админов принудительно обновлён")


# === Унифицированный выход в главное меню администратора ===

async def exit_to_admin_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message: str = "🚪 Вы в главном меню администратора.",
    keys_to_clear: Optional[List[str]] = None,
    disable_notification: bool = True,
    parse_mode: Optional[str] = "HTML"
):
    """
    Унифицированный выход в главное меню.
    Отправляет ЕДИНСТВЕННОЕ сообщение: действие + заголовок.

    Порядок:
        "Редактирование отменено.\n\n🔐 Админ-панель"

    Полностью очищает следы текущего диалога.
    """
    # Стандартные ключи для очистки
    default_keys = {
        'breed', 'date', 'quantity', 'price', 'incubator',
        'edit_action', 'edit_breed', 'edit_quantity', 'edit_date',
        'cancel_breed', 'cancel_stock_id', 'stock_list',
        'add_breed', 'add_date', 'add_quantity', 'add_price', 'add_incubator',
        'issue_step', 'issue_query', 'selected_order',
        'current_state', 'in_conversation', 'waiting_for',
        'edit_flow_history',           # ← история шагов
        'current_conversation',        # ← КРИТИЧЕСКИ ВАЖНО!
        'HANDLED',                     # ← предотвращает блокировку
    }
    keys_to_remove = (set(keys_to_clear or []) | default_keys) - {"back"}

    for key in keys_to_remove:
        context.user_data.pop(key, None)

    # Единое сообщение
    full_message = f"{message}\n\n🔐 Админ-панель"

    await safe_reply(
        update,
        context,
        full_message,
        reply_markup=get_admin_main_keyboard(),
        parse_mode=parse_mode,
        disable_notification=disable_notification,
    )

    return ConversationHandler.END


# ✅ Экспорт
__all__ = [
    "is_admin",
    "check_admin",
    "admin_required",
    "refresh_admin_cache",
    "exit_to_admin_menu",
]
