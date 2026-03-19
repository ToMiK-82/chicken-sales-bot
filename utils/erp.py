# utils/erp.py
import aiohttp
import asyncio
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

# 🔐 Загружаем параметры из .env
HTTP_URL = os.getenv("ERP_HTTP_URL")
USERNAME = os.getenv("ERP_USERNAME")
PASSWORD = os.getenv("ERP_PASSWORD")
DEVOPS_CHAT_ID = int(os.getenv("DEVOPS_CHAT_ID", 0))  # Обязательно задай в .env

if not all([HTTP_URL, USERNAME, PASSWORD]):
    logger.critical("❌ Не заданы ERP_... переменные в .env")
    raise ValueError("ERP_HTTP_URL, ERP_USERNAME, ERP_PASSWORD обязательны")

if DEVOPS_CHAT_ID == 0:
    logger.warning("⚠️ DEVOPS_CHAT_ID не задан — /getib доступен всем")


async def send_order_to_1c(
    order_id: int,
    breed: str,
    quantity: int,
    price: float = 85.0
) -> Tuple[bool, str]:
    """
    Отправляет заказ в 1С через HTTP-сервис.
    Возвращает (True, номер документа) при успехе,
    иначе (False, сообщение об ошибке).
    """
    data = {
        "order_id": order_id,
        "breed": breed,
        "quantity": quantity,
        "price": price
    }

    # ✅ Используем ERP_HTTP_URL как полный URL (уже содержит /Order)
    url = HTTP_URL.rstrip("/")

    auth = aiohttp.BasicAuth(USERNAME, PASSWORD)

    logger.debug(f"📤 Отправка заказа {order_id} в 1С: {url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=data,
                auth=auth,
                timeout=30
            ) as resp:

                if resp.status == 200:
                    try:
                        result = await resp.json()
                        if result.get("success"):
                            doc_number = result.get("doc_number", "неизвестно")
                            logger.info(f"✅ Заказ {order_id} отправлен в 1С: документ №{doc_number}")
                            return True, f"Документ №{doc_number} создан"
                        else:
                            error_msg = result.get("error", "unknown error")
                            logger.warning(f"❌ Ошибка 1С (в JSON): {error_msg}")
                            return False, f"Ошибка 1С: {error_msg}"
                    except Exception:
                        # Сервер вернул текст (например, номер документа)
                        text = await resp.text()
                        text_stripped = text.strip()
                        if text_stripped:
                            logger.info(f"✅ Заказ {order_id} отправлен в 1С: ответ={text_stripped}")
                            return True, f"Документ №{text_stripped} создан"
                        else:
                            logger.error("❌ Пустой ответ от 1С")
                            return False, "Пустой ответ от 1С"
                else:
                    text = await resp.text()
                    logger.error(f"❌ HTTP {resp.status} от 1С: {text[:200]}")
                    return False, f"HTTP {resp.status}: {text[:200]}"

    except asyncio.TimeoutError:
        logger.error("❌ Таймаут подключения к 1С (30 сек)")
        return False, "⏰ Таймаут подключения к 1С (30 сек)"
    except aiohttp.ClientConnectionError:
        logger.error("❌ Нет соединения с 1С (проверьте URL и доступность)")
        return False, "🔌 Нет соединения с 1С (проверьте URL и доступность)"
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка отправки в 1С: {e}", exc_info=True)
        return False, f"Ошибка: {str(e)}"


async def send_to_1c(
    order_id: int,
    phone: str,
    breed: str,
    quantity: int,
    price: float = 85.0,
    action: str = "issue"
) -> Tuple[bool, str]:
    """
    Обёртка для отправки в 1С.
    Сейчас используется только при выдаче (action='issue').
    """
    if action != "issue":
        logger.debug(f"ERP: action='{action}' skipped for order {order_id}")
        return True, "Skipped"  # Логично: не ошибка, просто пропущено

    return await send_order_to_1c(order_id, breed, quantity, price)


# === 🔧 Диагностика 1С: команда /getib ===

async def get_ib_parameters() -> tuple[bool, str]:
    """
    Возвращает текущие параметры подключения к 1С.
    Для диагностики командой /getib.
    Доступно только DEVOPS_CHAT_ID.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        is_available = await _check_connection()
        end_time = asyncio.get_event_loop().time()

        params = {
            "Configured": "✅ Да" if all([HTTP_URL, USERNAME, PASSWORD]) else "❌ Нет",
            "Available": "🟢 Доступен" if is_available else "🔴 Недоступен",
            "Response Time": f"{end_time - start_time:.2f} sec",
            "Full Order URL": HTTP_URL.rstrip("/")  # ✅ Только реальный URL
        }
        result = "\n".join(f"{k}: {v}" for k, v in params.items())
        return True, result
    except Exception as e:
        return False, f"Ошибка генерации: {e}"


async def _check_connection() -> bool:
    """
    Проверяет доступность сервера 1С по URL (GET-запрос).
    Не отправляет данные — только проверяет, жив ли сервер.
    """
    if not HTTP_URL:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HTTP_URL, timeout=10) as resp:
                # Даже если метод не разрешён (405) — сервер жив
                return resp.status in (200, 405, 401, 403)
    except Exception as e:
        logger.debug(f"❌ Сервер 1С недоступен: {e}")
        return False
