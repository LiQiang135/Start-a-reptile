"""RSS feed crawler for WordPress-based sites (phayul, tibetpost)."""
import re
import warnings
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

from base import fetch_html, parse_soup, extract_text, save_article, is_scraped, polite_sleep
from config import SITES

# Suppress XML-parsed-as-HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def parse_feed(feed_url):
    """Parse RSS/Atom feed, return list of item dicts."""
    html = fetch_html(feed_url)
    # Use XML parser for RSS feeds to avoid <link/> self-closing issue
    try:
        soup = BeautifulSoup(html, "xml")
    except Exception:
        soup = parse_soup(html)
    items = []
    for item in soup.find_all("item"):
        entry = {}
        t = item.find("title")
        entry["title"] = t.get_text(strip=True) if t else ""
        l = item.find("link")
        entry["link"] = l.get_text(strip=True) if l else ""
        d = item.find("pubDate")
        entry["published"] = d.get_text(strip=True) if d else ""
        a = item.find("creator")
        entry["author"] = a.get_text(strip=True) if a else ""
        desc = item.find("description")
        entry["summary"] = desc.get_text(strip=True) if desc else ""
        # content:encoded often has full article
        content = item.find("content:encoded")
        if content:
            entry["full_content"] = content.get_text(strip=True)
        items.append(entry)
    # Atom feed fallback
    if not items:
        for entry in soup.find_all("entry"):
            e = {}
            t = entry.find("title")
            e["title"] = t.get_text(strip=True) if t else ""
            l = entry.find("link")
            e["link"] = l.get("href", "") if l else ""
            d = entry.find("published") or entry.find("updated")
            e["published"] = d.get_text(strip=True) if d else ""
            a = entry.find("author")
            e["author"] = a.get_text(strip=True) if a else ""
            s = entry.find("summary")
            e["summary"] = s.get_text(strip=True) if s else ""
            items.append(e)
    return items


def crawl_site(site_key, max_articles=50):
    cfg = SITES[site_key]
    print(f"[{site_key}] Fetching feed: {cfg['feed_url']}")
    try:
        items = parse_feed(cfg["feed_url"])
    except Exception as e:
        print(f"[{site_key}] Error fetching feed: {e}")
        return 0
    print(f"[{site_key}] Found {len(items)} feed items")
    selectors = cfg.get("content_selectors", [])
    count = 0
    for item in items:
        url = item.get("link", "")
        if not url or is_scraped(url):
            continue
        if count >= max_articles:
            break
        # If feed already has full content, use it
        full = item.get("full_content", "")
        if full and len(full) > 200:
            content_soup = parse_soup(full)
            content = extract_text(content_soup, selectors)
        else:
            # Fetch article page for full content
            try:
                polite_sleep(cfg.get("delay", 2.0))
                html = fetch_html(url)
                soup = parse_soup(html)
                content = extract_text(soup, selectors)
            except Exception as e:
                print(f"[{site_key}] Error fetching {url}: {e}")
                content = item.get("summary", "")
        save_article(
            site=site_key,
            url=url,
            title=item.get("title", ""),
            author=item.get("author", ""),
            published=item.get("published", ""),
            content=content,
            summary=item.get("summary", ""),
        )
        count += 1
        print(f"[{site_key}] Saved ({count}): {item.get('title','')[:60]}")
    print(f"[{site_key}] Total saved: {count}")
    return count