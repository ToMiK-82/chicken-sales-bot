from telegram import Update
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from config.buttons import (
    CONTACTS_BUTTON_TEXT,
    BTN_BACK_FULL,
    BTN_CANCEL_FULL,
    get_main_keyboard,
)
from utils.messaging import safe_reply
import os
import logging

logger = logging.getLogger(__name__)

# === Константы ===
IMAGE_PATH = "images/zootopia.jpg"
WEBSITE_URL = "https://zootopia.ru"  # Проверьте протокол!

# === Состояние ===
CONTACTS_VIEW = 0

# === Глобальный обработчик для startup_check ===
contacts_handler = None

def make_tel_link(phone: str) -> str:
    """Преобразует номер в кликабельный формат tel:+7..."""
    cleaned = phone.replace(" ", "").replace("-", "").replace("+", "")
    return f"tel:+7{cleaned}"

async def contacts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Формируем сообщение с native tel: ссылками
        message = (
            "Наша компания предлагает широкий ассортимент товаров для сельскохозяйственных животных и домашних питомцев,\n"
            "включая корма, аксессуары, игрушки и товары для рыбалки 😊.\n\n"
            "📩 Чтобы связаться с менеджером:\n"
            "🌍 Крым\n"
            f"- Лилия 📞 {make_tel_link('+7 978 061 25 52')}\n"
            "  Региональный склад, Красногвардейский район, с. Полтавка, ул. Строителей, 15;\n"
            f"- Давид 📞 {make_tel_link('+7 978 589 93 07')}\n"
            "  Сакский, Черноморский, Раздольненский, Первомайский, Красноперекопский и Джанкойский районы;\n"
            f"- Павел 📞 {make_tel_link('+7 978 589 93 15')}\n"
            "  Красногвардейский, Нижнегорский, Советский, Кировский, Белогорский и Ленинский районы;\n"
            f"- Денис 📞 {make_tel_link('+7 978 697 43 09')}\n"
            "  Симферопольский и Бахчисарайский районы, г. Севастополь и ЮБК.\n\n"
            "🌍 Херсонская область\n"
            f"- Андрей 📞 {make_tel_link('+7 978 589 91 67')}\n\n"
            "🌍 Запорожская область\n"
            f"- Павел 📞 {make_tel_link('+7 990 144 36 63')}\n"
            "  Региональный склад, Запорожская область, г. Мелитополь, Каховское шоссе, 24/2;\n\n"
            f"- Вадим 📞 {make_tel_link('+7 990 144 70 03')}\n\n"
            "📞 Если нужна помощь с выбором или расчётом объёма — просто начните оформление, и мы поможем!\n\n"
            f"🌐 Полный ассортимент на сайте — <a href='{WEBSITE_URL}'>ZOOTOPIA.RU</a>"
        )

        # Проверяем наличие изображения
        if os.path.exists(IMAGE_PATH):
            try:
                with open(IMAGE_PATH, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=message,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                logger.info(f"🖼️ Отправлено фото и контакты пользователю {update.effective_user.id}")
            except Exception as e:
                logger.warning(f"❌ Не удалось отправить фото: {e}")
                # Отправляем текст при ошибке
                await safe_reply(
                    update,
                    context,
                    message,
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return ConversationHandler.END
        else:
            # Отправляем текст без фото
            await safe_reply(
                update,
                context,
                message,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"❌ Ошибка при отображении контактов: {e}", exc_info=True)
        await safe_reply(
            update,
            context,
            "⚠️ Произошла ошибка при загрузке информации.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

    return ConversationHandler.END

async def fallback_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Безопасный выход из просмотра контактов."""
    await safe_reply(
        update,
        context,
        "🚪 Просмотр контактов завершён.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    return ConversationHandler.END

def register_contacts_handler(application):
    """Регистрирует обработчик '📞 Контакты' в group=1."""
    global contacts_handler
    contacts_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Text([CONTACTS_BUTTON_TEXT]),
                contacts_command
            )
        ],
        states={},
        fallbacks=[
            CommandHandler("start", fallback_contacts),
            CommandHandler("cancel", fallback_contacts),
            MessageHandler(filters.COMMAND, fallback_contacts),
            MessageHandler(
                filters.Text([BTN_BACK_FULL, BTN_CANCEL_FULL]),
                fallback_contacts
            ),
        ],
        per_user=True,
        allow_reentry=True,
        name="contacts_handler"
    )

    application.add_handler(contacts_handler, group=1)
    logger.info(f"✅ Обработчик 'Контакты' зарегистрирован: '{CONTACTS_BUTTON_TEXT}' (group=1)")

__all__ = ["contacts_handler"]
