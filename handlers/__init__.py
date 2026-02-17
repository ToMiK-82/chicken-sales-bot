# handlers/__init__.py

"""
Центральная точка регистрации всех обработчиков.
✅ Поддерживает явную регистрацию (как сейчас)
✅ Дополнительно может автоматически находить обработчики
✅ Гибкая, безопасная, масштабируемая
"""

from typing import Callable
from telegram.ext import Application

# --- Явные импорты ---
# ❌ Удалён: from handlers.client.catalog import register_order_handler
from .client.my_orders import register_my_orders_handler
from .client.promotions import register_promotions_handler
from .client.contacts import register_contacts_handler
from .client.help import register_help_handler        # ✅ Заменили website → help
from .client.schedule import register_schedule_handler  # ✅ Если есть
from .admin import register_admin_handlers

# --- Список функций регистрации ---
REGISTER_FUNCTIONS: list[Callable[[Application], None]] = [
    # ❌ register_order_handler больше не нужен
    register_my_orders_handler,
    register_promotions_handler,
    register_contacts_handler,
    register_help_handler,
    register_schedule_handler,
    register_admin_handlers,
]

# --- Регистрация всех обработчиков ---
def register_all_handlers(application: Application) -> Application:
    """
    Регистрирует все обработчики из REGISTER_FUNCTIONS.
    Можно заменить на автоматическую загрузку, если нужно.
    """
    for register_func in REGISTER_FUNCTIONS:
        try:
            register_func(application)
        except Exception as e:
            from logging import getLogger
            logger = getLogger(__name__)
            logger.error(f"❌ Ошибка при вызове {register_func.__name__}: {e}", exc_info=True)

    from logging import getLogger
    logger = getLogger(__name__)
    logger.info(f"✅ Успешно зарегистрировано {len(REGISTER_FUNCTIONS)} обработчиков")
    return application


# --- Автоматическая регистрация (опционально) ---
def register_all_handlers_auto(application: Application) -> Application:
    """
    Альтернатива: автоматически находит и регистрирует все register_*_handler.
    Полезно при быстром прототипировании.
    """
    import importlib
    import pkgutil
    from logging import getLogger

    logger = getLogger(__name__)
    count = 0

    packages = [
        "handlers.client",
        "handlers.admin",
    ]

    for package_name in packages:
        try:
            package = importlib.import_module(package_name)
            for _, name, _ in pkgutil.iter_modules(package.__path__, package_name + "."):
                try:
                    module = importlib.import_module(name)
                    register_func = getattr(module, "register_handler", None)

                    # Поддержка register_something_handler
                    if not register_func:
                        for attr in dir(module):
                            if attr.startswith("register_") and attr.endswith("_handler") and attr != "register_handler":
                                # Игнорируем catalog, если он устарел
                                if "catalog" in attr and "order" in attr:
                                    continue
                                register_func = getattr(module, attr)
                                break

                    if register_func and callable(register_func):
                        register_func(application)
                        count += 1
                        logger.debug(f"🔁 Авто-регистрация: {name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка в модуле {name}: {e}")
        except Exception as e:
            logger.error(f"❌ Не удалось загрузить пакет {package_name}: {e}")

    logger.info(f"✅ Автоматически зарегистрировано {count} обработчиков")
    return application


# --- Экспорт ---
__all__ = [
    "register_my_orders_handler",
    "register_promotions_handler",
    "register_contacts_handler",
    "register_help_handler",
    "register_schedule_handler",
    "register_admin_handlers",
    "register_all_handlers",
    "register_all_handlers_auto",
]