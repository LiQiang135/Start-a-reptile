"""HTML page crawler tailored for Tibetan CMS websites (e.g., Shambala News).

URL Structure:
- Home:     http://example.com/
- Category: http://example.com/{分类}/ (e.g., /གསར་འགྱུར།/)
- Article:  http://example.com/{主分类}/{子分类}/{文章藏文标题}/
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

# 目标藏文主分类（统一保留标点）
TIBETAN_CATEGORIES = [
    "གསར་འགྱུར།",  # 新闻
    # "དཔྱད་གླེང༌།"
    # "དཔྱད་གླེང༌།",  # 评论
    # "བོད་སྐོར།",  # 关于西藏
    # "མང་གཙོ།",  # 民主
]

# ==================== 藏文日期与数字映射 ====================
TIBETAN_DIGITS = {
    "༠": "0", "༡": "1", "༢": "2", "༣": "3", "༤": "4",
    "༥": "5", "༦": "6", "༧": "7", "༨": "8", "༩": "9",
}

TIBETAN_MONTHS = {
    "ཟླ་བ་དང་པོ": "01",
    "ཟླ་བ་གཉིས་པ": "02",
    "ཟླ་བ་གསུམ་པ": "03",
    "ཟླ་བ་བཞི་པ": "04",
    "ཟླ་བ་ལྔ་པ": "05",
    "ཟླ་བ་དྲུག་པ": "06",
    "ཟླ་བ་བདུན་པ": "07",
    "ཟླ་བ་བརྒྱད་པ": "08",
    "ཟླ་བ་དགུ་པ": "09",
    "ཟླ་བ་བཅུ་པ": "10",
    "ཟླ་བ་བཅུ་གཅིག་པ": "11",
    "ཟླ་བ་བཅུ་གཉིས་པ": "12",
}


def normalize_tibetan_digits(text: str) -> str:
    """将文本中的藏文数字转为阿拉伯数字。"""
    if not text:
        return ""
    for tib_d, arab_d in TIBETAN_DIGITS.items():
        text = text.replace(tib_d, arab_d)
    return text


def parse_tibetan_date(text: str) -> str:
    """解析纯藏文自然语言日期并规范化为 YYYY-MM-DD，未匹配则返回阿拉伯数字格式文本。"""
    if not text:
        return ""

    normalized = normalize_tibetan_digits(text.strip())
    pattern = re.compile(r"(\d{1,2})\s*(ཟླ་བ་[^\s\d]+)\s*(\d{4})", re.UNICODE)
    match = pattern.search(normalized)
    if match:
        day, raw_month, year = match.groups()
        month = TIBETAN_MONTHS.get(raw_month.strip("།").strip())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    return normalized


def extract_published_date(soup, ld_meta: dict) -> str:
    """按设定优先级提取发布日期（优先从 class 容器中捕获）。"""
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

    if not raw_date:
        class_el = soup.find(attrs={"class": re.compile(r"date|time|published|post-date", re.I)})
        if class_el:
            raw_date = class_el.get("datetime") or class_el.get_text(strip=True)

    # 2. 第二优先：HTML5 <time> 标签
    if not raw_date:
        time_el = soup.find("time")
        if time_el:
            raw_date = time_el.get("datetime") or time_el.get_text(strip=True)

    # 3. 第三优先：Meta 标签
    if not raw_date:
        meta = soup.find("meta", property=re.compile(r"^(article|og):published_time$"))
        if meta and meta.get("content"):
            raw_date = meta.get("content").strip()

    # 4. 兜底回退：结构化数据 ld+json
    if not raw_date:
        raw_date = ld_meta.get("published", "")

    # 统一出口解析转换
    return parse_tibetan_date(raw_date)


def is_same_domain(url: str, base_url: str) -> bool:
    """通过 netloc 校验域名，规避 URL 编码/未编码导致的字符串前缀不匹配。"""
    return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()


def is_tibetan_article_link(url: str) -> bool:
    """基于纯路径层级判断是否为藏文详情页。"""
    if not url:
        return False

    decoded_url = unquote(url)
    clean_path = urlparse(decoded_url).path.strip("/")
    segments = [seg for seg in clean_path.split("/") if seg]

    # 过滤分页、标签、作者汇总
    if any(seg.lower() in ("page", "tag", "author", "search") for seg in segments):
        return False

    # 至少存在主分类与文章两级
    if len(segments) < 2:
        return False

    # 根路径命中目标分类
    first_seg = segments[0].rstrip("།")
    return any(first_seg == cat.rstrip("།") for cat in TIBETAN_CATEGORIES)


def get_seed_urls(base_url: str) -> list:
    """仅生成真实存在的首页与目标藏文分类入口。"""
    seeds = [base_url]
    for cat in TIBETAN_CATEGORIES:
        seeds.append(urljoin(base_url, f"/{cat}/"))
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
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

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
    """解析文章标准 ld+json 结构化数据。"""
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
                        meta["author"] = (
                            first_author.get("name", "")
                            if isinstance(first_author, dict)
                            else str(first_author)
                        )
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

            # ---------- 1. 标题提取与清洗 ----------
            h1 = soup.find("h1")
            og = soup.find("meta", property="og:title")
            title = (
                ld_meta.get("title")
                or (h1.get_text(strip=True) if h1 else "")
                or (og.get("content", "").strip() if og else "")
                or (soup.title.get_text(strip=True) if soup.title else "")
            )

            # 去除网站后缀（兼顾藏文标点与中英文横杠）
            for sep in ("། །", " ། ", " - ", " | "):
                if sep in title:
                    parts = title.split(sep)
                    if len(parts) >= 2:
                        title = sep.join(parts[:-1]).strip()

            # ---------- 2. 优先通过 class 体系提取时间 ----------
            published = extract_published_date(soup, ld_meta)

            # ---------- 3. 作者 ----------
            author = ld_meta.get("author") or ""
            if not author:
                author_el = soup.find(attrs={"class": re.compile(r"author|byline|writer", re.I)})
                if author_el:
                    author = author_el.get_text(strip=True)

            # ---------- 4. 正文提取 ----------
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