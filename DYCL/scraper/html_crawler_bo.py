"""藏文路径 CMS 爬虫（专用：路径含藏文分类的站点）

URL 结构：
/{主分类}/                  ← 主分类
/{主分类}/{子分类}/         ← 二级分类（支持分页）
/{主分类}/{子分类}/{文章}/   ← 文章

站点差异放在本模块 BO_SITE_PROFILES，不改 config.py。
config 仅继续提供 base_url / delay / content_selectors（profile 可覆盖正文 selector）。
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
    # "གསར་འགྱུར།",  # 新闻
    "དཔྱད་གླེང༌།",  # 评论
    # "བོད་སྐོར།",  # 关于西藏
    # "མང་གཙོ།",  # 民主
]

# 明确的列表/相关稿件容器 class
# 注意：不要用过宽的 magazine —— 文章页模板是 layout-magazine / mainbody-magazine
_LIST_CONTAINER_CLASSES = {
    "magazine-item",
    "category-module",
    "item-list",
    "grid-view",
    "link-item",
}
_LIST_NOISE_RE = re.compile(
    r"\b(mod-articles|mod_related|related-posts|other-posts|teaser|widget)\b",
    re.I,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

DEFAULT_PROFILE = {
    "categories": None,  # None → TIBETAN_CATEGORIES
    "content_selectors": None,  # None → SITES[key].content_selectors
    "date_selectors": [
        "dd.published.hasTooltip",
        ".article-aside .published",
        ".published.hasTooltip",
        "time[itemprop=datePublished]",
        "time[datetime]",
    ],
    "author_from_list": False,
    "article_root_selectors": [
        "div.article-main",
        "article.article",
        "section.article-content",
        "article",
        ".item-page",
        ".com-content-article",
    ],
    "author_meta_name": None,
    "author_meta_is_brand": False,
}

BO_SITE_PROFILES = {
    "shambalanews": {
        # None → 使用模块级 TIBETAN_CATEGORIES（改分类只改那一处）
        "categories": None,
        "content_selectors": [".article-content", ".article-body", "article"],
        "date_selectors": [
            "dd.published.hasTooltip",
            ".article-header ~ .article-aside .published",
            ".article-aside .published",
            "time[itemprop=datePublished]",
            ".article-content time[datetime]",
            ".published.hasTooltip",
        ],
        "author_from_list": True,
        "article_root_selectors": [
            "div.article-main",
            "article.article",
            "section.article-content",
            "article",
            ".item-page",
            ".com-content-article",
        ],
        "author_meta_name": "author",
        "author_meta_is_brand": True,
    },
}


def get_profile(site_key: str) -> dict:
    profile = {**DEFAULT_PROFILE, **BO_SITE_PROFILES.get(site_key, {})}
    if not profile.get("categories"):
        profile["categories"] = list(TIBETAN_CATEGORIES)
    return profile


def get_segments(url: str) -> list[str]:
    path = unquote(urlparse(url).path).strip("/")
    return [s for s in path.split("/") if s]


def is_same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()


def make_url_predicates(categories: list[str]):
    normalized = {c.rstrip("།") for c in categories}

    def is_subcategory(url: str) -> bool:
        segs = get_segments(url)
        return len(segs) == 2 and segs[0].rstrip("།") in normalized

    def is_article(url: str) -> bool:
        segs = get_segments(url)
        if len(segs) < 3:
            return False
        if any(s.lower() in {"page", "tag", "author", "search"} for s in segs):
            return False
        return segs[0].rstrip("།") in normalized

    return is_subcategory, is_article


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


def _class_str(el) -> str:
    if el is None:
        return ""
    cls = el.get("class") or []
    if isinstance(cls, list):
        return " ".join(cls)
    return str(cls)


def _class_set(el) -> set[str]:
    if el is None:
        return set()
    cls = el.get("class") or []
    if isinstance(cls, str):
        return set(cls.split())
    return set(cls)


def _in_list_module(el) -> bool:
    """是否在列表/相关稿件模块中。页面级 layout-magazine 不算噪声。"""
    node = el
    for _ in range(15):
        if node is None:
            break
        name = getattr(node, "name", None)
        if name in (None, "body", "[document]", "html"):
            break
        classes = _class_set(node)
        if name == "li" and "item" in classes:
            return True
        if classes & _LIST_CONTAINER_CLASSES:
            return True
        if _LIST_NOISE_RE.search(_class_str(node)):
            return True
        node = getattr(node, "parent", None)
    return False


def _find_article_region(soup, profile: dict):
    default_roots = list(profile.get("article_root_selectors") or []) + [
        "div.article-main",
        "article.article",
        "section.article-content",
        "article",
        ".item-page",
        ".com-content-article",
    ]
    seen = set()
    for sel in default_roots:
        if sel in seen:
            continue
        seen.add(sel)
        for el in soup.select(sel):
            if _in_list_module(el):
                continue
            if el.select_one(
                "h1.article-title, h1[itemprop=headline], h1, .article-body, .article-intro"
            ):
                text = el.get_text(strip=True)
                if len(text) >= 50:
                    return el
    h1 = (
        soup.find("h1", class_="article-title")
        or soup.find("h1", attrs={"itemprop": "headline"})
        or soup.find("h1")
    )
    if h1 is not None and not _in_list_module(h1):
        header = h1.find_parent("header") or h1
        if header.parent is not None:
            return header.parent
    return soup


_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def _format_rfc2822(year: int, month: int, day: int,
                    hour: int = 0, minute: int = 0, second: int = 0) -> str:
    """贴近 Fri, 02 Jan 2026 09:04:59 +0000"""
    from datetime import date
    wd = _WEEKDAYS[date(year, month, day).weekday()]
    return (
        f"{wd}, {day:02d} {_MONTH_ABBR[month]} {year:04d} "
        f"{hour:02d}:{minute:02d}:{second:02d} +0000"
    )


def normalize_date(raw: str) -> str:
    """归一为 RFC2822 风格：Fri, 02 Jan 2026 09:04:59 +0000"""
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""

    # 已是目标格式
    if re.match(r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} [+-]\d{4}$", raw):
        return raw

    # ISO: 2024-10-05 / 2024-10-05T08:30:00+00:00 / 2024-10-05 08:30:00
    m = re.match(
        r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        return _format_rfc2822(y, mo, d, hh, mm, ss)

    # 05 October 2024 / 5 Oct 2024
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m and m.group(2).lower() in _MONTHS:
        return _format_rfc2822(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))

    # Oct 11 2024 / October 11, 2024
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m and m.group(1).lower() in _MONTHS:
        return _format_rfc2822(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))

    return raw


def _el_raw_date(el) -> str:
    if el is None:
        return ""
    return (
        el.get("datetime")
        or el.get("title")
        or el.get("data-original-title")
        or el.get_text(strip=True)
        or ""
    )


def extract_published(soup, profile: dict | None = None) -> str:
    profile = profile or DEFAULT_PROFILE
    region = _find_article_region(soup, profile)

    candidates = []
    for sel in profile.get("date_selectors") or []:
        for scope in (region, soup):
            try:
                found = scope.select(sel)
            except Exception:
                continue
            for el in found:
                if _in_list_module(el):
                    continue
                raw = _el_raw_date(el)
                if raw and raw.strip():
                    candidates.append(raw.strip())
            if candidates:
                break
        if candidates:
            break
    if not candidates:
        return ""
    return normalize_date(candidates[0])


def extract_author(soup, profile: dict | None = None) -> str:
    """文章页作者（不含 meta 品牌名）。"""
    profile = profile or DEFAULT_PROFILE
    region = _find_article_region(soup, profile)

    for scope in (region, soup):
        for dd in scope.find_all("dd", class_=lambda c: c and "createdby" in c):
            if _in_list_module(dd):
                continue
            span = dd.find("span", itemprop="name")
            text = (span or dd).get_text(strip=True)
            if text:
                return text
        for el in scope.select("[itemprop=author]"):
            if _in_list_module(el):
                continue
            text = el.get_text(strip=True) or (el.get("content") or "")
            if text.strip():
                return text.strip()
        if scope is not region:
            break
    return ""


def extract_author_meta(soup, profile: dict) -> str:
    name = profile.get("author_meta_name")
    if not name:
        return ""
    meta = soup.find("meta", attrs={"name": name})
    if meta is None:
        return ""
    value = (meta.get("content") or "").strip()
    if not value:
        return ""
    if profile.get("author_meta_is_brand"):
        return f"[brand] {value}"
    return value


def scrape_list_authors(soup, base_url: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in soup.select("li.item, .magazine-item, article, .item"):
        link = item.find("a", href=True)
        if not link:
            continue
        href = (link.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        full, _ = urldefrag(urljoin(base_url, href))
        if not is_same_domain(full, base_url):
            continue
        dd = item.find("dd", class_=lambda c: c and "createdby" in c)
        if not dd:
            continue
        span = dd.find("span", itemprop="name")
        author = (span or dd).get_text(strip=True)
        if author:
            mapping[full] = author
    return mapping


def _normalize_page_url(url: str) -> str:
    """分页 URL 去锚点，便于防环去重。"""
    full, _ = urldefrag(url)
    return full.rstrip("/") or full


def find_next_page(soup, current_url: str, visited: set[str] | None = None) -> str | None:
    """找下一页；visited 中已出现过的分页 URL 会跳过，避免 start=7/14 打转。"""
    visited = visited or set()
    current_norm = _normalize_page_url(current_url)
    candidates: list[str] = []

    next_link = soup.find("a", rel="next")
    if next_link and next_link.get("href"):
        candidates.append(urljoin(current_url, next_link["href"]))

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        classes = " ".join(a.get("class", [])).lower()
        if any(k in text or k in classes for k in ("next", "下一页", "›", "»")):
            candidates.append(urljoin(current_url, a["href"]))

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if "/page/" in href or "start=" in href or "limitstart=" in href:
            candidates.append(urljoin(current_url, href))

    for full in candidates:
        norm = _normalize_page_url(full)
        if not norm or norm == current_norm:
            continue
        if norm in visited:
            continue
        return full
    return None


def discover_articles(
    base_url: str,
    profile: dict,
    max_articles: int = 200,
    max_pages_per_sub: int = 8,
) -> tuple[list[str], dict[str, str]]:
    """主分类 → 子分类（翻页）→ 文章；可选列表页作者映射。

    日志含义：
      page_hits = 当页符合 is_article 的链接数（可含侧栏/相关稿重复）
      new       = 相对全局集合的新增唯一 URL
      total     = 目前去重后的文章 URL 总数
    """
    categories = profile.get("categories") or TIBETAN_CATEGORIES
    is_subcategory, is_article = make_url_predicates(categories)
    articles: set[str] = set()
    list_authors: dict[str, str] = {}

    def ingest(soup) -> tuple[int, int]:
        page_hits = collect_links(soup, base_url, is_article)
        before = len(articles)
        articles.update(page_hits)
        if profile.get("author_from_list"):
            for u, a in scrape_list_authors(soup, base_url).items():
                list_authors.setdefault(u, a)
        return len(page_hits), len(articles) - before

    for category in categories:
        if len(articles) >= max_articles:
            break
        main_url = urljoin(base_url, f"/{category.strip('/')}/")
        print(f"[discover] Scanning category: {main_url}")
        try:
            html = fetch_html(main_url)
            soup = parse_soup(html)
            subcats = collect_links(soup, base_url, is_subcategory)
            hits, new = ingest(soup)
            print(
                f"  Category home: page_hits={hits} new={new} "
                f"subcats={len(subcats)} total={len(articles)}"
            )
        except Exception as e:
            print(f"[discover] Error fetching category {main_url}: {e}")
            continue

        for sub_url in sorted(subcats):
            page_url = sub_url
            pages = 0
            visited_pages: set[str] = set()
            while page_url and pages < max_pages_per_sub and len(articles) < max_articles:
                page_norm = _normalize_page_url(page_url)
                if page_norm in visited_pages:
                    break
                visited_pages.add(page_norm)
                try:
                    html = fetch_html(page_url)
                    soup = parse_soup(html)
                except Exception as e:
                    print(f"  Error fetching {page_url}: {e}")
                    break
                hits, new = ingest(soup)
                print(
                    f"  [{category}] p{pages + 1}: page_hits={hits} new={new} "
                    f"total={len(articles)} | {page_url[-50:]}"
                )
                next_url = find_next_page(soup, page_url, visited_pages)
                if not next_url:
                    break
                page_url = next_url
                pages += 1
                polite_sleep(1.0)

    return list(articles)[:max_articles], list_authors


def crawl_site(site_key: str, max_articles: int = 50) -> int:
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    profile = get_profile(site_key)
    selectors = profile.get("content_selectors") or cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] Discovering Tibetan links from {base_url}")
    print(f"[{site_key}] profile categories={profile['categories']} selectors={selectors}")
    links, list_authors = discover_articles(
        base_url, profile, max_articles=max_articles * 2
    )
    print(f"[{site_key}] Found {len(links)} candidate links, list_authors={len(list_authors)}")

    count = 0
    for url in links:
        if is_scraped(url) or count >= max_articles:
            continue
        polite_sleep(delay)
        try:
            html = fetch_html(url)
            soup = parse_soup(html)

            title_el = (
                soup.find("h1", class_="article-title")
                or soup.find("h1", attrs={"itemprop": "headline"})
                or soup.find("h2", class_="article-title")
                or soup.find("h1")
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                og = soup.find("meta", property="og:title")
                title = og.get("content", "").strip() if og else ""
            for sep in ("། །", " - ", " | "):
                if sep in title:
                    title = title.split(sep)[0].strip()

            author = list_authors.get(url) or extract_author(soup, profile)
            if not author and profile.get("author_meta_name"):
                brand = extract_author_meta(soup, profile)
                if brand:
                    author = brand

            published = extract_published(soup, profile)
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
