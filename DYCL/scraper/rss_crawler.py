"""RSS feed crawler for WordPress-based sites (phayul, tibetpost)."""
import re
import warnings
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

from base import fetch_html, parse_soup, extract_text, save_article, is_scraped, polite_sleep
from config import SITES

# Suppress XML-parsed-as-HTML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def parse_feed(feed_url):
    """Parse RSS/Atom feed, return list of item dicts."""
    html = fetch_html(feed_url)
    # Use XML parser for RSS feeds to avoid <link/> self-closing issue
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
        entry["summary"] = desc.get_text(strip=True) if desc else ""
        # content:encoded often has full article
        content = item.find("content:encoded")
        if content:
            entry["full_content"] = content.get_text(strip=True)
        items.append(entry)
    # Atom feed fallback
    if not items:
        for entry in soup.find_all("entry"):
            e = {}
            t = entry.find("title")
            e["title"] = t.get_text(strip=True) if t else ""
            l = entry.find("link")
            e["link"] = l.get("href", "") if l else ""
            d = entry.find("published") or entry.find("updated")
            e["published"] = d.get_text(strip=True) if d else ""
            a = entry.find("author")
            e["author"] = a.get_text(strip=True) if a else ""
            s = entry.find("summary")
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


def crawl_site(site_key, max_articles=50, max_pages=20):
    """
    抓取站点 RSS，支持 WordPress 的 ?paged= 翻页。

    :param max_articles: 本站最多保存多少篇（对应配置里的上限）
    :param max_pages:    最多翻多少页，防止无限循环
    """
    cfg = SITES[site_key]
    feed_url = cfg["feed_url"]
    selectors = cfg.get("content_selectors", [])
    delay = cfg.get("delay", 2.0)

    print(f"[{site_key}] 开始抓取，目标最多 {max_articles} 篇，最多翻 {max_pages} 页")
    count = 0
    page = 1
    seen_urls = set()          # 防止同一篇文章在不同页重复出现

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
            try:
                full = item.get("full_content", "")
                if full and len(full) > 200:
                    # 优先使用 RSS 自带的全文
                    content_soup = parse_soup(full)
                    content = extract_text(content_soup, selectors)
                else:
                    # 否则去抓取文章页面
                    polite_sleep(delay)
                    html = fetch_html(url)
                    soup = parse_soup(html)
                    content = extract_text(soup, selectors)
            except Exception as e:
                print(f"[{site_key}] 提取内容失败 {url}: {e}")
                content = item.get("summary", "")

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

        # 如果这一页完全没有新文章，说明后面也没必要再翻了
        if new_in_this_page == 0:
            print(f"[{site_key}] 第 {page} 页没有新文章，停止翻页")
            break

        page += 1
        # 翻页之间也稍微休息一下，更礼貌
        if page <= max_pages and count < max_articles:
            polite_sleep(delay)

    print(f"[{site_key}] 完成，共保存 {count} 篇")
    return count