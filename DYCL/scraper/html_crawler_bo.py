"""藏文 CMS 爬虫

URL 结构：
/{主分类}/                  ← 主分类
/{主分类}/{子分类}/         ← 二级分类（支持分页）
/{主分类}/{子分类}/{文章}/   ← 文章
"""

import re
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from base import (
    extract_text,
    fetch_html,
    is_scraped,
    parse_soup,
    polite_sleep,
    save_article,
)
from config import SITES

TIBETAN_CATEGORIES = [
    "གསར་འགྱུར།",  # 新闻
    # "དཔྱད་གླེང༌།",  # 评论
    # "བོད་སྐོར།",  # 关于西藏
    # "མང་གཙོ།",  # 民主
]

# 规范化分类名称（去除末尾藏文垂符 །），用于路由匹配
NORMALIZED_CATEGORIES = {cat.rstrip("།") for cat in TIBETAN_CATEGORIES}


def get_segments(url: str) -> list[str]:
    """返回解码后的路径分段。"""
    path = unquote(urlparse(url).path).strip("/")
    return [s for s in path.split("/") if s]


def is_same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()


def is_subcategory(url: str) -> bool:
    """正好两段，且第一段属于任一主分类。"""
    segs = get_segments(url)
    return len(segs) == 2 and segs[0].rstrip("།") in NORMALIZED_CATEGORIES


def is_article(url: str) -> bool:
    """至少三段，且第一段属于任一主分类。"""
    segs = get_segments(url)
    if len(segs) < 3:
        return False
    if any(s.lower() in {"page", "tag", "author", "search"} for s in segs):
        return False
    return segs[0].rstrip("།") in NORMALIZED_CATEGORIES


def collect_links(soup, base_url: str, predicate) -> set[str]:
    """从页面收集符合条件的链接。"""
    found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        full, _ = urldefrag(urljoin(base_url, href))
        if is_same_domain(full, base_url) and predicate(full):
            found.add(full)
    return found


def find_next_page(soup, current_url: str) -> str | None:
    """寻找下一页链接（兼容常见分页写法）。"""
    next_link = soup.find("a", rel="next")
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        classes = " ".join(a.get("class", [])).lower()
        if any(k in text or k in classes for k in ("next", "下一页", "›", "»")):
            return urljoin(current_url, a["href"])

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/page/" in href or "start=" in href or "limitstart=" in href:
            full = urljoin(current_url, href)
            if full != current_url:
                return full
    return None


def discover_articles(base_url: str, max_articles: int = 200, max_pages_per_sub: int = 8) -> list[str]:
    """发现流程：遍历所有主分类 → 子分类（翻页）→ 文章。"""
    articles = set()

    for category in TIBETAN_CATEGORIES:
        if len(articles) >= max_articles:
            break

        main_url = urljoin(base_url, f"/{category.strip('/')}/")
        print(f"[discover] Scanning category: {main_url}")

        try:
            html = fetch_html(main_url)
            soup = parse_soup(html)
            subcats = collect_links(soup, base_url, is_subcategory)

            new_arts = collect_links(soup, base_url, is_article)
            articles |= new_arts
            print(f"  Category home found {len(new_arts)} articles, {len(subcats)} subcategories")
        except Exception as e:
            print(f"[discover] Error fetching category {main_url}: {e}")
            continue

        # 遍历该分类下的每个二级分类与分页
        for sub_url in sorted(subcats):
            page_url = sub_url
            pages = 0

            # while page_url and pages < max_pages_per_sub and len(articles) < max_articles:
            try:
                html = fetch_html(page_url)
                soup = parse_soup(html)
            except Exception as e:
                print(f"  Error fetching {page_url}: {e}")
                break

            new_arts = collect_links(soup, base_url, is_article)
            before = len(articles)
            articles |= new_arts
            print(f"  [{category}] Page {pages + 1}: Found {len(new_arts)} articles (+{len(articles) - before} new)")

            page_url = find_next_page(soup, page_url)
            pages += 1
            polite_sleep(1.0)

    return list(articles)[:max_articles]


def extract_author(soup) -> str:
    """从 .createdby.hasTooltip 提取作者。"""
    dd = soup.find("dd", class_=lambda c: c and "createdby" in c)
    if not dd:
        return ""
    span = dd.find("span", itemprop="name")
    return (span or dd).get_text(strip=True)


def extract_published(soup) -> str:
    raw_date = ""
    # 1. 第一优先：含 class 属性的元素（先查 published hasTooltip 特征类，再查通用 date/time 类）
    tooltip_el = soup.find(attrs={"class": lambda c: c and "published" in c and "hasTooltip" in c})
    if tooltip_el:
        raw_date = (
            tooltip_el.get("title")
            or tooltip_el.get("data-original-title")
            or tooltip_el.get("datetime")
            or tooltip_el.get_text(strip=True)
        )
    return raw_date


def crawl_site(site_key: str, max_articles: int = 50) -> int:
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    selectors = cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] Discovering Tibetan links from {base_url}")
    links = discover_articles(base_url, max_articles=max_articles * 2)
    print(f"[{site_key}] Found {len(links)} candidate links")

    count = 0
    for url in links:
        if is_scraped(url) or count >= max_articles:
            continue

        polite_sleep(delay)
        try:
            html = fetch_html(url)
            soup = parse_soup(html)

            title_el = soup.find("h2", class_="article-title") or soup.find("h1")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                og = soup.find("meta", property="og:title")
                title = og.get("content", "").strip() if og else ""

            for sep in ("། །", " - ", " | "):
                if sep in title:
                    title = title.split(sep)[0].strip()

            author = extract_author(soup)
            published = extract_published(soup)
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
            print(f"[{site_key}] Saved ({count}/{max_articles}): {title[:40]}...")

        except Exception as e:
            print(f"[{site_key}] Error scraping {url}: {e}")

    print(f"[{site_key}] Total saved: {count}")
    return count