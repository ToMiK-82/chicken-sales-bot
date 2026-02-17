"""
Утилиты для генерации клавиатур.
Динамически загружает породы из БД, с fallback на старые данные.
"""

from typing import List, Optional
import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton

# Локальный импорт — чтобы не было проблем с порядком инициализации
from config.buttons import BREEDS, BREED_EMOJI, with_emoji, BACK_BUTTON


logger = logging.getLogger(__name__)


async def get_available_breeds_from_db() -> List[str]:
    """
    Загружает список уникальных пород с остатками и актуальной датой.
    Возвращает пустой список при ошибках или если БД ещё не инициализирована.
    """
    try:
        from database.repository import db  # Отложенная загрузка — безопасно

        if not db.conn:
            logger.warning("⚠️ Попытка загрузить породы до инициализации БД — возвращаем пустой список")
            return []

        rows = await db.execute_read("""
            SELECT DISTINCT breed
            FROM stocks
            WHERE available_quantity > 0
              AND status = 'active'
              AND date >= DATE('now')
            ORDER BY breed
        """)

        breeds = [row["breed"] for row in rows]
        logger.info(f"✅ Успешно загружено {len(breeds)} пород из БД")
        return breeds

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки пород из БД: {e}", exc_info=True)
        return []


async def get_breeds_keyboard(bot_data: Optional[dict] = None) -> ReplyKeyboardMarkup:
    """
    Генерирует клавиатуру с доступными породами.
    
    Приоритет:
    1. Актуальные породы из БД (с остатками и будущей датой)
    2. Кэш из bot_data['available_breeds'] (на случай временной ошибки БД)
    3. Статичный список BREEDS (финальный fallback)

    Args:
        bot_data: словарь из application.bot_data (может не содержать available_breeds)

    Returns:
        ReplyKeyboardMarkup с кнопками пород и "Назад"
    """
    breeds = []

    # 1. Пытаемся получить актуальные данные из БД
    try:
        breeds = await get_available_breeds_from_db()
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить породы из БД: {e}")

    # 2. Fallback: кэш из bot_data (если есть)
    if not breeds and isinstance(bot_data, dict):
        cached = bot_data.get("available_breeds", [])
        if cached:
            logger.info(f"🔁 Используем кэшированные породы из bot_data: {len(cached)} шт.")
            breeds = cached

    # 3. Fallback: статичный список
    if not breeds:
        logger.info("🔁 Используем статичный список BREEDS как fallback")
        breeds = BREEDS

    # Фильтрация и сортировка
    unique_breeds = sorted({b for b in breeds if b in BREED_EMOJI})

    if not unique_breeds:
        logger.warning("⚠️ Нет доступных пород для отображения")
        return ReplyKeyboardMarkup(
            [["Нет доступных пород"]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

    # Формируем кнопки по 3 в ряд
    buttons = []
    row = []
    for breed in unique_breeds:
        row.append(KeyboardButton(with_emoji(breed, BREED_EMOJI)))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Добавляем кнопку "Назад"
    buttons.append([BACK_BUTTON])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )