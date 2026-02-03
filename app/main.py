"""
FastAPI main application for AI News Parser.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.database import (
    init_db, add_news, get_all_news, get_unsent_news, mark_as_sent, 
    get_news_count, get_pending_news, get_sent_news, get_pending_count, get_sent_count,
    clear_all_news, check_if_exists
)
from app.scraper import scrape_all_sources
from app.translator import translate_to_russian, check_libretranslate_status
from app.telegram_bot import send_news_to_telegram

# Auto-send state
auto_send_task: Optional[asyncio.Task] = None
auto_send_running = False
last_auto_parse_stats = {"found": 0, "added": 0, "duplicates": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield
    # Cleanup
    global auto_send_task, auto_send_running
    auto_send_running = False
    if auto_send_task:
        auto_send_task.cancel()


app = FastAPI(title="AI News Parser", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page with news list."""
    news = await get_all_news()
    pending_news = await get_pending_news()
    sent_news = await get_sent_news()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "news": news,
            "pending_news": pending_news,
            "sent_news": sent_news,
            "auto_send_running": auto_send_running
        }
    )


@app.get("/api/news")
async def api_get_news():
    """Get all news as JSON."""
    news = await get_all_news()
    return {"news": news, "count": len(news)}


@app.post("/api/parse")
async def api_parse_news():
    """Parse news from all sources."""
    # Check LibreTranslate
    lt_status = await check_libretranslate_status()
    if not lt_status:
        print("Warning: LibreTranslate is unavailable. News will be saved in English.")
    
    # Check how many more we can add
    pending_count = await get_pending_count()
    max_to_add = max(0, 10 - pending_count)
    
    if max_to_add == 0:
        return {"message": "В базе уже 10 ожидающих новостей", "added": 0, "parsed": 0}
    
    # Scrape news
    scrape_result = await scrape_all_sources()
    news_items = scrape_result["items"]
    
    if not news_items:
        return {"message": "Новости не найдены", "added": 0}
    
    added_count = 0
    
    # Add news one by one up to limit
    for item in news_items:
        if added_count >= max_to_add:
            break
            
        # Translate summary (will fallback to original if offline)
        translated_summary = await translate_to_russian(item.summary)
        
        # Add to database
        added = await add_news(
            title=item.title,
            summary_ru=translated_summary,
            source_url=item.url,
            source_name=item.source
        )
        
        if added:
            added_count += 1
            
    # Update stats for auto-loop usage (even though this is manual)
    global last_auto_parse_stats
    last_auto_parse_stats = {
        "found": len(news_items),
        "added": added_count,
        "duplicates": len(news_items) - added_count, # Approx for manual
        "sources": scrape_result["sources"]
    }
    
    msg = f"Добавлено {added_count} новых новостей"
    if not lt_status:
        msg += " (переводчик недоступен)"
        
    return {
        "message": msg,
        "added": added_count,
        "parsed": len(news_items),
        "sources": scrape_result["sources"]
    }


@app.post("/api/send-telegram")
async def api_send_telegram():
    """Send the latest unsent news to Telegram."""
    news = await get_unsent_news()
    
    if not news:
        return JSONResponse(
            status_code=404,
            content={"error": "Нет новостей для отправки"}
        )
    
    success, message = await send_news_to_telegram(
        title=news["title"],
        summary=news["summary_ru"],
        source_url=news["source_url"],
        source_name=news["source_name"]
    )
    
    if success:
        await mark_as_sent(news["id"])
        return {"message": message, "sent_news": news["title"]}
    else:
        return JSONResponse(
            status_code=500,
            content={"error": message}
        )


async def auto_send_loop():
    """Background task for auto-parsing news when pending count < 10."""
    global auto_send_running, last_auto_parse_stats
    
    while auto_send_running:
        # Check if we need to parse more news
        pending_count = await get_pending_count()
        
        if pending_count < 10:
            # Calculate how many we need to add
            needed = 10 - pending_count
            print(f"Pending news: {pending_count}. Need {needed} more. Starting auto-parse...")
            
            # Check status mainly for logging
            lt_status = await check_libretranslate_status()
            if not lt_status:
                print("Auto-parse: LibreTranslate offline, using English.")
            
            try:
                scrape_result = await scrape_all_sources()
                news_items = scrape_result["items"]
                found_count = len(news_items)
                added = 0
                duplicates = 0
                
                # First pass: Check duplicates and count them
                # We need to process ALL items to get accurate stats
                for item in news_items:
                    # Check if exists
                    exists = await check_if_exists(item.title)
                    
                    if exists:
                        duplicates += 1
                    else:
                        # New item - add if we have space
                        if added < needed:
                            translated_summary = await translate_to_russian(item.summary)
                            await add_news(
                                title=item.title,
                                summary_ru=translated_summary,
                                source_url=item.url,
                                source_name=item.source
                            )
                            added += 1
                        # If we don't have space (added >= needed), we just skip adding
                        # but we still count it in "found" (and it's not a duplicate)
                
                last_auto_parse_stats = {
                    "found": found_count,
                    "added": added,
                    "duplicates": duplicates,
                    "sources": scrape_result["sources"]
                }
                print(f"Auto-parsed: found={found_count}, added={added}, duplicates={duplicates}")
            except Exception as e:
                print(f"Auto-parse error: {e}")
        
        await asyncio.sleep(30)


@app.post("/api/auto-send/start")
async def api_start_auto_send():
    """Start auto-sending news every 30 seconds."""
    global auto_send_task, auto_send_running
    
    if auto_send_running:
        return {"message": "Автоотправка уже запущена"}
    
    # Check if there are news to send
    count = await get_news_count()
    if count == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "Нет новостей в базе. Сначала выполните парсинг."}
        )
    
    auto_send_running = True
    auto_send_task = asyncio.create_task(auto_send_loop())
    
    return {"message": "Автоотправка запущена (каждые 30 секунд)"}


@app.post("/api/auto-send/stop")
async def api_stop_auto_send():
    """Stop auto-sending."""
    global auto_send_task, auto_send_running
    
    if not auto_send_running:
        return {"message": "Автоотправка не запущена"}
    
    auto_send_running = False
    if auto_send_task:
        auto_send_task.cancel()
        auto_send_task = None
    
    return {"message": "Автоотправка остановлена"}


@app.get("/api/status")
async def api_status():
    """Get current status."""
    lt_status = await check_libretranslate_status()
    news_count = await get_news_count()
    pending_count = await get_pending_count()
    sent_count = await get_sent_count()
    
    return {
        "libretranslate": "online" if lt_status else "offline",
        "news_count": news_count,
        "pending_count": pending_count,
        "sent_count": sent_count,
        "auto_send": auto_send_running,
        "parse_stats": last_auto_parse_stats
    }


@app.post("/api/clear")
async def api_clear_database():
    """Clear all news from database."""
    deleted = await clear_all_news()
    return {"message": f"Удалено {deleted} новостей из базы данных", "deleted": deleted}
