"""
🚀 ДИАГНОСТИКА: Что реально происходит с python-telegram-bot?
"""

import sys
import os
import inspect

print("📍 Python executable:", sys.executable)
print("📍 Рабочая директория:", os.getcwd())
print()

# --- Поиск telegram.py ---
print("🔍 Поиск файлов telegram.py в проекте...")
found = False
for root, dirs, files in os.walk("."):
    for file in files:
        if file.lower() == "telegram.py":
            found = True
            print(f"❌ НАЙДЕН: {os.path.join(root, file)} — УДАЛИТЕ!")
if found:
    print("❌ УДАЛИТЕ эти файлы и перезапустите.")
    sys.exit(1)
else:
    print("✅ Файлов telegram.py не найдено")
print()

# --- Импорт и проверка ---
try:
    import telegram
    print(f"✅ telegram импортирован: {getattr(telegram, '__version__', 'неизвестно')}")
    print(f"📍 Путь: {telegram.__file__}")
    print(f"📍 Тип: {type(telegram)}")
    print()

    # --- Проверим, откуда импортируется ---
    if "site-packages" not in telegram.__file__:
        print("🚨 ВАЖНО: telegram импортирован НЕ из site-packages!")
        print("❌ Возможно, у вас переопределён sys.path или есть конфликт.")
        sys.exit(1)

    # --- Проверим ConversationHandler ---
    from telegram.ext import ConversationHandler
    print("✅ Успешно импортирован ConversationHandler")

    # Проверим параметры __init__
    sig = inspect.signature(ConversationHandler.__init__)
    params = list(sig.parameters.keys())
    print(f"\n📋 Параметры ConversationHandler.__init__:")
    for param in params:
        print(f"  - {param}")

    # Проверим нужные параметры
    required = ['conversation_timeout', 'timeout_handler']
    print("\n🔍 Проверка ключевых параметров:")
    for req in required:
        if req in params:
            print(f"✅ Есть параметр: {req}")
        else:
            print(f"❌ НЕТ параметра: {req}")

    # Проверим путь
    expected_in = os.path.join("venv", "Lib", "site-packages", "telegram")
    if expected_in.replace("/", "\\") in telegram.__file__:
        print(f"✅ Путь соответствует виртуальному окружению")
    else:
        print(f"⚠️ Путь НЕ из виртуального окружения: {telegram.__file__}")

except ImportError as e:
    print("❌ Ошибка импорта:", e)
    sys.exit(1)
except Exception as e:
    print("❌ Неизвестная ошибка:", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# === Если всё ок — попробуем создать Application ===
print("\n✅ ВСЁ В ПОРЯДКЕ. Попытка создать Application...")

try:
    from telegram.ext import Application
    app = Application.builder().token("FAKE:TOKEN").build()
    print("✅ Application успешно создан — библиотека работает корректно.")
    print("🟢 БОТ ДОЛЖЕН ЗАПУСТИТЬСЯ. ОШИБКА В КОДЕ ИЛИ КЭШЕ.")
except Exception as e:
    print("❌ Ошибка при создании Application:", e)
    import traceback
    traceback.print_exc()