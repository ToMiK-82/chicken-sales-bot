@echo off
:: === Stop the chicken-sales-bot ===
set BOT_DIR=F:\bots\chicken-sales-bot

echo [🛑] Stopping the bot...

taskkill /f /im python.exe >nul 2>&1

:: Check if the process is still running
timeout /t 2 /nobreak >nul
wmic process where "name='python.exe' and commandline like '%%chicken-sales-bot%%'" get commandline >nul
if %errorlevel% equ 0 (
    echo ⚠️ Bot is still running. Try to stop manually.
) else (
    echo ✅ Bot stopped successfully.
)

pause
