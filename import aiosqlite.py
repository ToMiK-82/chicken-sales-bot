import aiosqlite

async def create_orders_table():
    async with aiosqlite.connect("database.sqlite") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                breed TEXT NOT NULL,
                date DATE NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                phone TEXT NOT NULL
            )
            """
        )
        await db.commit()

# Запустите скрипт через asyncio
import asyncio
asyncio.run(create_orders_table())

