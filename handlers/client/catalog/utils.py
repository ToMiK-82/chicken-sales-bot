"""Вспомогательные утилиты: очистка, описание пород, изображения, даты."""

from datetime import datetime
import os
from telegram import Update
from telegram.ext import ContextTypes
from html import escape
from config.buttons import BREED_EMOJI, BREEDS
from database.repository import db
from utils.messaging import safe_reply

# === Описания пород ===
BREED_DESCRIPTIONS = {
    "Бройлер": (
        "<b>🍗 Бройлер</b>\n\n"
        "Высокопродуктивный гибрид мясных кур. Быстро набирает массу: 2,7–2,9 кг за 35–40 дней.\n"
        "Выход мяса — до 75%. Идеален для мясного производства."
    ),
    "Мясо-яичная": (
        "<b>🥚 Мясо-яичная</b>\n\n"
        "Универсальный гибрид: хорошая яйценоскость (до 250 яиц/год) и неплохой набор массы.\n"
        "Подходит для фермеров с разнонаправленным хозяйством."
    ),
    "Несушка": (
        "<b>🪺 Несушка</b>\n\n"
        "Одна из самых продуктивных пород: до 300 яиц в год.\n"
        "Хорошо переносит разные условия содержания."
    ),
    "Индейка": (
        "<b>🦃 Индейка</b>\n\n"
        "Крупная птица с диетическим мясом. Используется в промышленности и на праздниках.\n"
        "Высокое содержание белка, низкий жир."
    ),
    "Утка": (
        "<b>🦆 Утка</b>\n\n"
        "Универсальная птица: устойчива к болезням, хорошо переносит холод.\n"
        "Популярные породы: мускусная, Пекинская."
    ),
    "Гусь": (
        "<b>🦢 Гусь</b>\n\n"
        "Мясо с насыщенным вкусом и высоким содержанием жира.\n"
        "Используется для гусиного масла и субпродуктов."
    ),
}

# === Изображения ===
BREED_IMAGES = {
    "Бройлер": "images/broiler.jpg",
    "Мясо-яичная": "images/layer.jpg",
    "Несушка": "images/layer.jpg",
    "Индейка": "images/turkey.jpg",
    "Утка": "images/duck.jpg",
    "Гусь": "images/goose.jpg",
}


def get_today_str():
    """Текущая дата в формате YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


async def send_breed_info(update: Update, breed: str, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет описание породы с фото (если есть)."""
    try:
        image_path = BREED_IMAGES.get(breed)
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=BREED_DESCRIPTIONS[breed], parse_mode="HTML")
        else:
            await update.message.reply_text(BREED_DESCRIPTIONS[breed], parse_mode="HTML")
    except Exception as e:
        from logging import getLogger
        logger = getLogger(__name__)
        logger.error(f"Ошибка отправки фото {breed}: {e}")
        await update.message.reply_text(BREED_DESCRIPTIONS[breed], parse_mode="HTML")


def clear_catalog_data(context: ContextTypes.DEFAULT_TYPE):
    """Очищает данные каталога, НО сохраняет доверенный номер."""
    keys_to_clear = [
        "selected_breed", "selected_incubator", "selected_date", "selected_quantity",
        "selected_price", "available_quantity", "available_dates", "available_incubators",
        "available_breeds",
        "navigation_stack", "confirmation_sent", "_order_in_progress"
        # ❌ УДАЛЕНО: "phone", "phone_verified", "saved_phone"
        # Они остаются, чтобы при следующем заказе номер подставлялся автоматически
    ]
    for key in keys_to_clear:
        context.user_data.pop(key, None)