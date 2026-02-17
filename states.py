"""
Глобальные состояния для ConversationHandler.
Сгруппированы по модулям: админка, рассылка, пользовательские диалоги, выдача заказов.
"""

from __future__ import annotations  # Для отложенных аннотаций


# === Состояния для добавления новой партии (ADM) ===
ADMIN_BREED = "ADMIN_BREED"
ADMIN_DATE = "ADMIN_DATE"
ADMIN_QUANTITY = "ADMIN_QUANTITY"
ADMIN_PRICE = "ADMIN_PRICE"
ADMIN_INCUBATOR = "ADMIN_INCUBATOR"
CONFIRM_ADD = "CONFIRM_ADD"

# === Состояния для редактирования партии ===
EDIT_STOCK_SELECT = "EDIT_STOCK_SELECT"
EDIT_STOCK_QUANTITY = "EDIT_STOCK_QUANTITY"
EDIT_STOCK_DATE = "EDIT_STOCK_DATE"
CONFIRM_EDIT_STOCK = "CONFIRM_EDIT_STOCK"

# === Состояния для отмены партии ===
CANCEL_STOCK_SELECT = "CANCEL_STOCK_SELECT"
CONFIRM_CANCEL_STOCK = "CONFIRM_CANCEL_STOCK"

# === Состояния для просмотра партий ===
ADMIN_STOCKS_MENU = "ADMIN_STOCKS_MENU"

# === Состояния для статистики ===
SELECT_YEAR = "SELECT_YEAR"
SHOW_STATISTICS = "SHOW_STATISTICS"


# === Состояния для рассылки (BDC) ===
class BroadcastState:
    SELECT_MESSAGE_TYPE = "BDC_MSG_TYPE"
    ENTER_MESSAGE = "BDC_MSG_TEXT"
    SELECT_RECIPIENTS = "BDC_RECIPIENTS"
    CONFIRM_SEND = "BDC_CONFIRM_SEND"

    def __init__(self):
        raise NotImplementedError("BroadcastState — namespace, not instantiable")


# === Пользовательские состояния ===
SELECTING_BREED = "SELECTING_BREED"
SELECTING_INCUBATOR = "SELECTING_INCUBATOR"
SELECTING_DATE = "SELECTING_DATE"
CHOOSE_QUANTITY = "CHOOSE_QUANTITY"
ENTER_PHONE = "ENTER_PHONE"
CONFIRM_ORDER = "CONFIRM_ORDER"


# === Состояния для выдачи заказов (ISSUE) ===
CHOOSE_ISSUE_METHOD = "CHOOSE_ISSUE_METHOD"
WAITING_ISSUE_ID = "WAITING_ISSUE_ID"
WAITING_BATCH_DATE = "WAITING_BATCH_DATE"
WAITING_PHONE = "WAITING_PHONE"
CHOOSE_ORDER_ID = "CHOOSE_ORDER_ID"
CONFIRM_ISSUE_FINAL = "CONFIRM_ISSUE_FINAL"


# === Админ-диалоги ===
WAITING_FOR_ACTION = "WAITING_FOR_ACTION"


__all__ = [
    # Admin stock
    "ADMIN_BREED", "ADMIN_DATE", "ADMIN_QUANTITY", "ADMIN_PRICE", "ADMIN_INCUBATOR", "CONFIRM_ADD",
    # Edit
    "EDIT_STOCK_SELECT", "EDIT_STOCK_QUANTITY", "EDIT_STOCK_DATE", "CONFIRM_EDIT_STOCK",
    # Cancel
    "CANCEL_STOCK_SELECT", "CONFIRM_CANCEL_STOCK",
    # View
    "ADMIN_STOCKS_MENU",
    # Stats
    "SELECT_YEAR", "SHOW_STATISTICS",
    # Broadcast
    "BroadcastState",
    # User
    "SELECTING_BREED", "SELECTING_INCUBATOR", "SELECTING_DATE", "CHOOSE_QUANTITY", "ENTER_PHONE", "CONFIRM_ORDER",
    # Issue
    "CHOOSE_ISSUE_METHOD", "WAITING_ISSUE_ID", "WAITING_BATCH_DATE", "WAITING_PHONE", "CHOOSE_ORDER_ID", "CONFIRM_ISSUE_FINAL",
    # Admin menu
    "WAITING_FOR_ACTION",
]
