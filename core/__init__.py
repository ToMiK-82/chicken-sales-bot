"""
Пакет core — основная логика бота.
Содержит:
- handlers.py — маршрутизация сообщений
- session.py — управление сессиями пользователя
"""
# Можно оставить пустым или добавить импорты для удобства

# Пример: если хочешь писать `from core import handlers`
from . import handlers, session

# Или явно указать, что доступно при `from core import *`
__all__ = ["handlers", "session"]
