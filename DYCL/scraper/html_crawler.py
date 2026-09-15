"""HTML page crawler for sites without RSS feeds (dalailamaworld, xizangzhiye, freetibet)."""
import re
from urllib.parse import urljoin, urlparse

from base import fetch_html, parse_soup, extract_text, save_article, is_scraped, polite_sleep
from config import SITES

# Common link patterns for article links
ARTICLE_PATTERNS = [
    re.compile(r"/latest/", re.I),          # Free Tibet 主要路径
    re.compile(r"/article/", re.I),
    re.compile(r"/news/", re.I),
    re.compile(r"/post/", re.I),
    re.compile(r"/\d{4}/\d{2}/", re.I),     # /2024/01/ date-style URLs
    re.compile(r"\.(html?|php)$", re.I),
    re.compile(r"/detail/", re.I),
    re.compile(r"/content/", re.I),
]


def is_article_link(href, base_url=None):
    if not href:
        return False

    href_lower = href.lower()

    # 1. 排除带筛选参数的页面（最常见漏网情况）
    if "filter_" in href_lower or "filter_submit" in href_lower:
        return False

    # 2. 排除纯列表页（各种写法）
    # 匹配以 /latest 或 /latest/ 结尾，且后面没有文章别名
    if re.search(r"/latest/?$", href_lower):
        return False
    if re.search(r"/news/?$", href_lower):
        return False

    # 3. 排除明显的分页、分类、标签等
    if re.search(r"/(page|tag|category|author|search)/", href_lower):
        return False

    # 4. 正常文章规则匹配
    return any(p.search(href) for p in ARTICLE_PATTERNS)

def discover_links(base_url, max_links=100):
    """Crawl homepage and common section pages to discover article links."""
    urls_to_check = [base_url]

    for path in [
        "/latest",
        "/news",
        "/articles",
        "/category/news",
        "/news.html",
        "/index.php/news",
        "/index.php/articles",
    ]:
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
            href = a["href"].strip()
            full_url = urljoin(base_url, href).split("#")[0].split("?")[0]  # 去掉锚点和参数

            # 必须是本站
            if not full_url.startswith(base_url):
                continue

            # 再次强制排除纯列表页
            path = urlparse(full_url).path.rstrip("/")
            if path in ("", "/latest", "/news", "/articles"):
                continue

            # 最终判断
            if is_article_link(full_url):
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

            # ---------- 标题（优先 h1 → og:title → <title>）----------
            title = ""
            h1 = soup.find("h1")
            if h1 is not None:
                title = h1.get_text(strip=True)
            if not title:
                og_title = soup.find("meta", property="og:title")
                if og_title is not None:
                    title = og_title.get("content", "").strip()
            if not title:
                title_el = soup.find("title")
                if title_el is not None:
                    title = title_el.get_text(strip=True)
            # 去掉末尾常见的站点后缀
            for suffix in (" - Free Tibet", " | Free Tibet", " - FreeTibet"):
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()
                    break

            # ---------- 发布时间（优先 meta → <time> → class）----------
            published = ""
            # 1. 最准确的 meta
            for prop in ("article:published_time", "og:published_time", "publishdate", "pubdate"):
                meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                if meta is not None and meta.get("content"):
                    published = meta.get("content").strip()
                    break
            # 2. <time> 标签
            if not published:
                date_el = soup.find("time")
                if date_el is not None:
                    published = date_el.get("datetime") or date_el.get_text(strip=True)
            # 3. 常见 class
            if not published:
                date_el = soup.find(attrs={"class": re.compile(r"date|time|published|post-date", re.I)})
                if date_el is not None:
                    published = date_el.get("datetime") or date_el.get_text(strip=True)

            # ---------- 作者 ----------
            author = ""
            author_el = soup.find(attrs={"class": re.compile(r"author|byline|writer", re.I)})
            if author_el is not None:
                author = author_el.get_text(strip=True)

            # ---------- 正文 ----------
            content = extract_text(soup, selectors)
            if not content or len(content) < 50:
                print(f"[{site_key}] Skip (content too short): {url}")
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
            import traceback
            print(f"[{site_key}] Error scraping {url}: {e}")
            traceback.print_exc()

    print(f"[{site_key}] Total saved: {count}")
    return count