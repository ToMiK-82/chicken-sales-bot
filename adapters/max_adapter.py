"""
🚀 Встроенный MAX-адаптер — только для приёма вебхуков
Не требует config, bot, TOKEN — только FastAPI + core.handlers
"""
import sys
import os

# Добавляем корневую папку в путь, чтобы import работал
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(docs_url=None, redoc_url=None)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("📩 [MAX] Получено:", data)

        # Импортируем логику обработки
        from core.handlers import handle_message_from_messenger

        messenger = data.get("messenger", "max")
        user_id = str(data["user_id"])
        text = data["text"]
        chat_id = data["chat_id"]
        bot = None  # не используется в core/handlers

        response = await handle_message_from_messenger(messenger, user_id, text, chat_id, bot)
        print("📤 [MAX] Ответ:", response)

        return JSONResponse(response)

    except Exception as e:
        print(f"❌ Ошибка в max_adapter: {e}")
        return JSONResponse({"text": "Ошибка сервера. Попробуйте позже."})

if __name__ == "__main__":
    print("🚀 MAX-адаптер запущен на http://194.28.90.23:9999/webhook")
    uvicorn.run(
        "adapters.max_adapter:app",   # путь к приложению
        host="0.0.0.0",               # слушает все интерфейсы
        port=9999,                    # именно этот порт!
        reload=False                  # отключаем авто-перезагрузку (для продакшена)
    )

