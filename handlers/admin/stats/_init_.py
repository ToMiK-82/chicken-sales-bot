# handlers/admin/stats/__init__.py

"""
Модуль статистики: /stats и /yearly_stats.
"""

from .daily import register_daily_stats
from .yearly import get_yearly_stats_handler

__all__ = ["register_daily_stats", "get_yearly_stats_handler"]
