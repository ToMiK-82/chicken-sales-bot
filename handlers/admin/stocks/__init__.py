"""
Модуль управления партиями: просмотр, редактирование, добавление.
✅ Регистрирует обработчики: add, view, edit
✅ add — в group=0, остальные — в group=2
"""

from telegram.ext import Application
import logging

logger = logging.getLogger(__name__)

# Импортируем все обработчики
from .view import register_stock_view_handler
from .edit import register_edit_stock_handler
from .add import register_add_stock_handler


def register_stock_handlers(application: Application):
    """
    Регистрирует ВСЕ админские обработчики партий:
    - 📦 Добавить (group=0)   → высокий приоритет
    - 📊 Остатки               → group=2
    - ✏️ Редактировать         → group=2
    """
    logger.info("📦 Регистрация ВСЕХ обработчиков партий...")

    # ✅ Сначала: добавление (group=0 — высокий приоритет)
    # Чтобы не перехватывалось другими обработчиками текста
    register_add_stock_handler(application)

    # ✅ Потом: просмотр и редактирование (group=2)
    register_stock_view_handler(application)  # 📊 Остатки
    register_edit_stock_handler(application)  # ✏️ Редактировать

    logger.info("✅ ВСЕ обработчики партий зарегистрированы: добавление, остатки, редактирование")


__all__ = ["register_stock_handlers"]
