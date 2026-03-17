# utils/safe_send.py
import logging
import asyncio
import hashlib
from typing import Optional, List, Union

from telegram import Update, Message
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


def _split_text(text: str, max_length: int) -> List[str]:
    """
    Разбивает текст на части до max_length.
    Старается разбить по абзацам или строкам.
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Пытаемся разбить по последнему двойному переносу
        split_pos = text.rfind('\n\n', 0, max_length)
        if split_pos == -1:
            # Если нет — по одному переносу
            split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            # Если и нет — просто по лимиту
            split_pos = max_length

        part = text[:split_pos].rstrip()
        parts.append(part)
        text = text[split_pos:].lstrip()

        if len(text) <= max_length:
            parts.append(text)
            break

    return parts


async def _send_single_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    send_kwargs: dict,
    attempt_limit: int = MAX_RETRIES
) -> Optional[Message]:
    """Отправляет одно сообщение с повторными попытками."""
    for attempt in range(attempt_limit + 1):
        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                **send_kwargs
            )
        except (TimedOut, NetworkError, httpx.ReadError, httpx.ConnectError) as e:
            if attempt == attempt_limit:
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
                if attempt == attempt_limit:
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


async def safe_reply(
    update: Optional[Update],
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    max_retries: int = MAX_RETRIES,
    disable_cooldown: bool = False,
    **kwargs
) -> Union[Optional[Message], List[Optional[Message]], None]:
    """
    Безопасная отправка сообщений с повторными попытками и поддержкой длинных текстов.

    Поддерживает:
    - update=None (например, из задачи)
    - context.job.chat_id
    - parse_mode="HTML" по умолчанию
    - disable_notification=True по умолчанию
    - Автоматическое разбиение длинных сообщений (>4096)

    Returns:
        Message | List[Message] | None
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

    # Устанавливаем parse_mode и disable_notification по умолчанию
    if "parse_mode" not in kwargs:
        kwargs["parse_mode"] = "HTML"
    if "disable_notification" not in kwargs:
        kwargs["disable_notification"] = True

    # Удаляем chat_id из kwargs, чтобы не дублировать
    send_kwargs = {k: v for k, v in kwargs.items() if k != "chat_id"}

    # Проверка длины
    if len(text) > MAX_MESSAGE_LENGTH:
        logger.info(f"📝 Сообщение длиннее {MAX_MESSAGE_LENGTH}, разбиваем...")
        parts = _split_text(text, MAX_MESSAGE_LENGTH)
        message_ids = []
        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(0.1)  # Лёгкая пауза между частями
            msg = await _send_single_message(context, target_chat_id, part, send_kwargs, attempt_limit=max_retries)
            if msg:
                message_ids.append(msg)
            else:
                logger.warning(f"❌ Не удалось отправить часть {i+1}")
        return message_ids if message_ids else None
    else:
        return await _send_single_message(context, target_chat_id, text, send_kwargs, attempt_limit=max_retries)
