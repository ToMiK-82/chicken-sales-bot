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

if not all([HTTP_URL, USERNAME, PASSWORD]):
    logger.critical("❌ Не заданы ERP_... переменные в .env")
    raise ValueError("ERP_HTTP_URL, ERP_USERNAME, ERP_PASSWORD обязательны")


async def send_order_to_1c(
    order_id: int,
    breed: str,
    quantity: int,
    price: float
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

    auth = aiohttp.BasicAuth(USERNAME, PASSWORD)
    url = HTTP_URL.rstrip("/") + "/order"  # Можно вынести в .env

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
                            logger.info(f"📤 Заказ {order_id} отправлен в 1С: документ №{doc_number}")
                            return True, f"Документ №{doc_number} создан"
                        else:
                            error_msg = result.get("error", "unknown error")
                            return False, f"Ошибка 1С: {error_msg}"
                    except Exception:
                        text = await resp.text()
                        if text.strip():
                            logger.info(f"📤 Заказ {order_id} отправлен в 1С: ответ={text.strip()}")
                            return True, f"Документ №{text.strip()} создан"
                        else:
                            return False, "Пустой ответ от 1С"
                else:
                    text = await resp.text()
                    return False, f"HTTP {resp.status}: {text[:200]}"

    except asyncio.TimeoutError:
        return False, "⏰ Таймаут подключения к 1С (30 сек)"
    except aiohttp.ClientConnectionError:
        return False, "🔌 Нет соединения с 1С (проверьте URL и доступность)"
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в 1С: {e}", exc_info=True)
        return False, f"Ошибка: {str(e)}"


async def send_to_1c(
    order_id: int,
    phone: str,
    breed: str,
    quantity: int,
    price: float,
    action: str = "issue"
) -> Tuple[bool, str]:
    """
    Обёртка для отправки в 1С.
    Сейчас используется только при выдаче (issue).
    """
    if action != "issue":
        logger.debug(f"ERP: action='{action}' skipped for order {order_id}")
        return False, f"Action skipped: '{action}' not supported"
    
    return await send_order_to_1c(order_id, breed, quantity, price)


# === 🔧 Диагностика 1С: команда /getib ===

async def get_ib_parameters() -> tuple[bool, str]:
    """
    Возвращает текущие параметры подключения к 1С.
    Для диагностики командой /getib.
    """
    try:
        start_time = asyncio.get_event_loop().time()
        is_available = await _check_connection()
        end_time = asyncio.get_event_loop().time()

        params = {
            "ERP_HTTP_URL": HTTP_URL,
            "ERP_USERNAME": USERNAME,
            "Configured": "✅ Да" if all([HTTP_URL, USERNAME, PASSWORD]) else "❌ Нет",
            "Available": "🟢 Доступен" if is_available else "🔴 Недоступен",
            "Response Time": f"{end_time - start_time:.2f} sec"
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
                return resp.status in (200, 405, 401, 403)
    except Exception as e:
        logger.debug(f"❌ Сервер 1С недоступен: {e}")
        return False
