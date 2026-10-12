"""RSS feed crawler for WordPress-based sites (phayul, tibetpost, tibettimes)."""
import re
import warnings
from html import unescape
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

from base import fetch_html, parse_soup, extract_text, save_article, is_scraped, polite_sleep
from config import SITES

# Suppress XML-parsed-as-HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# WordPress / Yoast 在 excerpt 末尾拼的样板句
# 注意：藏文会紧贴 The post / on，不能用 \b
_WP_FOOTER_RE = re.compile(
    r"The\s+post.*?appeared\s+first\s+on.*$",
    re.I | re.S,
)
_SHARE_RE = re.compile(r"(?:Share on\s+\w+\s*)+", re.I)

def clean_wp_boilerplate(text: str) -> str:
    """去掉 appeared first on 样板与分享按钮文案。"""
    if not text:
        return ""
    text = _WP_FOOTER_RE.sub("", text)
    text = _SHARE_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_junk_content(text: str) -> bool:
    """正文是否过短，或实质只剩 WP 摘录样板。"""
    if not text:
        return True
    cleaned = clean_wp_boilerplate(text)
    if len(cleaned) < 50:
        return True
    if re.search(r"appeared\s+first\s+on", text, re.I) and len(cleaned) < 80:
        return True
    return False


def _feed_full_trustworthy(raw: str) -> bool:
    """content:encoded 是否像真全文，而不是长标题摘录。"""
    if not raw or len(raw) < 200:
        return False
    cleaned = clean_wp_boilerplate(raw)
    if len(cleaned) < 200:
        return False
    # 去掉样板后开头仍是 The post → 整段就是摘录
    if re.match(r"The\s+post\b", cleaned, re.I):
        return False
    # 至少应有较多非空白字符（藏文正文）
    body = re.sub(r"\s+", "", cleaned)
    return len(body) >= 150


def parse_feed(feed_url):
    """Parse RSS/Atom feed, return list of item dicts."""
    html = fetch_html(feed_url)
    try:
        soup = BeautifulSoup(html, "xml")
    except Exception:
        soup = parse_soup(html)
    items = []
    for item in soup.find_all("item"):
        entry = {}
        t = item.find("title")
        entry["title"] = t.get_text(strip=True) if t else ""
        l = item.find("link")
        entry["link"] = l.get_text(strip=True) if l else ""
        d = item.find("pubDate")
        entry["published"] = d.get_text(strip=True) if d else ""
        a = item.find("creator")
        entry["author"] = a.get_text(strip=True) if a else ""
        desc = item.find("description")
        if desc is None:
            entry["summary"] = ""
        else:
            raw_desc = desc.decode_contents() if hasattr(desc, "decode_contents") else desc.get_text()
            entry["summary"] = unescape(raw_desc)
        # content:encoded 保留 HTML（feed 常做实体转义，需 unescape）
        content = item.find("content:encoded") or item.find("encoded")
        if content is not None:
            if hasattr(content, "decode_contents"):
                raw_c = content.decode_contents()
            else:
                raw_c = str(content)
            # 优先取节点文本中的转义 HTML，再 unescape 成真实标签
            if content.string:
                raw_c = content.string
            entry["full_content"] = unescape(raw_c)
        items.append(entry)
    if not items:
        for entry_el in soup.find_all("entry"):
            e = {}
            t = entry_el.find("title")
            e["title"] = t.get_text(strip=True) if t else ""
            l = entry_el.find("link")
            e["link"] = l.get("href", "") if l else ""
            d = entry_el.find("published") or entry_el.find("updated")
            e["published"] = d.get_text(strip=True) if d else ""
            a = entry_el.find("author")
            e["author"] = a.get_text(strip=True) if a else ""
            s = entry_el.find("summary")
            e["summary"] = s.get_text(strip=True) if s else ""
            items.append(e)
    return items


def build_paged_url(feed_url, page):
    """给 WordPress RSS 地址加上 ?paged=N 参数"""
    if page <= 1:
        return feed_url
    parsed = urlparse(feed_url)
    qs = parse_qs(parsed.query)
    qs["paged"] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _extract_from_html(html: str, selectors) -> str:
    soup = parse_soup(html)
    return clean_wp_boilerplate(extract_text(soup, selectors))


def crawl_site(site_key, max_articles=50, max_pages=10):
    cfg = SITES[site_key]
    feed_url = cfg["feed_url"]
    selectors = cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] 开始抓取，目标最多 {max_articles} 篇，最多翻 {max_pages} 页")
    count = 0
    page = 1
    seen_urls = set()
    consecutive_empty_new = 0
    max_consecutive_empty = 2

    while count < max_articles and page <= max_pages:
        current_url = build_paged_url(feed_url, page)
        print(f"[{site_key}] 正在获取第 {page} 页: {current_url}")

        try:
            items = parse_feed(current_url)
        except Exception as e:
            print(f"[{site_key}] 第 {page} 页获取失败: {e}")
            break

        if not items:
            print(f"[{site_key}] 第 {page} 页没有条目，停止翻页")
            break

        print(f"[{site_key}] 第 {page} 页找到 {len(items)} 条")

        new_in_this_page = 0
        for item in items:
            url = item.get("link", "").strip()
            if not url or url in seen_urls or is_scraped(url):
                continue

            seen_urls.add(url)
            if count >= max_articles:
                break

            content = ""
            full = item.get("full_content", "") or ""
            try:
                if _feed_full_trustworthy(full):
                    content = _extract_from_html(full, selectors)
                if is_junk_content(content):
                    polite_sleep(delay)
                    page_html = fetch_html(url)
                    content = _extract_from_html(page_html, selectors)
            except Exception as e:
                print(f"[{site_key}] 提取内容失败 {url}: {e}")
                content = ""

            if is_junk_content(content):
                print(f"[{site_key}] 跳过（正文无效/仅摘录样板）: {url}")
                continue

            save_article(
                site=site_key,
                url=url,
                title=item.get("title", ""),
                author=item.get("author", ""),
                published=item.get("published", ""),
                content=content,
                summary=item.get("summary", ""),
            )
            count += 1
            new_in_this_page += 1
            print(f"[{site_key}] 已保存 ({count}/{max_articles}): {item.get('title', '')[:60]}")

        if new_in_this_page == 0:
            consecutive_empty_new += 1
            print(f"[{site_key}] 第 {page} 页没有新文章（连续 {consecutive_empty_new} 页）")
            if consecutive_empty_new >= max_consecutive_empty:
                print(f"[{site_key}] 连续 {max_consecutive_empty} 页没有新文章，停止翻页")
                break
        else:
            consecutive_empty_new = 0

        page += 1
        if page <= max_pages and count < max_articles:
            polite_sleep(delay)

    print(f"[{site_key}] 完成，共保存 {count} 篇")
    return count
