"""
Отправляет уведомление в DevOps-чат о предстоящей перезагрузке бота.
Запускается из update_and_restart.bat
"""
import httpx
import sys

def main():
    if len(sys.argv) != 3:
        print("❌ Usage: python notify_devops.py <token> <chat_id>")
        sys.exit(1)

    token = sys.argv[1].strip()
    chat_id = sys.argv[2].strip()

    text = (
        '⚠️ <b>Бот будет перезагружен</b>\n\n'
        'Через 2 минуты начнётся обновление.\n'
        'Пожалуйста, завершите все действия.'
    )

    url = f'https://api.telegram.org/bot{token}/sendMessage'

    try:
        resp = httpx.post(
            url,
            data={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            },
            timeout=10.0
        )
        if resp.status_code == 200:
            print('✅ Уведомление отправлено в DevOps')
        else:
            print(f'❌ Ошибка API Telegram: {resp.status_code}')
            print(f'Response: {resp.text}')
    except Exception as e:
        print(f'❌ Не удалось отправить уведомление: {e}')

if __name__ == "__main__":
    main()
