# database/repository.py
"""
Управление базой данных: таблицы, миграции, индексы, CRUD-операции.
✅ Асинхронный доступ через aiosqlite
✅ Транзакции, миграции, индексы
✅ Управление админами, номерами, акциями
✅ Безопасный парсинг дат
✅ Полная поддержка каталога и заказов
✅ DB_PATH загружается из .env
✅ Поддержка users и user_actions для отчётов
✅ trust_phone() теперь с user_id
✅ get_trusted_phone_for_user() добавлен
✅ Исправлен семафор: asyncio.Semaphore
✅ 🎯 НОВОЕ: акции с датами начала и окончания
✅ ✅ add_promotion() — с is_active=1 и updated_at
✅ 🆕 set_promotion_active(), get_all_promotions()
✅ 🧼 Удалены дубли и логические ошибки
✅ ❌ УДАЛЕНА: таблица schedule (не используется)
"""

import os
import aiosqlite
import logging
import asyncio
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- Загружаем переменные окружения ---
load_dotenv()

# ✅ Единый путь к БД — теперь доступен для импорта
DB_PATH = os.getenv("DB_PATH", "chicken_sales.db")

logger = logging.getLogger(__name__)

__all__ = ["db", "init_db", "close_db", "DB_PATH"]


class DB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.conn = None
        self.semaphore = asyncio.Semaphore(1)  # Защита от параллельных транзакций

    async def connect(self):
        """Устанавливает соединение с базой данных"""
        try:
            if not os.path.exists(self.db_path):
                logger.info(f"Создаём новую базу данных: {self.db_path}")
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row  # Доступ по имени колонки
            # 🔥 Включаем WAL — уменьшает блокировки
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")
            logger.info(f"Подключение к БД '{self.db_path}' установлено")
            await self._create_tables()
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}", exc_info=True)
            raise

    async def _create_tables(self):
        """Создаёт таблицы при первом запуске"""
        if not self.conn:
            raise ConnectionError("Соединение с БД не установлено")

        try:
            # === Пользователи ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    username TEXT,
                    phone TEXT,
                    language_code TEXT DEFAULT 'ru',
                    created_at TEXT DEFAULT (datetime('now')),
                    last_active TEXT DEFAULT (datetime('now'))
                )
            ''')

            # === Партии кур ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    breed TEXT NOT NULL,
                    incubator TEXT NOT NULL DEFAULT 'Ленинский',
                    date DATE NOT NULL,
                    quantity INTEGER NOT NULL,
                    available_quantity INTEGER NOT NULL CHECK (available_quantity >= 0),
                    price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                )
            ''')

            # === Заказы ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    breed TEXT NOT NULL,
                    date DATE NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    stock_id INTEGER NOT NULL,
                    incubator TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            # === Действия пользователей (для отчётов) ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_id INTEGER,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            # === Администраторы ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # === Попытки заказа ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS phone_attempts (
                    phone TEXT PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP,
                    blocked_until TIMESTAMP NULL
                )
            ''')

            # === Заблокированные номера ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS blocked_phones (
                    phone TEXT PRIMARY KEY,
                    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT,
                    blocked_until TIMESTAMP NULL
                )
            ''')

            # === Доверенные номера (с привязкой к user_id) ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS trusted_phones (
                    phone TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    marked_by INTEGER,
                    marked_at TIMESTAMP NOT NULL,
                    source TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            # === 🎯 Акции (с датами начала и окончания) ===
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS promotions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    image_url TEXT,
                    is_active INTEGER DEFAULT 1,
                    start_date DATE,
                    end_date DATE,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            ''')

            await self.conn.commit()
            logger.info("Все таблицы созданы или уже существуют")
            await self._run_migrations()

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}", exc_info=True)
            await self.conn.rollback()
            raise

    async def _run_migrations(self):
        """Применяет миграции для совместимости"""
        try:
            # stocks: incubator
            async with self.conn.execute("PRAGMA table_info(stocks)") as cursor:
                cols = [c[1] for c in await cursor.fetchall()]
            if 'incubator' not in cols:
                await self.conn.execute("ALTER TABLE stocks ADD COLUMN incubator TEXT NOT NULL DEFAULT 'Ленинский'")
                logger.info("✅ Миграция: добавлен incubator в stocks")

            # orders: updated_at, incubator, confirmed_at, status default pending
            async with self.conn.execute("PRAGMA table_info(orders)") as cursor:
                cols = [c[1] for c in await cursor.fetchall()]

            if 'updated_at' not in cols:
                await self.conn.execute("ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("✅ Миграция: добавлен updated_at в orders")
            if 'incubator' not in cols:
                await self.conn.execute("ALTER TABLE orders ADD COLUMN incubator TEXT")
                logger.info("✅ Миграция: добавлен incubator в orders")
            if 'confirmed_at' not in cols:
                await self.conn.execute("ALTER TABLE orders ADD COLUMN confirmed_at TIMESTAMP")
                logger.info("✅ Миграция: добавлен confirmed_at в orders")

            # ✅ ИСПРАВЛЕНО: проверка DEFAULT для status
            if 'status' in cols:
                cursor = await self.conn.execute(
                    "SELECT dflt_value FROM pragma_table_info('orders') WHERE name = 'status'"
                )
                row = await cursor.fetchone()
                if row is None or row[0] != 'pending':
                    logger.warning("⚠️ Пересоздаём orders с status DEFAULT 'pending'")
                    await self.conn.executescript('''
                        CREATE TABLE IF NOT EXISTS orders_backup AS SELECT * FROM orders;
                        DROP TABLE orders;
                        CREATE TABLE orders (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            phone TEXT NOT NULL,
                            breed TEXT NOT NULL,
                            date DATE NOT NULL,
                            quantity INTEGER NOT NULL,
                            price REAL NOT NULL,
                            stock_id INTEGER NOT NULL,
                            incubator TEXT,
                            status TEXT NOT NULL DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            confirmed_at TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        );
                        INSERT INTO orders SELECT id, user_id, phone, breed, date, quantity, price, stock_id, incubator, status, created_at, updated_at, confirmed_at FROM orders_backup;
                        DROP TABLE orders_backup;
                    ''')
                    logger.info("✅ Таблица orders обновлена: status DEFAULT 'pending'")

            # users: phone, last_active
            async with self.conn.execute("PRAGMA table_info(users)") as cursor:
                cols = [c[1] for c in await cursor.fetchall()]
            if 'phone' not in cols:
                await self.conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
                logger.info("✅ Миграция: добавлен phone в users")
            if 'last_active' not in cols:
                await self.conn.execute("ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT (datetime('now'))")
                logger.info("✅ Миграция: добавлен last_active в users")

            # trusted_phones: user_id
            async with self.conn.execute("PRAGMA table_info(trusted_phones)") as cursor:
                cols = [c[1] for c in await cursor.fetchall()]
            if 'user_id' not in cols:
                logger.warning("⚠️ Пересоздаём trusted_phones с user_id (старые данные будут потеряны)")
                await self.conn.executescript('''
                    DROP TABLE IF EXISTS trusted_phones_backup;
                    ALTER TABLE trusted_phones RENAME TO trusted_phones_backup;
                    CREATE TABLE trusted_phones (
                        phone TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        marked_by INTEGER,
                        marked_at TIMESTAMP NOT NULL,
                        source TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    );
                ''')
                logger.info("✅ Таблица trusted_phones обновлена с user_id")

            # promotions: start_date, end_date, updated_at, is_active
            async with self.conn.execute("PRAGMA table_info(promotions)") as cursor:
                cols = [c[1] for c in await cursor.fetchall()]
            if 'start_date' not in cols:
                await self.conn.execute("ALTER TABLE promotions ADD COLUMN start_date DATE")
                logger.info("✅ Миграция: добавлен start_date в promotions")
            if 'end_date' not in cols:
                await self.conn.execute("ALTER TABLE promotions ADD COLUMN end_date DATE")
                logger.info("✅ Миграция: добавлен end_date в promotions")
            if 'updated_at' not in cols:
                await self.conn.execute("ALTER TABLE promotions ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
                logger.info("✅ Миграция: добавлен updated_at в promotions")
            if 'is_active' not in cols:
                await self.conn.execute("ALTER TABLE promotions ADD COLUMN is_active INTEGER DEFAULT 1")
                logger.info("✅ Миграция: добавлен is_active в promotions")

            await self.conn.commit()

        except Exception as e:
            logger.error(f"Ошибка миграций: {e}", exc_info=True)
            await self.conn.rollback()
            raise

    async def _create_indexes(self):
        """Создаёт индексы для оптимизации запросов"""
        try:
            await self.conn.executescript('''
                CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone);
                CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_stock_id ON orders(stock_id);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_stocks_status ON stocks(status);
                CREATE INDEX IF NOT EXISTS idx_stocks_breed_date ON stocks(breed, date);
                CREATE INDEX IF NOT EXISTS idx_blocked_phones ON blocked_phones(phone);
                CREATE INDEX IF NOT EXISTS idx_promotions_active ON promotions(is_active);
                CREATE INDEX IF NOT EXISTS idx_promotions_dates ON promotions(start_date, end_date);
                CREATE INDEX IF NOT EXISTS idx_user_actions_order ON user_actions(action, target_id);
                CREATE INDEX IF NOT EXISTS idx_user_actions_user ON user_actions(user_id, action);
                CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
                CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);
                CREATE INDEX IF NOT EXISTS idx_trusted_user ON trusted_phones(user_id);
            ''')
            await self.conn.commit()
            logger.info("✅ Индексы успешно созданы")
        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}", exc_info=True)
            await self.conn.rollback()

    async def execute_read(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        """Выполняет SELECT-запрос"""
        try:
            async with self.conn.execute(query, params) as cursor:
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка SELECT: {query} | {params} | {e}", exc_info=True)
            return []

    async def execute_write(self, query: str, params: tuple = ()) -> bool:
        """Выполняет запись (INSERT/UPDATE/DELETE)"""
        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(query, params)
            await self.conn.commit()
            # Для UPDATE/DELETE возвращаем True только если строки были изменены
            if query.strip().upper().startswith(("UPDATE", "DELETE")):
                return cursor.rowcount > 0
            return True
        except Exception as e:
            logger.error(f"Ошибка записи: {query} | {params} | {e}", exc_info=True)
            await self.conn.rollback()
            return False

    async def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> bool:
        """Выполняет транзакцию"""
        try:
            await self.conn.execute("BEGIN IMMEDIATE")
            for query, params in queries:
                await self.conn.execute(query, params)
            await self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка транзакции: {e}", exc_info=True)
            await self.conn.rollback()
            return False

    async def close(self):
        """Закрывает соединение"""
        if self.conn:
            try:
                await self.conn.close()
                logger.info("Соединение с БД закрыто")
            except Exception as e:
                logger.error(f"Ошибка закрытия БД: {e}", exc_info=True)
            finally:
                self.conn = None

    # === Вспомогательные методы ===

    def _parse_datetime(self, s: str) -> datetime:
        """Безопасный парсинг строки в datetime"""
        if not s:
            return datetime.min
        try:
            s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.split(".")[0], "%Y-%m-%d %H:%M:%S")
            except:
                logger.warning(f"Не удалось распарсить дату: {s}")
                return datetime.min

    # === УПРАВЛЕНИЕ АДМИНАМИ ===
    async def is_admin(self, user_id: int) -> bool:
        r = await self.execute_read("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return bool(r)

    async def add_admin(self, user_id: int, added_by: int) -> bool:
        return await self.execute_write(
            "INSERT OR REPLACE INTO admins (user_id, added_by, added_at) VALUES (?, ?, datetime('now'))",
            (user_id, added_by)
        )

    async def remove_admin(self, user_id: int) -> bool:
        return await self.execute_write("DELETE FROM admins WHERE user_id = ?", (user_id,))

    async def get_all_admins(self) -> List[aiosqlite.Row]:
        return await self.execute_read(
            "SELECT user_id, added_by, added_at FROM admins ORDER BY added_at DESC"
        )

    # === УПРАВЛЕНИЕ НОМЕРАМИ ===
    async def is_phone_blocked(self, phone: str) -> bool:
        r = await self.execute_read("SELECT blocked_until FROM blocked_phones WHERE phone = ?", (phone,))
        if not r:
            return False
        until = r[0]['blocked_until']
        if until is None:
            return True
        return self._parse_datetime(until) > datetime.now()

    async def block_phone(self, phone: str, reason: str, duration_hours: int = 24):
        until = None
        if duration_hours > 0:
            until = (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        await self.execute_write(
            "INSERT OR REPLACE INTO blocked_phones (phone, reason, blocked_until) VALUES (?, ?, ?)",
            (phone, reason, until)
        )

    async def get_daily_attempts(self, phone: str) -> int:
        r = await self.execute_read("SELECT attempts, last_attempt FROM phone_attempts WHERE phone = ?", (phone,))
        if not r:
            return 0
        attempts = r[0]['attempts']
        last = self._parse_datetime(r[0]['last_attempt'])
        if datetime.now() - last > timedelta(hours=24):
            await self.reset_attempt(phone)
            return 0
        return attempts

    async def add_attempt(self, phone: str):
        await self.execute_write("""
            INSERT INTO phone_attempts (phone, attempts, last_attempt)
            VALUES (?, 1, datetime('now'))
            ON CONFLICT(phone) DO UPDATE SET
                attempts = attempts + 1,
                last_attempt = datetime('now')
        """, (phone,))

    async def reset_attempt(self, phone: str):
        await self.execute_write("DELETE FROM phone_attempts WHERE phone = ?", (phone,))

    async def is_trusted_phone(self, phone: str) -> bool:
        r = await self.execute_read("SELECT 1 FROM trusted_phones WHERE phone = ?", (phone,))
        return bool(r)

    async def trust_phone(self, phone: str, user_id: int):
        """
        Делает номер доверенным и привязывает к пользователю.
        Вызывается после успешного заказа.
        """
        now = datetime.now().isoformat()
        await self.execute_write("""
            INSERT OR REPLACE INTO trusted_phones (phone, user_id, marked_by, marked_at, source)
            VALUES (?, ?, NULL, ?, 'auto')
        """, (phone, user_id, now))

    async def get_trusted_phone_for_user(self, user_id: int) -> Optional[str]:
        """
        Возвращает доверенный номер пользователя.
        """
        row = await self.execute_read(
            "SELECT phone FROM trusted_phones WHERE user_id = ?",
            (user_id,)
        )
        return row[0]["phone"] if row else None

    async def mark_phone_as_trusted(self, phone: str, admin_id: int, user_id: int):
        """
        Админ вручную помечает номер как доверенный.
        """
        now = datetime.now().isoformat()
        await self.execute_write("""
            INSERT OR REPLACE INTO trusted_phones (phone, user_id, marked_by, marked_at, source)
            VALUES (?, ?, ?, ?, 'admin')
        """, (phone, user_id, admin_id, now))

    async def unmark_trusted_phone(self, phone: str):
        await self.execute_write("DELETE FROM trusted_phones WHERE phone = ?", (phone,))

    # === УПРАВЛЕНИЕ ПАРТИЯМИ ===
    async def get_stock_id(self, breed: str, incubator: str, date: str) -> Optional[int]:
        r = await self.execute_read(
            "SELECT id FROM stocks WHERE breed = ? AND incubator = ? AND date = ? AND status = 'active'",
            (breed, incubator, date))
        return r[0]['id'] if r else None

    async def get_stock_by_id(self, stock_id: int) -> Optional[aiosqlite.Row]:
        r = await self.execute_read("SELECT * FROM stocks WHERE id = ? AND status = 'active'", (stock_id,))
        return r[0] if r else None

    async def get_available_stocks(self, breed: str = None) -> List[aiosqlite.Row]:
        query = """SELECT id, breed, incubator, date, available_quantity, price
                   FROM stocks WHERE status = 'active' AND available_quantity > 0"""
        params = ()
        if breed:
            query += " AND breed = ?"
            params = (breed,)
        query += " ORDER BY date ASC"
        return await self.execute_read(query, params)

    # === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===
    async def upsert_user(self, user_id: int, full_name: str, username: str = None, phone: str = None):
        await self.execute_write('''
            INSERT OR REPLACE INTO users (user_id, full_name, username, phone, last_active)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = COALESCE(exCLUDED.username, users.username),
                phone = COALESCE(EXCLUDED.phone, users.phone),
                last_active = datetime('now')
        ''', (user_id, full_name, username, phone))

    # === ОФОРМЛЕНИЕ ЗАКАЗА ===
    async def create_order(
        self,
        user_id: int,
        phone: str,
        stock_id: int,
        quantity: int,
        price: float,
        breed: str,
        date: str,
        incubator: str,
        full_name: str,
        username: str = None
    ) -> Optional[int]:
        stock = await self.get_stock_by_id(stock_id)
        if not stock or stock['available_quantity'] < quantity:
            return None

        new_avail = stock['available_quantity'] - quantity
        queries = [
            (
                "INSERT INTO orders (user_id, phone, breed, date, quantity, price, stock_id, incubator, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (user_id, phone, breed, date, quantity, price, stock_id, incubator)
            ),
            (
                "UPDATE stocks SET available_quantity = ? WHERE id = ?",
                (new_avail, stock_id)
            )
        ]
        success = await self.execute_transaction(queries)
        if not success:
            return None

        await self.upsert_user(user_id, full_name, username, phone)

        try:
            async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
                row = await cursor.fetchone()
                order_id = row[0] if row else None
        except Exception as e:
            logger.error(f"Ошибка получения ID заказа: {e}")
            order_id = None

        return order_id

    # === УПРАВЛЕНИЕ ЗАКАЗАМИ ===
    async def get_orders_by_user(self, user_id: int) -> List[aiosqlite.Row]:
        return await self.execute_read(
            "SELECT id, breed, date, incubator, quantity, price, status, created_at FROM orders WHERE user_id = ? AND status IN ('pending', 'active') ORDER BY created_at DESC",
            (user_id,))

    async def get_order_by_id(self, order_id: int) -> Optional[aiosqlite.Row]:
        r = await self.execute_read("SELECT * FROM orders WHERE id = ?", (order_id,))
        return r[0] if r else None

    # === УПРАВЛЕНИЕ АКЦИЯМИ ===

    async def get_active_promotions(self) -> List[aiosqlite.Row]:
        """
        Возвращает активные акции, которые:
        - is_active = 1
        - start_date <= now (или NULL)
        - end_date >= now (или NULL)
        """
        query = """
            SELECT id, title, description, image_url, start_date, end_date
            FROM promotions
            WHERE is_active = 1
              AND (start_date IS NULL OR start_date <= date('now'))
              AND (end_date IS NULL OR end_date >= date('now'))
            ORDER BY end_date NULLS LAST, updated_at DESC
            LIMIT 10
        """
        return await self.execute_read(query)

    async def get_all_promotions(self) -> List[aiosqlite.Row]:
        """
        Возвращает все акции (активные и неактивные) — для админки.
        """
        query = """
            SELECT id, title, description, image_url, start_date, end_date, is_active, created_at, updated_at
            FROM promotions
            ORDER BY is_active DESC, updated_at DESC
        """
        return await self.execute_read(query)

    async def add_promotion(
        self,
        title: str,
        description: str,
        image_url: str = None,
        start_date: str = None,
        end_date: str = None,
        is_active: bool = True
    ) -> bool:
        """
        Добавляет новую акцию с is_active=1 и временем создания.
        :param start_date: 'YYYY-MM-DD' или None
        :param end_date: 'YYYY-MM-DD' или None
        :param is_active: активна ли акция
        :return: True, если успешно
        """
        query = """
            INSERT INTO promotions (
                title, description, image_url, is_active,
                start_date, end_date, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """
        try:
            success = await self.execute_write(
                query,
                (title, description, image_url, 1 if is_active else 0, start_date, end_date)
            )
            if success:
                logger.info(f"✅ Акция добавлена: {title} | {start_date} – {end_date or 'бессрочно'}")
            return success
        except Exception as e:
            logger.error(f"❌ Ошибка добавления акции: {e}", exc_info=True)
            return False

    async def update_promotion(self, promo_id: int, **updates) -> bool:
        """
        Обновляет акцию по ID.
        :param promo_id: ID акции
        :param updates: поля для обновления (title, description, image_url, start_date, end_date)
        :return: True, если обновлено
        """
        try:
            row = await self.execute_read("SELECT id FROM promotions WHERE id = ?", (promo_id,))
            if not row:
                logger.warning(f"Акция с ID {promo_id} не найдена")
                return False

            query = "UPDATE promotions SET updated_at = datetime('now')"
            params = []
            for field, value in updates.items():
                if field in ['title', 'description', 'image_url', 'start_date', 'end_date']:
                    query += f", {field} = ?"
                    params.append(value)

            query += " WHERE id = ?"
            params.append(promo_id)

            if len(params) == 1:
                return True  # ничего не обновлялось

            result = await self.execute_write(query, tuple(params))
            if result:
                logger.info(f"✅ Акция {promo_id} обновлена: {list(updates.keys())}")
            return result

        except Exception as e:
            logger.error(f"Ошибка при обновлении акции {promo_id}: {e}", exc_info=True)
            return False

    async def set_promotion_active(self, promo_id: int, active: bool) -> bool:
        """
        Активирует/деактивирует акцию.
        """
        try:
            result = await self.execute_write(
                "UPDATE promotions SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
                (int(active), promo_id)
            )
            if result:
                action = "✅ Активирована" if active else "🗑️ Деактивирована"
                logger.info(f"{action} акция ID {promo_id}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при изменении статуса акции {promo_id}: {e}", exc_info=True)
            return False

    async def delete_promotion(self, promo_id: int) -> bool:
        """
        Мягкое удаление акции — деактивирует, не удаляет из БД.
        """
        return await self.set_promotion_active(promo_id, False)

    async def get_promotion_by_id(self, promo_id: int) -> Optional[aiosqlite.Row]:
        """
        Получает акцию по ID (включая все поля).
        """
        r = await self.execute_read(
            "SELECT id, title, description, image_url, start_date, end_date, is_active, created_at, updated_at "
            "FROM promotions WHERE id = ?",
            (promo_id,)
        )
        return r[0] if r else None


# === Глобальный экземпляр ===
db = DB()


# === Инициализация и закрытие ===
async def init_db():
    """Инициализирует соединение с БД и создаёт таблицы."""
    try:
        await db.connect()
        logger.info("✅ База данных инициализирована и гidотова к работе")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка при инициализации БД: {e}", exc_info=True)
        raise


async def close_db():
    """Закрывает соединение с БД."""
    try:
        await db.close()
        logger.info("✅ Соединение с базой данных закрыто")
    except Exception as e:
        logger.critical(f"❌ Ошибка при закрытии БД: {e}", exc_info=True)
        raise