"""Base crawler: HTTP client, parsing, storage, dedup."""
import hashlib
import json
import os
import re
import time
import sqlite3
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "articles.db")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,bo;q=0.6",
}


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def init_db():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT NOT NULL,
            url TEXT NOT NULL,
            url_hash TEXT UNIQUE NOT NULL,
            title TEXT,
            author TEXT,
            published TEXT,
            scraped_at TEXT NOT NULL,
            content TEXT,
            raw_html TEXT,
            summary TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_site ON articles(site)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_url_hash ON articles(url_hash)")
    conn.commit()
    conn.close()


def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def is_scraped(url):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT 1 FROM articles WHERE url_hash=?", (url_hash(url),))
    found = cur.fetchone() is not None
    conn.close()
    return found


def save_article(site, url, title, author, published, content, raw_html="", summary=""):
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO articles (site,url,url_hash,title,author,published,scraped_at,content,raw_html,summary) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (site, url, url_hash(url), title, author, published,
             datetime.utcnow().isoformat(), content, raw_html, summary),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    # Also save as individual JSON for convenience
    site_dir = os.path.join(DATA_DIR, site)
    os.makedirs(site_dir, exist_ok=True)
    fname = os.path.join(site_dir, f"{url_hash(url)}.json")
    if not os.path.exists(fname):
        with open(fname, "w", encoding="utf-8") as f:
            json.dump({
                "site": site, "url": url, "title": title, "author": author,
                "published": published, "scraped_at": datetime.utcnow().isoformat(),
                "content": content, "summary": summary,
            }, f, ensure_ascii=False, indent=2)


# Use explicit proxy for accessing blocked sites (e.g., web.archive.org is blocked by GFW).
# The proxy address matches the Windows system proxy (Clash on 127.0.0.1:7897).
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}


def fetch_html(url, timeout=30):
    """Fetch HTML with robust encoding detection.

    Priority: HTTP Content-Type charset > HTML meta charset > apparent_encoding > utf-8.
    Also fixes a common chardet false positive where UTF-8 is misdected as ISO-8859-1.
    """
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, proxies=PROXIES)
    resp.raise_for_status()
    raw = resp.content  # raw bytes

    # 1. Check HTTP response headers for charset
    content_type = resp.headers.get("Content-Type", "").lower()
    header_encoding = None
    if "charset=" in content_type:
        header_encoding = content_type.split("charset=")[-1].split(";")[0].strip()

    # 2. Check HTML meta tags for charset (within first 4 KB)
    meta_match = re.search(
        rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_-]+)', raw[:4096], re.I
    )
    meta_encoding = (
        meta_match.group(1).decode("ascii", errors="ignore") if meta_match else None
    )

    # 3. Determine encoding with sensible priority
    encoding = header_encoding or meta_encoding or resp.apparent_encoding or "utf-8"

    # 4. Common chardet false-positive: UTF-8 content misdected as ISO-8859-1
    if encoding.lower() in ("iso-8859-1", "latin-1"):
        try:
            raw.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            pass  # keep detected encoding

    return raw.decode(encoding, errors="replace")


def parse_soup(html):
    return BeautifulSoup(html, "lxml")


def extract_text(soup, selectors=None):
    """Try multiple CSS selectors to find article body, return cleaned text.

    Filters out navigation menus, sidebars, widgets, related posts, ads, and
    other non-article elements that may appear inside the selected container.
    """
    # Tags and class/id patterns to remove as noise
    NOISE_TAGS = [
        "script", "style", "nav", "footer", "header", "aside", "form",
        "noscript", "iframe",
    ]
    NOISE_CLASS_PATTERNS = [
        re.compile(r"\b(nav|menu|sidebar|widget|comment|related|share|social|"
                   r"advertisement|ad-|ads-|banner|breadcrumb|pagination|"
                   r"copyright|footer|header|subscribe|newsletter|popup|"
                   r"modal|overlay|cookie|consent|skip-link|screen-reader)\b", re.I),
    ]
    NOISE_ID_PATTERNS = [
        re.compile(r"^(nav|menu|sidebar|comment|header|footer|respond|"
                   r"related|share|social|ad|banner)", re.I),
    ]

    def _strip_noise(container):
        """Remove noise tags and elements with noise class/id from container."""
        # Remove noise tags
        for tag in container.find_all(NOISE_TAGS):
            tag.decompose()
        # Remove elements with noise class patterns
        for el in container.find_all(attrs={"class": True}):
            classes = " ".join(el.get("class", []))
            if any(pat.search(classes) for pat in NOISE_CLASS_PATTERNS):
                el.decompose()
        # Remove elements with noise id patterns
        for el in container.find_all(attrs={"id": True}):
            el_id = el.get("id", "")
            if any(pat.search(el_id) for pat in NOISE_ID_PATTERNS):
                el.decompose()
        # Remove empty divs (cleanup)
        for div in container.find_all("div"):
            if not div.get_text(strip=True) and not div.find(["img", "video", "audio"]):
                div.decompose()

    if selectors:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                _strip_noise(el)
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 50:
                    return text

    # Fallback: collect <p> tags, filtering noise
    body = soup.find("body") or soup
    _strip_noise(body)
    paragraphs = body.find_all("p")
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
    if len(text) > 50:
        return text
    # Last resort
    return body.get_text(separator="\n", strip=True)


def polite_sleep(delay=2.0):
    time.sleep(delay)