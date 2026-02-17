# utils/erp.py
import aiohttp
import asyncio
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# ✅ URL HTTP-сервиса (обрати внимание: /Order, а не /CreateOrder)
HTTP_URL = "http://194.28.90.23:9999/ka/hs/sales_bot/Order"

# ✅ Данные для Basic Auth
USERNAME = "Python"
PASSWORD = "Serafima"

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

    auth = aiohttp.BasicAuth(USERNAME, PASSWORD)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                HTTP_URL,
                json=data,
                auth=auth,
                timeout=30
            ) as resp:

                if resp.status == 200:
                    # Пытаемся прочитать как JSON
                    try:
                        result = await resp.json()
                        if result.get("success"):
                            doc_number = result.get("doc_number", "неизвестно")
                            return True, f"Документ №{doc_number} создан"
                        else:
                            return False, "Ошибка: success=false"
                    except:
                        # Если не JSON, то просто текст (номер документа)
                        text = await resp.text()
                        return True, f"Документ №{text} создан"
                else:
                    text = await resp.text()
                    return False, f"HTTP {resp.status}: {text[:200]}"

    except asyncio.TimeoutError:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


async def send_to_1c(order_id: int, phone: str, breed: str, quantity: int, price: float = 85.0, action: str = "issue") -> Tuple[bool, str]:
    if action != "issue":
        return True, "Skipped"
    return await send_order_to_1c(order_id, breed, quantity, price)