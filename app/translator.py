"""
LibreTranslate integration for English to Russian translation.
"""
import os
import httpx
from typing import Optional

LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "http://libretranslate:5000")


async def translate_to_russian(text: str) -> str:
    """
    Translate English text to Russian using LibreTranslate.
    Falls back to original text if translation fails.
    """
    if not text:
        return text
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{LIBRETRANSLATE_URL}/translate",
                json={
                    "q": text,
                    "source": "en",
                    "target": "ru",
                    "format": "text"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("translatedText", text)
            else:
                print(f"Translation error: {response.status_code} - {response.text}")
                return text
                
    except httpx.TimeoutException:
        print("Translation timeout")
        return text
    except Exception as e:
        print(f"Translation error: {e}")
        return text


async def check_libretranslate_status() -> bool:
    """Check if LibreTranslate service is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{LIBRETRANSLATE_URL}/languages")
            return response.status_code == 200
    except Exception:
        return False
