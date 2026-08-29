"""
🚀 MAX-адаптер для Chicken Sales Bot.

Приём вебхуков от мессенджера MAX → обработка через core.handlers →
отправка ответов через MAX API (текст + inline-клавиатура + картинки).

Ключевые особенности (по официальной документации dev.max.ru/docs-api):
- API-домен: platform-api2.max.ru, токен в заголовке `Authorization` СЫРОЙ строкой (без Bearer)
- Вебхук строго HTTPS:443 с доверенным сертификатом (Let's Encrypt / Минцифры)
- Секрет подписки приходит в заголовке `X-Max-Bot-Api-Secret` каждого вебхук-запроса
- Личный диалог адресуется по `user_id` отправителя (НЕ chat_id)
- Лимит: не более 2 сообщений в секунду в один диалог
- Подписка на вебхук СБРАСЫВАЕТСЯ MAX'ом через 8ч без успешного ответа → перерегистрируем на каждом старте
- MAX КОПИТ подписки (не заменяет) → перед регистрацией удаляем старые

События вебхука:
- message_created  — новое текстовое сообщение (message.sender.user_id, message.body.text)
- message_callback — нажатие на callback-кнопку (callback.user.user_id, callback.payload, callback.callback_id)
- bot_started      — пользователь нажал «Старт»

.env:
  MAX_TOKEN            — токен MAX-бота (обязательно)
  MAX_WEBHOOK_SECRET   — секрет подписки (5-256 символов A-Z a-z 0-9 - _)
  MAX_WEBHOOK_URL      — https://<домен>/webhook (обязательно для регистрации подписки)
"""
import asyncio
import logging
import os
import sys

# Добавляем корневую папку в sys.path, чтобы работали импорты проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv()

# === Конфигурация ===
MAX_TOKEN = os.getenv("MAX_TOKEN", "").strip()
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "").strip()
MAX_WEBHOOK_URL = os.getenv("MAX_WEBHOOK_URL", "").strip()
MAX_API_BASE = os.getenv("MAX_API_BASE", "https://platform-api2.max.ru")
MAX_MSG_DELAY = 0.55  # пауза между сообщениями одному пользователю (лимит 2 msg/сек)

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("max_adapter")

if not MAX_TOKEN:
    logger.warning("⚠️ MAX_TOKEN не задан в .env — бот не сможет отправлять сообщения")


def _make_headers() -> dict:
    """Заголовки для MAX API: токен сырой строкой, без Bearer."""
    return {"Authorization": MAX_TOKEN}


# === MAX API ===
async def max_post(path: str, *, params: dict = None, json_body: dict = None) -> httpx.Response:
    """POST к MAX API с повторной попыткой при 429/5xx."""
    headers = _make_headers()
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    url = f"{MAX_API_BASE}{path}"

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, headers=headers, params=params, json=json_body)
            if resp.status_code == 429:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if resp.status_code >= 500:
                await asyncio.sleep(1 * (attempt + 1))
                continue
            return resp
        except Exception as e:  # сетевые ошибки
            last_err = e
            await asyncio.sleep(1 * (attempt + 1))

    logger.error(f"❌ MAX API недоступен: {url} | {last_err}")
    return httpx.Response(503, request=httpx.Request("POST", url))


