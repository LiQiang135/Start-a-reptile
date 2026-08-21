"""Playwright crawler for JS-rendered sites (vot.org)."""
import re
from urllib.parse import urljoin

from base import save_article, is_scraped, polite_sleep, parse_soup, extract_text
from config import SITES


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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        page = context.new_page()

        # Step 1: Load homepage and collect links
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # Get the final URL after any redirects
            current_url = page.url
            print(f"[{site_key}] Homepage loaded: {current_url}")

            # Collect article links from the page
            links = page.eval_on_selector_all("a[href]", """els => els.map(e => e.href)""")
            article_links = set()
            for href in links:
                if not href:
                    continue
                # Must be under same domain
                if base_url not in href and current_url not in href:
                    # Check domain match
                    from urllib.parse import urlparse
                    base_domain = urlparse(base_url).netloc
                    link_domain = urlparse(href).netloc
                    if base_domain not in link_domain and link_domain not in base_domain:
                        continue
                # Filter for article-like URLs
                skip_patterns = [r"javascript:", r"mailto:", r"#", r"/tag/",
                                 r"/category/", r"/page/\d+", r"/author/",
                                 r"/wp-admin", r"/feed", r"\.(css|js|png|jpg|jpeg|gif|svg|ico|xml)$"]
                if any(re.search(pat, href, re.I) for pat in skip_patterns):
                    continue
                if re.search(r"/(news|article|detail|post|content)/", href, re.I) or re.search(r"\d{4}", href):
                    article_links.add(href)

            article_links = list(article_links)[:max_articles + 20]
            print(f"[{site_key}] Found {len(article_links)} candidate links")

        except Exception as e:
            print(f"[{site_key}] Error loading {base_url}: {e}")
            # Try to get whatever links are available
            try:
                links = page.eval_on_selector_all("a[href]", """els => els.map(e => e.href)""")
                article_links = set()
                for href in links:
                    if href and (re.search(r"/(news|article|detail|post|content)/", href, re.I) or re.search(r"\d{4}", href)):
                        article_links.add(href)
                article_links = list(article_links)[:max_articles + 20]
                print(f"[{site_key}] Found {len(article_links)} candidate links (after error)")
            except:
                article_links = []

        # Step 2: Fetch each article page
        for url in article_links:
            if is_scraped(url) or count >= max_articles:
                continue
            try:
                polite_sleep(delay)
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
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

                content = extract_text(soup, content_selectors)
                if len(content) < 50:
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