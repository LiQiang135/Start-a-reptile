"""HTML page crawler for sites without RSS feeds (dalailamaworld, xizangzhiye)."""
import re
from urllib.parse import urljoin

from base import fetch_html, parse_soup, extract_text, save_article, is_scraped, polite_sleep
from config import SITES

# Common link patterns for article links
ARTICLE_PATTERNS = [
    re.compile(r"/article/", re.I),
    re.compile(r"/news/", re.I),
    re.compile(r"/post/", re.I),
    re.compile(r"/\d{4}/\d{2}/", re.I),  # /2024/01/ date-style URLs
    re.compile(r"\.(html?|php)$", re.I),
    re.compile(r"/detail/", re.I),
    re.compile(r"/content/", re.I),
]


def is_article_link(href):
    return any(p.search(href) for p in ARTICLE_PATTERNS)


def discover_links(base_url, max_links=100):
    """Crawl homepage and common section pages to discover article links."""
    urls_to_check = [base_url]
    # Try common news listing pages
    for path in ["/news", "/articles", "/category/news", "/news.html",
                 "/index.php/news", "/index.php/articles"]:
        urls_to_check.append(urljoin(base_url, path))
    discovered = set()
    for page_url in urls_to_check:
        try:
            html = fetch_html(page_url)
            soup = parse_soup(html)
        except Exception as e:
            print(f"  [discover] Error fetching {page_url}: {e}")
            continue
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            if full_url.startswith(base_url) and is_article_link(full_url):
                discovered.add(full_url)
        if len(discovered) >= max_links:
            break
        polite_sleep(1.0)
    return list(discovered)[:max_links]


def crawl_site(site_key, max_articles=50):
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    selectors = cfg.get("content_selectors", [])
    print(f"[{site_key}] Discovering article links from {base_url}")
    links = discover_links(base_url)
    print(f"[{site_key}] Found {len(links)} candidate links")
    count = 0
    for url in links:
        if is_scraped(url):
            continue
        if count >= max_articles:
            break
        try:
            polite_sleep(cfg.get("delay", 2.0))
            html = fetch_html(url)
            soup = parse_soup(html)
            title_el = soup.find("title") or soup.find("h1")
            title = title_el.get_text(strip=True) if title_el else ""
            date_el = soup.find("time") or soup.find(attrs={"class": re.compile(r"date|time", re.I)})
            published = date_el.get("datetime", "") if date_el and date_el.has_attr("datetime") else (date_el.get_text(strip=True) if date_el else "")
            author_el = soup.find(attrs={"class": re.compile(r"author|byline", re.I)})
            author = author_el.get_text(strip=True) if author_el else ""
            content = extract_text(soup, selectors)
            if len(content) < 50:
                continue
            save_article(
                site=site_key,
                url=url,
                title=title,
                author=author,
                published=published,
                content=content,
                raw_html="",
            )
            count += 1
            print(f"[{site_key}] Saved ({count}): {title[:60]}")
        except Exception as e:
            print(f"[{site_key}] Error scraping {url}: {e}")
    print(f"[{site_key}] Total saved: {count}")
    return count