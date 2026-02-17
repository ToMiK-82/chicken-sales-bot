# utils/safe_send.py
import logging
import asyncio
import hashlib
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError, BadRequest, Forbidden, TimedOut
import httpx

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 10.0

# Внутренние ключи user_data (для cooldown)
COOLDOWN_KEY_PREFIX = "last_reply_"
LAST_MESSAGE_KEY = "last_bot_message_id"

def _stable_hash(text: str) -> str:
    """Генерирует стабильный короткий хеш текста."""
    return hashlib.sha256(text.encode()).hexdigest()[:10]

async def safe_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    max_retries: int = MAX_RETRIES,
    disable_cooldown: bool = False,
    **kwargs
):
    """
    Безопасная отправка сообщений с повторными попытками.
    Работает даже при context=None.
    """
    if not text or not isinstance(text, str):
        logger.warning("❌ safe_reply: пустой или неверный текст")
        return None

    if not context or not context.bot:
        logger.warning("❌ context или bot недоступен")
        return None

    # Определяем chat_id
    target_chat_id = kwargs.get("chat_id")
    if not target_chat_id:
        if update and update.effective_chat:
            target_chat_id = update.effective_chat.id
        elif hasattr(context, "job") and context.job:
            target_chat_id = context.job.chat_id
        else:
            logger.warning("❌ Не удалось определить chat_id")
            return None

    # Устанавливаем parse_mode по умолчанию
    if "parse_mode" not in kwargs:
        kwargs["parse_mode"] = "HTML"
    if "disable_notification" not in kwargs:
        kwargs["disable_notification"] = True

    # Удаляем chat_id из kwargs, чтобы не дублировать
    send_kwargs = {k: v for k, v in kwargs.items() if k != "chat_id"}

    for attempt in range(max_retries + 1):
        try:
            return await context.bot.send_message(
                chat_id=target_chat_id,
                text=text,
                **send_kwargs  # ✅ parse_mode уже внутри, без дублирования
            )
        except (TimedOut, NetworkError, httpx.ReadError, httpx.ConnectError) as e:
            if attempt == max_retries:
                logger.error(f"❌ Все попытки исчерпаны (Network): {e}")
                return None
            delay = min(BASE_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
            await asyncio.sleep(delay)
        except BadRequest as e:
            err_msg = str(e).lower()
            if any(x in err_msg for x in ("query is too old", "message is not modified")):
                logger.warning(f"⚠️ Игнор: {err_msg}")
                return None
            elif "retry after" in err_msg:
                wait_time = int(''.join(filter(str.isdigit, err_msg))) if any(c.isdigit() for c in err_msg) else 5
                await asyncio.sleep(wait_time)
                if attempt == max_retries:
                    return None
            else:
                logger.error(f"❌ BadRequest: {e}")
                return None
        except Forbidden as e:
            logger.error(f"❌ Бот заблокирован пользователем: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка: {e}", exc_info=True)
            return None

    return None
