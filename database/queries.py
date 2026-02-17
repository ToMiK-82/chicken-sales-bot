# database/queries.py

from typing import List, Tuple
from database.repository import db
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "get_user_orders",
    "get_all_active_stocks",
    "get_daily_stats",
]


async def get_user_orders(user_id: int) -> List[Tuple]:
    """
    Получение всех активных заказов пользователя.

    :param user_id: ID пользователя в Telegram
    :return: Список заказов: (id, user_id, phone, breed, date, quantity, price, status, created_at)
    """
    try:
        result = await db.execute_read(
            """
            SELECT id, user_id, phone, breed, date, quantity, price, status, created_at
            FROM orders 
            WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        return result or []
    except Exception as e:
        logger.error(f"Ошибка при получении заказов пользователя {user_id}: {e}", exc_info=True)
        return []


async def get_all_active_stocks() -> List[Tuple]:
    """
    Получение всех активных партий.

    :return: Список партий: (id, breed, date, quantity, available_quantity, price, incubator, created_at)
    """
    try:
        result = await db.execute_read(
            """
            SELECT id, breed, date, quantity, available_quantity, price, incubator, created_at 
            FROM stocks 
            WHERE quantity > 0 AND status = 'active'
            ORDER BY date, breed
            """
        )
        return result or []
    except Exception as e:
        logger.error(f"Ошибка при получении активных партий: {e}", exc_info=True)
        return []


async def get_daily_stats(date: str) -> List[Tuple]:
    """
    Статистика за день: количество и сумма заказов по породам.

    :param date: Дата в формате 'YYYY-MM-DD'
    :return: Список: [(breed, total_quantity, total_revenue), ...]
    """
    try:
        result = await db.execute_read(
            """
            SELECT breed, SUM(quantity), SUM(quantity * price)
            FROM orders 
            WHERE date = ? AND status = 'active'
            GROUP BY breed
            """,
            (date,)
        )
        return result or []
    except Exception as e:
        logger.error(f"Ошибка при получении статистики за {date}: {e}", exc_info=True)
        return []