# === Отправка сообщений ===
async def send_max_message(
    user_id: str,
    text: str,
    buttons: Optional[List[List[dict]]] = None,
    format_: Optional[str] = None,
    image_url: Optional[str] = None,
) -> bool:
    """Отправляет сообщение пользователю MAX (адрес — user_id, не chat_id)."""
    if not MAX_TOKEN:
        logger.error("❌ MAX_TOKEN не задан — сообщение не отправлено")
        return False

    body: Dict[str, Any] = {"text": text or ""}

    if format_ in ("markdown", "html"):
        body["format"] = format_

    attachments = []
    # Картинка — только публичные URL (file:// из локального диска MAX не увидит)
    if image_url and image_url.startswith("http"):
        attachments.append({"type": "image", "payload": {"url": image_url}})

    if buttons:
        keyboard = [[_to_max_button(b) for b in row] for row in buttons if row]
        if keyboard:
            attachments.append({"type": "inline_keyboard", "payload": {"buttons": keyboard}})

    if attachments:
        body["attachments"] = attachments

    try:
        resp = await max_post("/messages", params={"user_id": user_id}, json_body=body)
        if resp.status_code == 200:
            logger.info(f"📤 [MAX] OK → {user_id}: {text[:60]!r}")
            return True
        logger.error(f"❌ [MAX] Отправка {user_id} → HTTP {resp.status_code}: {resp.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"❌ [MAX] Ошибка отправки {user_id}: {e}", exc_info=True)
        return False


def _to_max_button(btn: dict) -> dict:
    """
    Конвертирует внутренний формат кнопки в формат MAX.
    Внутренний: {type: message|link|callback, text, payload|url}
    MAX:        {type: callback|link, text, payload|url}
    """
    btn_type = btn.get("type", "message")
    if btn_type == "link":
        return {"type": "link", "text": btn.get("text", ""), "url": btn.get("url", "")}
    # "message" и "callback" — оба превращаем в callback-кнопку с payload
    return {
        "type": "callback",
        "text": btn.get("text", ""),
        "payload": str(btn.get("payload", btn.get("text", ""))),
    }


async def answer_callback(callback_id: str) -> None:
    """Подтверждаем нажатие кнопки (снимаем «загрузку» у пользователя)."""
    if not callback_id:
        return
    try:
        resp = await max_post("/answers", params={"callback_id": callback_id}, json_body={})
        if resp.status_code != 200:
            logger.warning(f"⚠️ [MAX] answer_callback {callback_id} → HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"⚠️ [MAX] answer_callback {callback_id}: {e}")


# === Нормализация ответа core.handlers ===
def normalize_response(response: Any) -> List[dict]:
    """Приводит ответ handle_message_from_messenger к списку «сообщений»."""
    if response is None:
        return []
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        return [response]
    return []


async def send_response(user_id: str, response: Any) -> None:
    """Отправляет все сообщения ответа (с паузой для соблюдения лимита 2/сек)."""
    messages = normalize_response(response)
    for i, msg in enumerate(messages):
        text = (msg.get("text") or "").strip()
        image_url = msg.get("image_url") or ""
        # Пропускаем «сообщения» без текста и без публичной картинки (file:// MAX не увидит)
        if not text and not image_url.startswith("http"):
            continue
        ok = await send_max_message(
            user_id,
            text=text,
            buttons=msg.get("buttons"),
            format_=msg.get("format"),
            image_url=image_url,
        )
        # Пауза между сообщениями одному пользователю (лимит MAX)
        if i < len(messages) - 1:
            await asyncio.sleep(MAX_MSG_DELAY)


# === Разбор входящего вебхука ===
def parse_update(data: dict):
    """
    Извлекает (user_id, chat_id, text, callback_id) из Update MAX.
    Возвращает None, если событие необрабатываемое.
    """
    update_type = data.get("update_type")

    if update_type == "message_created":
        message = data.get("message") or {}
        sender = message.get("sender") or {}
        recipient = message.get("recipient") or {}
        body = message.get("body") or {}
        user_id = str(sender.get("user_id") or "").strip()
        chat_id = str(recipient.get("chat_id") or "").strip()
        text = str(body.get("text") or "").strip()
        return user_id, chat_id, text, None

    if update_type == "message_callback":
        callback = data.get("callback") or {}
        user = callback.get("user") or {}
        user_id = str(user.get("user_id") or "").strip()
        chat_id = str((data.get("message") or {}).get("recipient", {}).get("chat_id") or "").strip()
        text = str(callback.get("payload") or "").strip()
        callback_id = str(callback.get("callback_id") or "").strip()
        return user_id, chat_id, text, callback_id

    if update_type == "bot_started":
        user = data.get("user") or data.get("sender") or {}
        user_id = str(user.get("user_id") or "").strip()
        return user_id, "", "/start", None

    logger.info(f"ℹ️ [MAX] Пропускаем событие: {update_type}")
    return None


async def process_update(data: dict) -> None:
    """Полный цикл: вебхук → core.handlers → отправка ответа."""
    parsed = parse_update(data)
    if parsed is None:
        return

    user_id, chat_id, text, callback_id = parsed
    if not user_id:
        logger.warning(f"⚠️ [MAX] Событие без user_id: {str(data)[:300]}")
        return

    # Подтверждаем нажатие кнопки до отправки новых сообщений
    if callback_id:
        await answer_callback(callback_id)

    try:
        from core.handlers import handle_message_from_messenger

        response = await handle_message_from_messenger("max", user_id, text, chat_id or user_id, None)
        logger.info(f"📨 [MAX] {user_id}: {text!r} → {str(response)[:200]}")
        await send_response(user_id, response)
    except Exception as e:
        logger.error(f"❌ [MAX] Ошибка обработки {user_id}: {e}", exc_info=True)
        try:
            await send_max_message(user_id, "⚠️ Произошла ошибка. Попробуйте позже.")
        except Exception:
            pass


# === Подписка на вебхук ===
async def register_subscription() -> None:
    """(Пере)регистрирует вебхук-подписку на старте.
    MAX сбрасывает подписку через 8ч без успешного ответа → переустановка на каждом старте.
    """
    if not MAX_TOKEN or not MAX_WEBHOOK_URL:
        logger.warning("⚠️ MAX_TOKEN/MAX_WEBHOOK_URL не заданы — подписка пропущена")
        return

    headers = _make_headers()
    try:
        # 1. Список текущих подписок
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{MAX_API_BASE}/subscriptions", headers=headers)
            subscriptions = []
            if resp.status_code == 200:
                subscriptions = (resp.json().get("subscriptions") or [])

            # 2. Удаляем чужие/старые подписки (MAX копит, а не заменяет)
            for sub in subscriptions:
                url = (sub.get("url") or "")
                if url and url != MAX_WEBHOOK_URL:
                    try:
                        await client.delete(
                            f"{MAX_API_BASE}/subscriptions", headers=headers, params={"url": url}
                        )
                        logger.info(f"🗑️ [MAX] Удалена старая подписка: {url}")
                    except Exception as e:
                        logger.warning(f"⚠️ [MAX] Не удалилась подписка {url}: {e}")

        # 3. Регистрируем актуальную подписку
        payload = {
            "url": MAX_WEBHOOK_URL,
            "update_types": ["message_created", "message_callback", "bot_started"],
        }
        if MAX_WEBHOOK_SECRET:
            payload["secret"] = MAX_WEBHOOK_SECRET

        resp = await max_post("/subscriptions", json_body=payload)
        if resp.status_code == 200:
            body = resp.json()
            if body.get("success") is False:
                logger.error(f"❌ [MAX] Подписка отклонена: {body.get('message')}")
            else:
                logger.info(f"✅ [MAX] Вебхук зарегистрирован: {MAX_WEBHOOK_URL}")
        else:
            logger.error(f"❌ [MAX] Подписка → HTTP {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        logger.error(f"❌ [MAX] Ошибка регистрации подписки: {e}", exc_info=True)


# === Фоновая очистка сессий ===
async def session_cleanup_loop() -> None:
    while True:
        try:
            from core.session import cleanup_expired_sessions

            removed = cleanup_expired_sessions(max_age_seconds=3600)
            if removed:
                logger.info(f"🧹 [MAX] Очищено сессий: {removed}")
        except Exception as e:
            logger.warning(f"⚠️ [MAX] Ошибка очистки сессий: {e}")
        await asyncio.sleep(600)


# === FastAPI app ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Инициализация БД (та же chicken_sales.db, что у Telegram-бота)
    try:
        from database.repository import init_db

        await init_db()
        logger.info("✅ [MAX] База данных инициализирована")
    except Exception as e:
        logger.critical(f"🔴 [MAX] Ошибка инициализации БД: {e}", exc_info=True)
        raise

    # 2. Регистрация вебхука (обязательно на каждом старте)
    await register_subscription()

    # 3. Фоновая очистка сессий
    task = asyncio.create_task(session_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Chicken Sales MAX Adapter", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "max-adapter"}


@app.post("/webhook")
async def webhook(request: Request):
    # Проверка источника: заголовок X-Max-Bot-Api-Secret
    secret = request.headers.get("X-Max-Bot-Api-Secret", "")
    if MAX_WEBHOOK_SECRET and secret != MAX_WEBHOOK_SECRET:
        logger.warning(f"🚫 [MAX] Неверный секрет вебхука: {secret!r}")
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)

    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"❌ [MAX] Некорректный JSON вебхука: {e}")
        return JSONResponse({"ok": False, "error": "bad request"}, status_code=400)

    # Обрабатываем синхронно: 200 должен вернуться в течение 30 сек,
    # иначе MAX ретраит (дубли). Ошибки логируем, но 200 всё равно отдаём.
    try:
        await process_update(data)
    except Exception as e:
        logger.error(f"❌ [MAX] Сбой обработки вебхука: {e}", exc_info=True)

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 MAX-адаптер запускается (порт 9999)...")
    uvicorn.run("adapters.max_adapter:app", host="0.0.0.0", port=9999, reload=False)
