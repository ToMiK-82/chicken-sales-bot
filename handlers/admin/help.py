# handlers/admin/help.py — улучшенная версия с полным описанием

from telegram import Update
from telegram.ext import ContextTypes

from utils.messaging import safe_reply
from utils.admin_helpers import admin_required
from config.buttons import (
    BTN_ADMIN_ADD_FULL,
    BTN_ADMIN_STOCKS_FULL,
    BTN_ADMIN_ORDERS_FULL,
    BTN_ADMIN_ISSUE_FULL,
    BTN_ADMIN_BROADCAST_FULL,
    BTN_ADMIN_STATS_FULL,
    BTN_ADMIN_PROMO_FULL,
    BTN_ADMIN_HELP_FULL,
    BTN_ADMIN_EXIT_FULL,
)

HELP_TEXT = """
📘 <b>Справка по админ-панели</b>

Добро пожаловать в систему управления продажами цыплят 🐣  
Вот все доступные функции и как ими пользоваться.

━━━━━━━━━━━━━━━━━━━━━━━━━━  
📋 <b>ОСНОВНЫЕ КОММЕНДЫ</b>  
━━━━━━━━━━━━━━━━━━━━━━━━━━  

/start — начать работу с ботом  
/admin — войти в админ-панель  
/adminhelp — эта справка  

━━━━━━━━━━━━━━━━━━━━━━━━━━  
🛠️ <b>АДМИН-МЕНЮ</b>  
━━━━━━━━━━━━━━━━━━━━━━━━━━  

🔹 <b>{add}</b>  
Добавить новую партию цыплят: порода, инкубатор, дата поставки, количество, цена.

🔹 <b>{stocks}</b>  
Просмотр всех активных партий. Можно:
- Ввести <code>поиск &lt;слово&gt;</code> — найти по породе или инкубатору
- Нажать «✏️ Изменить» — отредактировать количество или дату

🔹 <b>{orders}</b>  
Просмотр всех заказов клиентов:
- Статус: ожидает, выдан, отменён
- Фильтрация по дате
- Поиск по имени или номеру

🔹 <b>{issuance}</b>  
Оформление выдачи:
1. Введите имя клиента или номер заказа
2. Подтвердите выдачу
3. Клиент получит уведомление

🔹 <b>{broadcast}</b>  
Рассылка всем подписчикам:
- Текст, фото, видео
- Поддержка форматирования (HTML)
- Подтверждение перед отправкой

🔹 <b>{stats}</b>  
Статистика продаж:
- За день, неделю, месяц
- По породам
- Общая выручка и количество

🔹 <b>{promo}</b>  
Управление акциями:
- Добавить промокод
- Настроить скидку
- Установить срок действия

🔹 <b>{help}</b>  
Это сообщение. Всегда можно вызвать снова.

🔹 <b>{exit}</b>  
Вернуться в главное меню бота.

━━━━━━━━━━━━━━━━━━━━━━━━━━  
📌 <b>ФОРМАТЫ ВВОДА</b>  
━━━━━━━━━━━━━━━━━━━━━━━━━━  

📅 <b>Дата</b>: ДД-ММ-ГГГГ  
Пример: <code>15-03-2026</code>

🔢 <b>Количество</b>: целое число ≥ 0  
Не может быть меньше уже проданного.

💬 <b>Текстовые команды</b>:  
- <code>поиск бройлер</code> — поиск в остатках  
- <code>заказ 123</code> — быстрый поиск заказа

━━━━━━━━━━━━━━━━━━━━━━━━━━  
🔐 <b>Безопасность</b>  
━━━━━━━━━━━━━━━━━━━━━━━━━━  

- Все действия логируются
- Только для администраторов
""".format(
    add=BTN_ADMIN_ADD_FULL,
    stocks=BTN_ADMIN_STOCKS_FULL,
    orders=BTN_ADMIN_ORDERS_FULL,
    issuance=BTN_ADMIN_ISSUE_FULL,
    broadcast=BTN_ADMIN_BROADCAST_FULL,
    stats=BTN_ADMIN_STATS_FULL,
    promo=BTN_ADMIN_PROMO_FULL,
    help=BTN_ADMIN_HELP_FULL,
    exit=BTN_ADMIN_EXIT_FULL,
)
""" 
✅ Совет: используйте эмодзи в интерфейсе — они помогают быстрее находить нужное.
"""


@admin_required
async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /adminhelp — показывает подробную справку."""
    await safe_reply(
        update,
        context,
        HELP_TEXT,
        parse_mode="HTML"
    )
    # Больше не нужно: context.user_data["HANDLED"] = True
    # Управление состоянием — на уровне ConversationHandler