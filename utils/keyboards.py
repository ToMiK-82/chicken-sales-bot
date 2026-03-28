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
    Генерирует клавиатуру с породами, У КОТОРЫХ ЕСТЬ ДОСТУПНЫЕ ПАРТИИ.
    
    ВАЖНО:
    - Никакого fallback на кэш, если БД вернула [] (это не ошибка — это "нет в наличии")
    - Кэш используется ТОЛЬКО при ошибке подключения к БД
    - Статичный список BREEDS — только как крайний fallback
    """

    breeds = []
    use_fallback = False  # флаг: только если ошибка, а не пустой результат

    # 1. Актуальные данные из БД
    try:
        breeds = await get_available_breeds_from_db()
        # Если запрос прошёл, даже если пород нет → это нормально
        # Не используем fallback
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при загрузке пород из БД: {e}. Используем fallback.")
        use_fallback = True

    # 2. Fallback: только если была ошибка (не пустой список!)
    if not breeds and use_fallback:
        if isinstance(bot_data, dict) and bot_data.get("available_breeds"):
            cached = bot_data["available_breeds"]
            logger.info(f"🔁 Используем кэшированные породы из bot_data: {len(cached)} шт.")
            breeds = cached
        elif BREEDS:
            logger.info("🔁 Используем статичный список BREEDS как fallback")
            breeds = BREEDS

    # 3. Фильтрация: только породы, для которых есть эмодзи
    unique_breeds = sorted({b for b in breeds if b in BREED_EMOJI})

    if not unique_breeds:
        logger.info("🚫 Нет доступных пород для отображения")
        return None

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
