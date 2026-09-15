"""HTML page crawler for Tibetan language websites and sections.

Targets categories:
- གསར་འགྱུར། (News)
- དཔྱད་གླེང༌། (Opinion)
- ཆེད་བསྒྲིགས། (Special Features)
- འཕྲོད་བསྟེན། (Health)
- ཚན་རྩལ། (Tech)
- བོད་སྐོར། (About Tibet)
- མང་གཙོ། (Democracy)
"""

import json
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

# 目标藏文分类关键词（去除尾部标点以增强兼容匹配）
TIBETAN_CATEGORIES = [
    "གསར་འགྱུར",  # 新闻
    # "དཔྱད་གླེང",  # 评论
    # "བོད་སྐོར",  # 关于西藏
    # "མང་གཙོ",  # 民主
]

# 藏文分类正则表达式
TIBETAN_CAT_PATTERN = re.compile(
    r"/(" + "|".join(re.escape(cat) for cat in TIBETAN_CATEGORIES) + r")", re.I
)

# 通用文章链接模式
ARTICLE_PATTERNS = [
    re.compile(r"/latest/", re.I),
    re.compile(r"/article/", re.I),
    re.compile(r"/news/", re.I),
    re.compile(r"/post/", re.I),
    re.compile(r"/\d{4}/\d{2}/", re.I),
    re.compile(r"\.(html?|php)$", re.I),
    re.compile(r"/detail/", re.I),
    re.compile(r"/content/", re.I),
    re.compile(r"[?&](p|id|post_id|article_id)=\d+", re.I),
]

# 藏文数字映射表
TIBETAN_DIGITS = {
    "༠": "0",
    "༡": "1",
    "༢": "2",
    "༣": "3",
    "༤": "4",
    "༥": "5",
    "༦": "6",
    "༧": "7",
    "༨": "8",
    "༩": "9",
}


def normalize_tibetan_digits(text: str) -> str:
    """将文本中的藏文数字转为阿拉伯数字。"""
    if not text:
        return ""
    for tib_d, arab_d in TIBETAN_DIGITS.items():
        text = text.replace(tib_d, arab_d)
    return text


def is_same_domain(url: str, base_url: str) -> bool:
    """校验链接域名是否一致。"""
    return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()


def is_tibetan_article_link(url: str) -> bool:
    """判断是否为目标藏文分类下的文章详情页。"""
    if not url:
        return False

    # 关键：将 %E0%BD%... 转码为标准藏文字符
    decoded_url = unquote(url)
    parsed = urlparse(decoded_url)
    clean_path = parsed.path.rstrip("/")
    path_and_query = (clean_path + ("?" + parsed.query if parsed.query else "")).lower()

    # 1. 过滤搜索与筛选参数
    if any(k in path_and_query for k in ("filter_", "filter_submit", "search=", "s=")):
        return False

    # 2. 排除纯分页、标签、作者汇总列表
    if re.search(r"/(page/\d+|tag/|author/|search/)", clean_path, re.I):
        return False

    # 3. 排除分类首页本身（末尾直接等于分类名）
    for cat in TIBETAN_CATEGORIES:
        if clean_path.endswith(f"/{cat}") or clean_path.endswith(f"/{cat}།"):
            return False

    # 4. 必须包含指定的藏文分类关键词
    if not TIBETAN_CAT_PATTERN.search(clean_path):
        return False

    # 5. 校验层级深度（分类层级之后必须还有路径/文章别名）
    path_segments = [seg for seg in clean_path.split("/") if seg]
    has_subpath = False
    for i, seg in enumerate(path_segments):
        if any(cat in seg for cat in TIBETAN_CATEGORIES) and i < len(path_segments) - 1:
            has_subpath = True
            break

    has_article_pattern = any(p.search(decoded_url) for p in ARTICLE_PATTERNS)
    return has_subpath or has_article_pattern


