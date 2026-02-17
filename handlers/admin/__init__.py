# handlers/admin/__init__.py

"""
Модуль администратора — точка входа для регистрации обработчиков админ-панели.
Теперь использует единый register_admin_handlers из main.py
"""

from .main import register_admin_handlers

__all__ = ["register_admin_handlers"]