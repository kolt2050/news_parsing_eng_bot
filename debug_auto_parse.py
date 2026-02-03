import asyncio
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.translator import check_libretranslate_status
from app.scraper import scrape_all_sources
from app.database import init_db, get_pending_count, get_news_count

async def main():
    print("Checking LibreTranslate status...")
    status = await check_libretranslate_status()
    print(f"LibreTranslate Status: {status}")
    
    if not status:
        print("WARNING: LibreTranslate is offline. Auto-parser will use English fallbacks.")
        # return  <-- Removed return to allow testing scraper

    print("\nChecking Database...")
    await init_db()
    count = await get_news_count()
    pending = await get_pending_count()
    print(f"Total News: {count}")
    print(f"Pending News: {pending}")
    
    print("\nTesting Scraper (Dry Run)...")
    try:
        items = await scrape_all_sources()
        print(f"Scraper found {len(items)} items")
        for i, item in enumerate(items[:3]):
            print(f"  {i+1}. {item.title} ({item.source})")
    except Exception as e:
        print(f"Scraper Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
