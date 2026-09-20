"""藏文路径站点爬虫（无 RSS 时使用）

URL：/{主分类}/、/{主分类}/{子分类}/、/{主分类}/{子分类}/{文章}/
站点差异写在 SITE_META，不改 config.py。
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

# 默认主分类（藏文垂符可有可无）
DEFAULT_CATEGORIES = ["གསར་འགྱུར།"]

# 仅无 RSS、且路径为藏文分类树的站
SITE_META = {
    "shambalanews": {
        "categories": DEFAULT_CATEGORIES,
        # config 里 .article-content-main 在本站不存在
        "content_selectors": [".article-content", ".article-body", "article"],
        "author_from_list": True,
        "author_meta_name": "author",  # 多为栏目名，仅作降级
    },
}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def get_meta(site_key: str) -> dict:
    meta = {"categories": list(DEFAULT_CATEGORIES), "content_selectors": None,
            "author_from_list": False, "author_meta_name": None}
    meta.update(SITE_META.get(site_key, {}))
    return meta


def get_segments(url: str) -> list[str]:
    return [s for s in unquote(urlparse(url).path).strip("/").split("/") if s]


def is_same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()


def is_subcategory(url: str, categories: set[str]) -> bool:
    segs = get_segments(url)
    return len(segs) == 2 and segs[0].rstrip("།") in categories


def is_article(url: str, categories: set[str]) -> bool:
    segs = get_segments(url)
    if len(segs) < 3:
        return False
    if any(s.lower() in {"page", "tag", "author", "search"} for s in segs):
        return False
    return segs[0].rstrip("།") in categories


def collect_links(soup, base_url: str, predicate) -> set[str]:
    found = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        full, _ = urldefrag(urljoin(base_url, href))
        if is_same_domain(full, base_url) and predicate(full):
            found.add(full)
    return found


def _in_listing(el) -> bool:
    """主文外的列表/相关稿件块（文章页 layout-magazine 不算）。"""
    node = el
    for _ in range(10):
        if node is None or getattr(node, "name", None) in (None, "body", "[document]", "html"):
            return False
        cls = node.get("class") or []
        if isinstance(cls, str):
            cls = cls.split()
        if node.name == "li" and "item" in cls:
            return True
        if {"magazine-item", "category-module", "item-list"} & set(cls):
            return True
        node = node.parent
    return False


def normalize_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m and m.group(2).lower() in _MONTHS:
        return f"{int(m.group(3)):04d}-{_MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m and m.group(1).lower() in _MONTHS:
        return f"{int(m.group(3)):04d}-{_MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return raw


def _raw_date(el) -> str:
    return (el.get("datetime") or el.get("title") or el.get("data-original-title")
            or el.get_text(strip=True) or "").strip()


def extract_published(soup) -> str:
    """主文日期：优先 dd.published.hasTooltip，其次主文 aside/time。"""
    # 1) Joomla CLEAN META（文章页主日期）
    for el in soup.select("dd.published.hasTooltip"):
        if not _in_listing(el):
            return normalize_date(_raw_date(el))
    # 2) 主文容器内的 published / schema time
    for root_sel in ("div.article-main", "article.article", "article"):
        root = soup.select_one(root_sel)
        if root is None or _in_listing(root):
            continue
        for sel in (".article-aside .published", "time[itemprop=datePublished]", "time[datetime]"):
            for el in root.select(sel):
                if _in_listing(el):
                    continue
                raw = _raw_date(el)
                if raw:
                    return normalize_date(raw)
        break
    return ""


def extract_author(soup) -> str:
    for el in soup.select("dd.createdby, [itemprop=author]"):
        if _in_listing(el):
            continue
        span = el.find("span", itemprop="name") if el.name == "dd" else None
        text = (span or el).get_text(strip=True) or (el.get("content") or "")
        if text.strip():
            return text.strip()
    return ""


def list_authors(soup, base_url: str) -> dict[str, str]:
    """列表页 URL→作者（仅在 dd.createdby 存在时）。"""
    mapping = {}
    for item in soup.select("li.item, .magazine-item"):
        a = item.find("a", href=True)
        dd = item.find("dd", class_=lambda c: c and "createdby" in c)
        if not a or not dd:
            continue
        full, _ = urldefrag(urljoin(base_url, (a.get("href") or "").strip()))
        span = dd.find("span", itemprop="name")
        name = (span or dd).get_text(strip=True)
        if name and is_same_domain(full, base_url):
            mapping[full] = name
    return mapping


def find_next_page(soup, current_url: str) -> str | None:
    a = soup.find("a", rel="next")
    if a and a.get("href"):
        return urljoin(current_url, a["href"])
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "/page/" in href or "start=" in href or "limitstart=" in href:
            full = urljoin(current_url, href)
            if full != current_url:
                return full
    return None


def discover_articles(base_url: str, meta: dict, max_articles: int = 200,
                      max_pages_per_sub: int = 8) -> tuple[list[str], dict[str, str]]:
    cats = {c.rstrip("།") for c in meta["categories"]}
    articles: set[str] = set()
    authors: dict[str, str] = {}

    def pred_sub(u):
        return is_subcategory(u, cats)

    def pred_art(u):
        return is_article(u, cats)

    def ingest(soup):
        found = collect_links(soup, base_url, pred_art)
        articles.update(found)
        if meta.get("author_from_list"):
            for u, name in list_authors(soup, base_url).items():
                authors.setdefault(u, name)
        return found

    for category in meta["categories"]:
        if len(articles) >= max_articles:
            break
        main_url = urljoin(base_url, f"/{category.strip('/')}/")
        print(f"[discover] {main_url}")
        try:
            soup = parse_soup(fetch_html(main_url))
            subcats = collect_links(soup, base_url, pred_sub)
            arts = ingest(soup)
            print(f"  home: {len(arts)} articles, {len(subcats)} subcats")
        except Exception as e:
            print(f"  error {main_url}: {e}")
            continue

        for sub_url in sorted(subcats):
            page_url, pages = sub_url, 0
            while page_url and pages < max_pages_per_sub and len(articles) < max_articles:
                try:
                    soup = parse_soup(fetch_html(page_url))
                except Exception as e:
                    print(f"  error {page_url}: {e}")
                    break
                arts = ingest(soup)
                print(f"  [{category}] p{pages + 1}: +{len(arts)} (total {len(articles)})")
                nxt = find_next_page(soup, page_url)
                if nxt == page_url:
                    break
                page_url, pages = nxt, pages + 1
                polite_sleep(1.0)

    return list(articles)[:max_articles], authors


def crawl_site(site_key: str, max_articles: int = 50) -> int:
    cfg = SITES[site_key]
    meta = get_meta(site_key)
    base_url = cfg["base_url"]
    selectors = meta.get("content_selectors") or cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] discover {base_url} selectors={selectors}")
    links, authors = discover_articles(base_url, meta, max_articles=max_articles * 2)
    print(f"[{site_key}] {len(links)} links, {len(authors)} list authors")

    count = 0
    for url in links:
        if is_scraped(url) or count >= max_articles:
            continue
        polite_sleep(delay)
        try:
            soup = parse_soup(fetch_html(url))
            title_el = (
                soup.find("h1", class_="article-title")
                or soup.find("h1", attrs={"itemprop": "headline"})
                or soup.find("h1")
                or soup.find("h2", class_="article-title")
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                og = soup.find("meta", property="og:title")
                title = og.get("content", "").strip() if og else ""
            for sep in ("། །", " - ", " | "):
                if sep in title:
                    title = title.split(sep)[0].strip()

            author = authors.get(url) or extract_author(soup)
            if not author and meta.get("author_meta_name"):
                m = soup.find("meta", attrs={"name": meta["author_meta_name"]})
                if m and (m.get("content") or "").strip():
                    author = f"[brand] {(m.get('content') or '').strip()}"

            published = extract_published(soup)
            content = extract_text(soup, selectors)
            if not content or len(content) < 50:
                print(f"[{site_key}] skip short: {url}")
                continue

            save_article(
                site=site_key, url=url, title=title, author=author,
                published=published, content=content, raw_html="",
            )
            count += 1
            print(f"[{site_key}] saved {count}/{max_articles}: {title[:36]}... pub={published!r} au={author[:24]!r}")
        except Exception as e:
            print(f"[{site_key}] error {url}: {e}")

    print(f"[{site_key}] total {count}")
    return count
