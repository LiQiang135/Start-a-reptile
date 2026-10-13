"""Playwright crawler for JS-rendered sites (vot.org)."""
import re
from datetime import datetime
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from base import PROXIES, save_article, is_scraped, polite_sleep, parse_soup, extract_text
from config import SITES


def is_article_url(url, base_url, site_key=None):
    """Accept article paths, not archives, date directories or outside hosts."""
    parsed, base = urlparse(url), urlparse(base_url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != base.netloc.lower():
        return False
    path = unquote(parsed.path)
    segments = [part.lower() for part in path.strip("/").split("/") if part]
    if not segments or any(part in {
        "archive", "archives", "档案资料库", "tag", "tags", "category", "categories",
        "page", "author", "authors", "search", "feed", "rss", "wp-admin",
    } for part in segments):
        return False
    if re.search(r"\.(css|js|png|jpg|jpeg|gif|svg|ico|xml|pdf|mp3|mp4)$", path, re.I):
        return False
    if site_key == "rfi":
        # RFI Chinese articles end in YYYYMMDD-title; monthly archives do not.
        match = re.fullmatch(r"/cn/(?:[^/]+/)*(\d{8})-[^/]+/?", path)
        if not match:
            return False
        try:
            datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            return False
        return True
    if segments[-1].isdigit():
        return False
    return bool(re.search(r"/(news|article|articles|detail|post|content)/.+", path, re.I)
                or re.search(r"/(?:19|20)\d{2}/(?:0?[1-9]|1[0-2])/(?:\d{1,2}/)?[^/]+/?$", path))


def filter_article_links(links, base_url, site_key, max_links):
    result = []
    seen = set()
    for href in links:
        if not href:
            continue
        url, _ = urldefrag(urljoin(base_url, href))
        if url not in seen and is_article_url(url, base_url, site_key):
            seen.add(url)
            result.append(url)
    return result[:max_links]


def extract_article_content(soup, selectors):
    """Require a title and an actual configured container; no body fallback."""
    if soup.find("h1") is None:
        return ""
    for selector in selectors:
        containers = soup.select(selector)
        if len(containers) != 1:
            continue
        container = parse_soup(str(containers[0]))
        # RFI inserts advertising modules inside its article body.
        for ad in container.select(".m-ad, .m-advertising"):
            ad.decompose()
        text = extract_text(container, [selector])
        if len(text) >= 50:
            return text
    return ""


def crawl_site(site_key, max_articles=50):
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    delay = cfg.get("delay", 3.0)
    content_selectors = cfg.get("content_selectors", [])
    print(f"[{site_key}] Starting Playwright crawl of {base_url}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[{site_key}] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return 0

    count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy={"server": PROXIES["https"]})
        context = browser.new_context(
            locale="zh-CN",
        )
        page = context.new_page()

        # Step 1: Load homepage and collect links
        try:
            response = page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            if response is None or not response.ok:
                print(f"[{site_key}] Homepage HTTP error; skipping site")
                browser.close()
                return 0
            page.wait_for_timeout(5000)

            # Get the final URL after any redirects
            current_url = page.url
            print(f"[{site_key}] Homepage loaded: {current_url}")

            # Collect article links from the page
            links = page.eval_on_selector_all("a[href]", """els => els.map(e => e.href)""")
            article_links = filter_article_links(links, base_url, site_key, max_articles + 20)
            print(f"[{site_key}] Found {len(article_links)} candidate links")

        except Exception as e:
            print(f"[{site_key}] Error loading {base_url}: {e}")
            # Try to get whatever links are available
            try:
                links = page.eval_on_selector_all("a[href]", """els => els.map(e => e.href)""")
                article_links = filter_article_links(links, base_url, site_key, max_articles + 20)
                print(f"[{site_key}] Found {len(article_links)} candidate links (after error)")
            except:
                article_links = []

        # Step 2: Fetch each article page
        for url in article_links:
            if is_scraped(url) or count >= max_articles:
                continue
            try:
                polite_sleep(delay)
                response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if response is None or not response.ok:
                    print(f"[{site_key}] Skip (HTTP error): {url}")
                    continue
                if not is_article_url(page.url, base_url, site_key):
                    print(f"[{site_key}] Skip (redirected to non-article): {page.url}")
                    continue
                if not content_selectors:
                    print(f"[{site_key}] Skip (no content selectors configured): {url}")
                    continue
                page.wait_for_selector(", ".join(content_selectors), state="attached", timeout=15000)
                html = page.content()
                soup = parse_soup(html)

                title_el = soup.find("h1") or soup.find("title")
                title = title_el.get_text(strip=True) if title_el else ""

                date_el = soup.find("time") or soup.find(attrs={"class": re.compile(r"date|time", re.I)})
                published = ""
                if date_el:
                    published = date_el.get("datetime", "") if date_el.has_attr("datetime") else (date_el.get_text(strip=True) if date_el else "")

                author_el = soup.find(attrs={"class": re.compile(r"author|byline", re.I)})
                author = author_el.get_text(strip=True) if author_el else ""

                content = extract_article_content(soup, content_selectors)
                if len(content) < 50:
                    print(f"[{site_key}] Skip (no valid article body): {url}")
                    continue

                save_article(
                    site=site_key, url=url, title=title, author=author,
                    published=published, content=content, raw_html="",
                )
                count += 1
                print(f"[{site_key}] Saved ({count}): {title[:60]}")
            except Exception as e:
                print(f"[{site_key}] Error scraping {url}: {e}")

        context.close()
        browser.close()

    print(f"[{site_key}] Total saved: {count}")
    return count
