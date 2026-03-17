import asyncio
import httpx

async def test_proxy(proxy_url):
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=20.0,
            verify=False  # временно
        ) as client:
            r = await client.get("https://api.telegram.org/bot8517673617:AAGSsm2b3rcpKlLUd6QY1XHqFTCKQMeKmsE/getMe")
            print("✅ OK:", r.json())
    except Exception as e:
        print("❌ Ошибка:", e)

# Замени на свой прокси
proxy = "socks5://194.135.84.47:1080"

asyncio.run(test_proxy(proxy))
