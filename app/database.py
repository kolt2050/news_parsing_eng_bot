"""
Database layer for news storage using SQLite with aiosqlite.
"""
import aiosqlite
from datetime import datetime
from typing import Optional
from pathlib import Path

DATABASE_PATH = Path("/app/data/news.db")


async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                title TEXT UNIQUE NOT NULL,
                summary_ru TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                sent_to_telegram INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def add_news(
    title: str,
    summary_ru: str,
    source_url: str,
    source_name: str
) -> bool:
    """
    Add a news item to the database.
    Returns True if added, False if duplicate (title already exists).
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO news (date, title, summary_ru, source_url, source_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (datetime.now().isoformat(), title, summary_ru, source_url, source_name)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Duplicate title
            return False


async def check_if_exists(title: str) -> bool:
    """Check if a news item with the given title already exists."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM news WHERE title = ?",
            (title,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_all_news() -> list[dict]:
    """Get all news ordered by date (newest first)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM news ORDER BY date DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_unsent_news() -> Optional[dict]:
    """Get the latest news that hasn't been sent to Telegram."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM news 
            WHERE sent_to_telegram = 0 
            ORDER BY date DESC 
            LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def mark_as_sent(news_id: int) -> None:
    """Mark a news item as sent to Telegram."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE news SET sent_to_telegram = 1 WHERE id = ?",
            (news_id,)
        )
        await db.commit()


async def get_news_count() -> int:
    """Get total count of news in database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM news") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_pending_news() -> list[dict]:
    """Get all news that hasn't been sent to Telegram."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM news WHERE sent_to_telegram = 0 ORDER BY date DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_sent_news() -> list[dict]:
    """Get all news that has been sent to Telegram."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM news WHERE sent_to_telegram = 1 ORDER BY date DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_pending_count() -> int:
    """Get count of unsent news."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM news WHERE sent_to_telegram = 0"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_sent_count() -> int:
    """Get count of sent news."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM news WHERE sent_to_telegram = 1"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def clear_all_news() -> int:
    """Clear all news from database. Returns count of deleted items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM news") as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0
        
        await db.execute("DELETE FROM news")
        await db.commit()
        return count
