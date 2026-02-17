# utils/logging_commands.py

"""
Декоратор: логирует вызов команд.
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def log_command(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        logger = __import__('logging').getLogger(__name__)
        logger.info(f"💬 Команда: /{func.__name__.replace('_command', '')} от @{user.username} (id={user.id})")
        return await func(update, context, *args, **kwargs)
    return wrapper
