from .entry import show_catalog
from .breed_selection import handle_breed_selection
from .incubator_selection import handle_incubator_selection
from .date_selection import handle_date_selection
from .quantity_input import handle_quantity_input
from .phone_input import handle_phone_input
from .confirmation import handle_confirm_order
from .navigation import handle_back_button
from .utils import clear_catalog_data

from telegram.ext import (
    Application,
    ConversationHandler,
    MessageHandler,
    filters,
)

from states import (
    SELECTING_BREED,
    SELECTING_INCUBATOR,
    SELECTING_DATE,
    CHOOSE_QUANTITY,
    ENTER_PHONE,
    CONFIRM_ORDER,
)

from config.buttons import (
    CATALOG_BUTTON_TEXT,
    BREED_BUTTONS,
    INCUBATOR_BUTTONS,
    BTN_BACK_FULL,
    BTN_CONFIRM_FULL,
    BTN_CANCEL_FULL,
    get_main_keyboard,
)

from utils.messaging import safe_reply

import logging

logger = logging.getLogger(__name__)


catalog_handler = ConversationHandler(
    entry_points=[
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Text([CATALOG_BUTTON_TEXT]),
            show_catalog
        )
    ],
    states={
        SELECTING_BREED: [
            MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
            MessageHandler(filters.Text(BREED_BUTTONS), handle_breed_selection),
        ],
        SELECTING_INCUBATOR: [
            MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
            MessageHandler(filters.Text(INCUBATOR_BUTTONS), handle_incubator_selection),
        ],
        SELECTING_DATE: [
            MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
            MessageHandler(
                filters.Regex(r"^\d{2}\.\d{2}$") & ~filters.COMMAND,
                handle_date_selection
            ),
        ],
        CHOOSE_QUANTITY: [
            MessageHandler(filters.Text([BTN_BACK_FULL]), handle_back_button),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity_input),
        ],
        ENTER_PHONE: [
            MessageHandler(
                (filters.TEXT | filters.CONTACT) & ~filters.COMMAND,
                handle_phone_input
            ),
        ],
        CONFIRM_ORDER: [
            MessageHandler(
                filters.Text([BTN_CONFIRM_FULL, BTN_CANCEL_FULL]),
                handle_confirm_order
            ),
        ],
    },
    fallbacks=[
        # Любой /командой — выходим из диалога
        MessageHandler(
            filters.COMMAND,
            lambda u, c: (clear_catalog_data(c), safe_reply(u, c, "🗑️ Диалог остановлен", reply_markup=get_main_keyboard()))[1]
        ),
    ],
    per_user=True,
    allow_reentry=True,
    name="catalog_flow",
    persistent=False,
    conversation_timeout=600,
    # map_to_parent удалён — не нужен без вложенных ConversationHandler
)


def register_catalog_handler(application: Application) -> None:
    """Регистрирует обработчик каталога."""
    application.add_handler(catalog_handler, group=0)
    logger.info("✅ Обработчик 'Каталог' зарегистрирован: '🐔 Каталог' (group=0)")


__all__ = ["catalog_handler", "register_catalog_handler"]


# === ДЕБАГ ПРИ ЗАГРУЗКЕ ===
print("✅ [DEBUG] handlers/client/catalog/__init__.py успешно загружен")
print(f"🎯 CATALOG_BUTTON_TEXT = {repr(CATALOG_BUTTON_TEXT)}")
print(f"🎯 entry_points = {[(f.filters, f.callback.__name__) for f in catalog_handler.entry_points]}")