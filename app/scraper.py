"""
News scraper using Playwright for TechCrunch, The Verge, and VentureBeat.
Visits each article page to extract real content.
"""
import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Browser


@dataclass
class NewsItem:
    """Represents a parsed news item."""
    title: str
    summary: str
    url: str
    source: str


def make_absolute_url(url: str, base_url: str) -> str:
    """Convert relative URL to absolute."""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return urljoin(base_url, url)


def extract_first_sentences(text: str, count: int = 3) -> str:
    """Extract first N sentences from text."""
    if not text:
        return ""
    # Clean up text
    text = re.sub(r'\s+', ' ', text.strip())
    # Split by sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = ' '.join(sentences[:count])
    # Limit length to 500 chars
    if len(result) > 500:
        result = result[:497] + "..."
    return result


async def get_article_content(page: Page, url: str, selectors: list[str]) -> str:
    """Visit article page and extract content."""
    try:
        await page.goto(url, timeout=20000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        
        # Try each selector to find article content
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    texts = []
                    for elem in elements[:5]:  # Get first 5 paragraphs
                        text = await elem.inner_text()
                        if text and len(text) > 30:
                            texts.append(text.strip())
                    if texts:
                        full_text = ' '.join(texts)
                        return extract_first_sentences(full_text, 3)
            except Exception:
                continue
        
        return ""
    except Exception as e:
        print(f"Error getting article content from {url}: {e}")
        return ""


async def scrape_techcrunch(browser: Browser) -> list[NewsItem]:
    """Scrape AI news from TechCrunch."""
    news_items = []
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await context.new_page()
    
    try:
        await page.goto(
            "https://techcrunch.com/category/artificial-intelligence/",
            timeout=30000
        )
        # Try multiple selectors for container
        article_selector = "article"
        for selector in ["div.wp-block-post", "div.loop-card__content", "article"]:
            try:
                if await page.query_selector(selector):
                    article_selector = selector
                    break
            except:
                continue
                
        await page.wait_for_selector(article_selector, timeout=10000)
        articles = await page.query_selector_all(article_selector)
        
        # Collect article info first
        article_data = []
        for article in articles[:20]:
            try:
                # Try multiple title selectors
                title_elem = await article.query_selector("h2.wp-block-post-title a, h2.loop-card__title a, h2 a, h3 a")
                if not title_elem:
                    continue
                    
                title = await title_elem.inner_text()
                url = await title_elem.get_attribute("href")
                
                if title and url:
                    article_data.append({
                        "title": title.strip(),
                        "url": make_absolute_url(url, "https://techcrunch.com")
                    })
            except Exception:
                continue
        
        # Now visit each article to get content
        content_selectors = [
            "article p",
            ".article-content p",
            ".post-content p",
            ".entry-content p"
        ]
        
        for data in article_data[:20]:
            summary = await get_article_content(page, data["url"], content_selectors)
            news_items.append(NewsItem(
                title=data["title"],
                summary=summary if summary else data["title"],
                url=data["url"],
                source="TechCrunch"
            ))
                
    except Exception as e:
        print(f"TechCrunch scraping error: {e}")
        return [], False
    finally:
        await context.close()
    
    return news_items, True


async def scrape_theverge(browser: Browser) -> list[NewsItem]:
    """Scrape AI news from The Verge."""
    news_items = []
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await context.new_page()
    
    try:
        await page.goto(
            "https://www.theverge.com/ai-artificial-intelligence",
            timeout=30000
        )
        # Try multiple selectors for container
        article_selector = "div[data-component='EntryBox'], article"
        for selector in ["div.duet--content-cards--content-card", "div[data-component='EntryBox'], article"]:
            try:
                if await page.query_selector(selector):
                    article_selector = selector
                    break
            except:
                continue
                
        await page.wait_for_selector(article_selector, timeout=10000)
        articles = await page.query_selector_all(article_selector)
        
        article_data = []
        for article in articles[:20]:
            try:
                title_elem = await article.query_selector("h2 a, a h2, h3 a")
                if not title_elem:
                    # Try finding link containing title
                    link = await article.query_selector("a[href*='/2']")
                    if link:
                        title_elem = link
                    else:
                        continue
                
                title = await title_elem.inner_text()
                url = await title_elem.get_attribute("href")
                if not url:
                    parent = await title_elem.query_selector("xpath=ancestor::a")
                    if parent:
                        url = await parent.get_attribute("href")
                
                if url:
                   url = make_absolute_url(url, "https://www.theverge.com")
                
                if title and url and len(title) > 5:
                    article_data.append({
                        "title": title.strip(),
                        "url": url
                    })
            except Exception:
                continue
        
        content_selectors = [
            "article p",
            ".duet--article--article-body-component p",
            ".c-entry-content p"
        ]
        
        for data in article_data[:20]:
            summary = await get_article_content(page, data["url"], content_selectors)
            news_items.append(NewsItem(
                title=data["title"],
                summary=summary if summary else data["title"],
                url=data["url"],
                source="The Verge"
            ))
                
    except Exception as e:
        print(f"The Verge scraping error: {e}")
        return [], False
    finally:
        await context.close()
    
    return news_items, True


async def scrape_venturebeat(browser: Browser) -> list[NewsItem]:
    """Scrape AI news from VentureBeat."""
    news_items = []
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await context.new_page()
    
    try:
        await page.goto(
            "https://venturebeat.com/category/ai/",
            timeout=30000
        )
        await page.wait_for_selector("article", timeout=10000)
        
        articles = await page.query_selector_all("article")
        
        article_data = []
        for article in articles[:20]:
            try:
                title_elem = await article.query_selector("h2 a, .ArticleListing__title a")
                if not title_elem:
                    continue
                
                title = await title_elem.inner_text()
                url = await title_elem.get_attribute("href")
                
                if title and url:
                    article_data.append({
                        "title": title.strip(),
                        "url": make_absolute_url(url, "https://venturebeat.com")
                    })
            except Exception:
                continue
        
        content_selectors = [
            "article p",
            ".article-content p",
            ".entry-content p"
        ]
        
        for data in article_data[:20]:
            summary = await get_article_content(page, data["url"], content_selectors)
            news_items.append(NewsItem(
                title=data["title"],
                summary=summary if summary else data["title"],
                url=data["url"],
                source="VentureBeat"
            ))
                
    except Exception as e:
        print(f"VentureBeat scraping error: {e}")
        return [], False
    finally:
        await context.close()
    
    return news_items, True


async def scrape_all_sources() -> dict:
    """
    Scrape news from all sources.
    Returns:
        {
            "items": list[NewsItem],
            "sources": {
                "Source Name": {"count": int, "status": "online"|"offline"}
            }
        }
    """
    all_news = []
    source_stats = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # Scrape sequentially to avoid overwhelming sites
        # techcrunch_res: tuple[list, bool]
        tc_items, tc_online = await scrape_techcrunch(browser)
        source_stats["TechCrunch"] = {
            "count": len(tc_items),
            "status": "online" if tc_online else "offline"
        }
        all_news.extend(tc_items)

        tv_items, tv_online = await scrape_theverge(browser)
        source_stats["The Verge"] = {
            "count": len(tv_items),
            "status": "online" if tv_online else "offline"
        }
        all_news.extend(tv_items)

        vb_items, vb_online = await scrape_venturebeat(browser)
        source_stats["VentureBeat"] = {
            "count": len(vb_items),
            "status": "online" if vb_online else "offline"
        }
        all_news.extend(vb_items)
        
        await browser.close()
    
    return {
        "items": all_news,
        "sources": source_stats
    }
