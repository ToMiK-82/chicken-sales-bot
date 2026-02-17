# utils/rate_limit.py

import time
from functools import wraps
from typing import Dict, Tuple, Optional
from telegram import Update
from telegram.ext import ContextTypes

# Ключ: (user_id, func_name), значение: время последнего вызова
_last_call: Dict[Tuple[int, str], float] = {}
# Максимальный возраст записи (в секундах)
_TTL = 3600  # 1 час
# Размер кэша (защита от утечки памяти)
_MAX_CACHE = 10_000


def _cleanup_old_calls():
    """Удаляет старые записи."""
    now = time.time()
    expired = [key for key, ts in _last_call.items() if now - ts > _TTL]
    for key in expired:
        del _last_call[key]


def rate_limit(limit_sec: float = 2.0, notify: bool = True):
    """
    Декоратор: ограничивает частоту вызова команды.
    :param limit_sec: минимальная задержка между вызовами
    :param notify: отправлять ли сообщение "Подождите"?
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            key = (user_id, func.__name__)

            # Очистка старых записей
            if len(_last_call) > _MAX_CACHE // 2:
                _cleanup_old_calls()

            last = _last_call.get(key, 0.0)
            now = time.time()

            if now - last < limit_sec:
                if notify and update.message:
                    try:
                        await update.message.reply_text("⏳ Подождите немного...")
                    except:
                        pass
                return  # Прерываем

            _last_call[key] = now
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator