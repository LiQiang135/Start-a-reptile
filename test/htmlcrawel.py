#!/usr/bin/env python3
"""
Standalone HTML page crawler for Free Tibet (and similar sites).
- Prioritizes content inside <article> tags
- Supports proxy
- Auto retry + better link filtering
"""

import os
import re
import json
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ====================== 代理配置 ======================
# 不需要代理就改成 PROXIES = None
PROXIES = {
    "http":  "http://127.0.0.1:7897",      # ← 改成你的代理地址
    "https": "http://127.0.0.1:7897",
}
# PROXIES = None


# ====================== 站点配置 ======================
SITES = {
    "freetibet": {
        "name": "Free Tibet",
        "base_url": "https://freetibet.org",
        "delay": 2.5,
        "content_selectors": [
            "article",                  # 最高优先级
            ".entry-content",
            "article .content",
            ".post-content",
            ".content",
            "main",
        ],
        "listing_paths": [
            "/latest",                  # Free Tibet 主要文章列表
        ],
    },
}

# 输出目录
OUTPUT_DIR = Path("scraped_articles")
OUTPUT_DIR.mkdir(exist_ok=True)

# 已抓取记录
SCRAPED_DB = OUTPUT_DIR / "scraped_urls.json"


# ====================== 工具函数 ======================

def load_scraped():
    if SCRAPED_DB.exists():
        with open(SCRAPED_DB, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_scraped(urls: set):
    with open(SCRAPED_DB, "w", encoding="utf-8") as f:
        json.dump(sorted(list(urls)), f, ensure_ascii=False, indent=2)


SCRAPED = load_scraped()


def is_scraped(url: str) -> bool:
    return url in SCRAPED


def mark_scraped(url: str):
    SCRAPED.add(url)
    save_scraped(SCRAPED)


def polite_sleep(seconds: float = 2.0):
    time.sleep(seconds)


def fetch_html(url: str, timeout: int = 35, max_retries: int = 3) -> str:
    """带重试的请求函数，支持代理"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url,
                headers=headers,
                proxies=PROXIES,
                timeout=timeout,
                verify=True,
            )
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            last_exception = e
            print(f"    [retry {attempt}/{max_retries}] {url} → {type(e).__name__}: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    raise last_exception


def parse_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_text(soup: BeautifulSoup, selectors: list) -> str:
    """优先提取 <article> 标签内容"""
    # 策略1：优先真实 <article> 标签（取最长的那个）
    articles = soup.find_all("article")
    if articles:
        best = max(articles, key=lambda a: len(a.get_text(strip=True)))
        text = best.get_text(separator="\n", strip=True)
        if len(text) > 80:
            return clean_text(text)

    # 策略2：使用配置的 CSS 选择器
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 80:
                return clean_text(text)

    # 策略3：兜底 body
    body = soup.find("body")
    if body:
        return clean_text(body.get_text(separator="\n", strip=True))

    return ""


def save_article(site: str, url: str, title: str, author: str, published: str, content: str):
    """保存为 JSON + TXT"""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug)[:60].strip("-")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    filename = f"{site}_{slug}_{url_hash}.json"

    data = {
        "site": site,
        "url": url,
        "title": title,
        "author": author,
        "published": published,
        "scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "content": content,
        "content_length": len(content),
    }

    out_path = OUTPUT_DIR / filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 同时保存可读 TXT
    txt_path = out_path.with_suffix(".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        f.write(f"URL: {url}\n")
        f.write(f"Author: {author}\n")
        f.write(f"Published: {published}\n")
        f.write(f"Scraped: {data['scraped_at']}\n")
        f.write("-" * 60 + "\n\n")
        f.write(content)

    mark_scraped(url)
    return out_path


# ====================== 链接发现 ======================

ARTICLE_PATTERNS = [
    re.compile(r"/latest/", re.I),           # Free Tibet 主要路径
    re.compile(r"/article/", re.I),
    re.compile(r"/news/", re.I),
    re.compile(r"/post/", re.I),
    re.compile(r"/story/", re.I),
    re.compile(r"/\d{4}/\d{2}/", re.I),
    re.compile(r"/\d{4}/\d{2}/\d{2}/", re.I),
    re.compile(r"\.(html?|php)$", re.I),
    re.compile(r"/detail/", re.I),
    re.compile(r"/content/", re.I),
    re.compile(r"/campaigns?/", re.I),
]


def is_article_link(href: str, base_url: str) -> bool:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return False

    full = urljoin(base_url, href)
    if not full.startswith(base_url):
        return False

    parsed = urlparse(full)
    path = parsed.path.rstrip("/")

    # 排除带筛选参数的页面
    if parsed.query and ("filter_" in parsed.query or "filter_submit" in parsed.query):
        return False

    # 排除纯列表页
    if path in ("", "/latest", "/news", "/campaigns", "/about"):
        return False

    # 排除分类、标签、分页等
    if re.search(r"/(tag|category|page|author|search|filter)/", path, re.I):
        return False

    return any(p.search(path) for p in ARTICLE_PATTERNS)


def discover_links(base_url: str, listing_paths: list = None, max_links: int = 120) -> list:
    urls_to_check = [base_url.rstrip("/")]
    if listing_paths:
        for path in listing_paths:
            urls_to_check.append(urljoin(base_url, path))

    discovered = set()
    for page_url in urls_to_check:
        try:
            print(f"  [discover] Fetching {page_url}")
            html = fetch_html(page_url)
            soup = parse_soup(html)
        except Exception as e:
            print(f"  [discover] Error fetching {page_url}: {e}")
            continue

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if is_article_link(href, base_url):
                full_url = urljoin(base_url, href).split("#")[0]
                discovered.add(full_url)

        if len(discovered) >= max_links:
            break
        polite_sleep(1.2)

    return list(discovered)[:max_links]


# ====================== 主爬取逻辑 ======================

def crawl_site(site_key: str, max_articles: int = 30):
    if site_key not in SITES:
        raise ValueError(f"Unknown site: {site_key}. Available: {list(SITES.keys())}")

    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    selectors = cfg.get("content_selectors", ["article", ".entry-content", "main"])
    delay = cfg.get("delay", 2.5)
    listing_paths = cfg.get("listing_paths", [])

    print(f"\n[{site_key}] Starting crawl of {cfg['name']} ({base_url})")
    print(f"[{site_key}] Content strategy: prioritize <article> tags")

    links = discover_links(base_url, listing_paths=listing_paths)
    print(f"[{site_key}] Found {len(links)} candidate article links")

    count = 0
    for url in links:
        if is_scraped(url):
            print(f"[{site_key}] Already scraped: {url}")
            continue
        if count >= max_articles:
            break

        try:
            polite_sleep(delay)
            print(f"[{site_key}] Scraping: {url}")
            html = fetch_html(url)
            soup = parse_soup(html)

            # 标题
            title_el = soup.find("h1") or soup.find("title")
            title = title_el.get_text(strip=True) if title_el else "Untitled"

            # 日期
            published = ""
            date_el = (
                soup.find("time")
                or soup.find(attrs={"class": re.compile(r"date|time|published", re.I)})
                or soup.find(attrs={"itemprop": "datePublished"})
            )
            if date_el:
                published = date_el.get("datetime") or date_el.get_text(strip=True)

            # 作者
            author = ""
            author_el = (
                soup.find(attrs={"class": re.compile(r"author|byline|writer", re.I)})
                or soup.find(attrs={"rel": "author"})
                or soup.find(attrs={"itemprop": "author"})
            )
            if author_el:
                author = author_el.get_text(strip=True)

            # 正文（优先 <article>）
            content = extract_text(soup, selectors)

            if len(content) < 80:
                print(f"[{site_key}] Content too short, skipping: {url}")
                continue

            path = save_article(
                site=site_key,
                url=url,
                title=title,
                author=author,
                published=published,
                content=content,
            )
            count += 1
            print(f"[{site_key}] Saved ({count}): {title[:70]}")
            print(f"         → {path}")

        except Exception as e:
            print(f"[{site_key}] Error scraping {url}: {e}")

    print(f"\n[{site_key}] Finished. Newly saved: {count}")
    return count


# ====================== 入口 ======================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Free Tibet 等站点爬虫")
    parser.add_argument("--site", default="freetibet", choices=list(SITES.keys()))
    parser.add_argument("--max", type=int, default=25, help="最多抓取多少篇新文章")
    args = parser.parse_args()

    crawl_site(args.site, max_articles=args.max)