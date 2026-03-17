"""
Модуль статистики: /stats и /yearly_stats.

Экспорт:
    - register_daily_stats(application) — регистрирует ежедневную статистику (/stats)
    - get_yearly_stats_handler() — возвращает обработчик для /yearly_stats

Использование:
    from handlers.admin.stats import register_daily_stats, get_yearly_stats_handler

    register_daily_stats(application)
    application.add_handler(get_yearly_stats_handler(), group=3)
"""

from .daily import register_daily_stats
from .yearly import get_yearly_stats_handler

__all__ = ["register_daily_stats", "get_yearly_stats_handler"]
