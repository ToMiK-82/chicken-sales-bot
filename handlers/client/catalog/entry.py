"""Точка входа: /catalog → выбор породы."""

from telegram import Update
from telegram.ext import ContextTypes
from .utils import clear_catalog_data
from .breed_selection import _back_to_breed_selection
from states import SELECTING_BREED
from database.repository import db
from logging import getLogger

logger = getLogger(__name__)


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск каталога."""
    user_id = update.effective_user.id

    # Восстановление доверенного номера, если есть
    if not context.user_data.get("phone_verified"):
        try:
            trusted_phone = await db.get_trusted_phone_for_user(user_id)
            if trusted_phone:
                context.user_data.update({
                    "phone": trusted_phone,
                    "phone_verified": True,
                    "saved_phone": {"phone": trusted_phone, "verified": True}
                })
        except Exception as e:
            logger.error(f"❌ Ошибка при восстановлении доверенного номера: {e}", exc_info=True)

    # Очищаем предыдущее состояние каталога
    clear_catalog_data(context)
    context.user_data["navigation_stack"] = [SELECTING_BREED]

    # Переходим к выбору породы
    return await _back_to_breed_selection(update, context)


__all__ = ["show_catalog"]