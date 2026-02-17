# test_1c.py
import asyncio
import logging
from utils.erp import send_order_to_1c

logging.basicConfig(level=logging.INFO)

async def main():
    print("📤 Создаём документ через HTTP-сервис...")
    result, message = await send_order_to_1c(
        order_id=999,
        breed="Бройлер",
        quantity=2,
        price=150.0
    )
    
    print(f"\n{'✅' if result else '❌'} Результат: {message}")

if __name__ == "__main__":
    asyncio.run(main())