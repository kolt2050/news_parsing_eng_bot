"""
Telegram bot integration for sending news.
"""
import os
import httpx
from typing import Optional

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_news_to_telegram(
    title: str,
    summary: str,
    source_url: str,
    source_name: str
) -> tuple[bool, str]:
    """
    Send a news item to Telegram.
    Returns (success, message).
    """
    message = f"""📰 <b>{title}</b>

{summary}

🔗 <a href="{source_url}">Источник: {source_name}</a>"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
            )
            
            if response.status_code == 200:
                return True, "Сообщение отправлено"
            else:
                error_data = response.json()
                return False, f"Ошибка: {error_data.get('description', 'Unknown error')}"
                
    except httpx.TimeoutException:
        return False, "Таймаут при отправке"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"


async def check_telegram_bot() -> bool:
    """Check if Telegram bot token is valid."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{TELEGRAM_API_URL}/getMe")
            return response.status_code == 200
    except Exception:
        return False
