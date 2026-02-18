@echo off
:: === Остановка бота chicken-sales-bot ===
set BOT_DIR=F:\bots\chicken-sales-bot

echo [🛑] Останавливаю бота...

taskkill /f /im python.exe >nul 2>&1

:: Проверка, остался ли процесс
timeout /t 2 /nobreak >nul
wmic process where "name='python.exe' and commandline like '%%chicken-sales-bot%%'" get commandline >nul
if %errorlevel% equ 0 (
    echo ⚠️ Бот всё ещё работает. Попробуйте вручную.
) else (
    echo ✅ Бот остановлен.
)

pause
