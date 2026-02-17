@echo off
echo 📥 Скачивание Python 3.11.9 с GitHub...

:: Используем GitHub — он реже блокируется
powershell -Command "Invoke-WebRequest -Uri https://github.com/python/cpython/releases/download/v3.11.9/python-3.11.9-amd64.exe -OutFile python-installer.exe"

if %errorlevel% neq 0 (
    echo ❌ Не удалось скачать Python. Проверьте подключение.
    pause
    exit /b
)

echo 🛠 Установка Python... (тихий режим)
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

echo ⏳ Ожидание завершения установки...
timeout /t 30 /nobreak >nul

:: Проверка
python --version
if %errorlevel% == 0 (
    echo ✅ Python успешно установлен
) else (
    echo ❌ Ошибка установки Python. Добавьте в PATH вручную.
)

:: Удаляем установщик
del python-installer.exe

echo.
echo 🔄 Перезапустите CMD и продолжите установку
pause