def get_seed_urls(base_url: str) -> list:
    """生成首页及各大藏文分类的探测入口。"""
    seeds = [base_url]
    for cat in TIBETAN_CATEGORIES:
        seeds.extend([
            urljoin(base_url, f"/{cat}/"),
            urljoin(base_url, f"/{cat}།/"),
            urljoin(base_url, f"/category/{cat}/"),
            urljoin(base_url, f"/category/{cat}།/"),
        ])
    return seeds


def discover_links(base_url: str, max_links: int = 100) -> list:
    """遍历目标栏目，搜集藏文文章 URL。"""
    urls_to_check = get_seed_urls(base_url)
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
            if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            # 去除 #fragment 锚点
            full_url, _ = urldefrag(urljoin(base_url, href))

            if not is_same_domain(full_url, base_url):
                continue

            if is_tibetan_article_link(full_url):
                discovered.add(full_url)
                if len(discovered) >= max_links:
                    break

        if len(discovered) >= max_links:
            break

        polite_sleep(1.0)

    return list(discovered)[:max_links]


def extract_metadata_from_ld_json(soup) -> dict:
    """解析 ld+json 结构化数据。"""
    meta = {}
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                schema_types = item.get("@type", [])
                if isinstance(schema_types, str):
                    schema_types = [schema_types]

                if any(t in ("NewsArticle", "Article", "BlogPosting") for t in schema_types):
                    meta["title"] = item.get("headline") or item.get("name") or ""
                    meta["published"] = item.get("datePublished") or ""
                    author_data = item.get("author")
                    if isinstance(author_data, dict):
                        meta["author"] = author_data.get("name", "")
                    elif isinstance(author_data, list) and author_data:
                        first_author = author_data[0]
                        meta["author"] = first_author.get("name", "") if isinstance(first_author, dict) else str(first_author)
                    return meta
        except Exception:
            continue
    return meta


def crawl_site(site_key: str, max_articles: int = 50) -> int:
    """执行站点爬取与解析入库。"""
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    selectors = cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] Discovering Tibetan links from {base_url}")
    links = discover_links(base_url)
    print(f"[{site_key}] Found {len(links)} candidate links")

    count = 0
    for url in links:
        if is_scraped(url):
            continue
        if count >= max_articles:
            break

        polite_sleep(delay)

        try:
            html = fetch_html(url)
            soup = parse_soup(html)
            ld_meta = extract_metadata_from_ld_json(soup)

            # ---------- 1. 标题 ----------
            title = ld_meta.get("title") or ""
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
            if not title:
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title.get("content", "").strip()
            if not title:
                title_el = soup.find("title")
                if title_el:
                    title = title_el.get_text(strip=True)

            # 去除网站通用后缀
            for sep in (" - ", " | ", " — "):
                if sep in title:
                    parts = title.split(sep)
                    if len(parts) >= 2:
                        title = sep.join(parts[:-1]).strip()

            # ---------- 2. 时间 ----------
            published = ld_meta.get("published") or ""
            if not published:
                for prop in ("article:published_time", "og:published_time", "publishdate", "pubdate"):
                    meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                    if meta and meta.get("content"):
                        published = meta.get("content").strip()
                        break
            if not published:
                time_el = soup.find("time")
                if time_el:
                    published = time_el.get("datetime") or time_el.get_text(strip=True)
            if not published:
                date_el = soup.find(attrs={"class": re.compile(r"date|time|published|post-date", re.I)})
                if date_el:
                    published = date_el.get("datetime") or date_el.get_text(strip=True)

            published = normalize_tibetan_digits(published)

            # ---------- 3. 作者 ----------
            author = ld_meta.get("author") or ""
            if not author:
                author_el = soup.find(attrs={"class": re.compile(r"author|byline|writer", re.I)})
                if author_el:
                    author = author_el.get_text(strip=True)

            # ---------- 4. 正文 ----------
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
            print(f"[{site_key}] Saved ({count}/{max_articles}): {title[:40]}")

        except Exception as e:
            print(f"[{site_key}] Error scraping {url}: {e}")

    print(f"[{site_key}] Total saved: {count}")
    return count