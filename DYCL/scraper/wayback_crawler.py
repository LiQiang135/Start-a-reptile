"""Wayback Machine fallback crawler for sites that block direct access.

Uses the CDX API to discover all archived URLs for a site, then fetches
each archived page to extract article content.
"""
import re
import time
from urllib.parse import urljoin, quote, urlparse

import requests

from base import (
    fetch_html, parse_soup, extract_text,
    save_article, is_scraped, polite_sleep, PROXIES,
)
from config import SITES


def get_wayback_url(original_url):
    """Get latest Wayback Machine snapshot URL for a given URL."""
    api_url = f"http://archive.org/wayback/available?url={quote(original_url)}"
    try:
        r = requests.get(api_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, proxies=PROXIES)
        data = r.json()
        closest = data.get("archived_snapshots", {}).get("closest", {})
        if closest and closest.get("available"):
            return closest.get("url", "")
    except Exception as e:
        print(f"  [wayback] API error: {e}")
    return ""


def wayback_url_to_original(wayback_url):
    """Extract original URL from a Wayback Machine URL."""
    match = re.match(r"https?://web\.archive\.org/web/\d+/(https?://.+)", wayback_url)
    if match:
        return match.group(1)
    return wayback_url


def make_wayback_snapshot_url(original_url, timestamp=""):
    """Create a Wayback Machine snapshot URL for a given original URL."""
    if timestamp:
        return f"http://web.archive.org/web/{timestamp}/{original_url}"
    return f"http://web.archive.org/web/{original_url}"


def cdx_search(domain, limit=5000, retries=3):
    """Search the Wayback CDX API for all archived URLs under a domain.

    Returns a list of (timestamp, original_url) tuples.
    """
    cdx_url = (
        f"http://web.archive.org/cdx/search/cdx"
        f"?url={domain}/*"
        f"&output=json"
        f"&fl=timestamp,original"
        f"&collapse=urlkey"
        f"&limit={limit}"
    )
    results = []
    for attempt in range(retries):
        try:
            r = requests.get(cdx_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, proxies=PROXIES)
            if r.status_code == 200:
                data = r.json()
                if len(data) > 1:
                    for row in data[1:]:
                        if len(row) >= 2:
                            results.append((row[0], row[1]))
                return results
            else:
                print(f"  [wayback] CDX API returned {r.status_code} (attempt {attempt+1}/{retries})")
        except Exception as e:
            print(f"  [wayback] CDX API error (attempt {attempt+1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(5)
    return results


def is_article_url(url, base_url):
    """Determine if a URL looks like an article/content page."""
    skip_patterns = [
        r"redirect\.php", r"login", r"register", r"search",
        r"memberlist", r"profile", r"ucp\.php", r"faq\.php",
        r"/feed/?$", r"/feed/", r"rss", r"atom", r"javascript:", r"mailto:",
        r"/tag/", r"/category/", r"/page/\d+", r"/author/",
        r"/wp-admin", r"/wp-content", r"/wp-includes",
        r"\.(css|js|png|jpg|jpeg|gif|svg|ico|xml|txt)$",
        r"mailster/form", r"iframe=1",
        r"/embed/?$", r"/embed/",
        r"/zh-hans/?$", r"/zh-hant/?$",
        r"utm_source=rss", r"\?variant=",
        r"/%C4%9F",  # Wayback encoding artifacts
        r"index\.php$",
        r"/\d+\.\d+\.\d+$",
    ]
    if any(re.search(p, url, re.I) for p in skip_patterns):
        return False

    # Normalize base_url for domain matching (handle http/https and www differences)
    base_domain = urlparse(base_url).netloc.replace("www.", "")
    try:
        url_domain = urlparse(url).netloc.replace("www.", "").replace(":80", "")
    except Exception:
        return False
    if base_domain not in url_domain and url_domain not in base_domain:
        return False

    url = re.sub(r"[?&]sid=[a-f0-9]+", "", url)
    url = re.sub(r"\?$", "", url)
    # Strip utm parameters
    url = re.sub(r"\?utm_source=.*$", "", url)

    article_patterns = [
        r"/(news|article|detail|post|content|blog)/",
        r"\d{4}/\d{2}/",
        r"\d{4}-\d{2}-\d{2}",
        r"topic\.php\?t=\d+",
        r"[?&](p|id|post|article|sid)=\d+",
        r"\.(html?|php)$",
        r"/\d{3,}",
        r"page_id=\d+",
        # URL-encoded Chinese characters (%XX patterns) indicate title-based URLs
        r"/%[eE][0-9a-fA-F]%[0-9a-fA-F]{2}%[0-9a-fA-F]{2}",
        r"/%[0-9a-fA-F]{2}%[0-9a-fA-F]{2}%[0-9a-fA-F]{2}",
    ]
    for pattern in article_patterns:
        if re.search(pattern, url, re.I):
            return True
    return False


def _extract_article(site_key, original_url, soup, content_selectors):
    """Extract article content from a parsed Wayback page."""
    # Remove Wayback Machine toolbar/overlays/banners/donation elements
    for tag in soup.find_all(id=re.compile(r"wm-|wayback|archive_|donate", re.I)):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"wm-|wayback|archive_|donate|banner|toolbar|overlay", re.I)):
        tag.decompose()
    # Remove script and style tags
    for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    # Remove Wayback Machine's inserted divs (often have wm- prefix or are at body start)
    for div in soup.find_all("div"):
        div_id = div.get("id", "")
        div_class = " ".join(div.get("class", []))
        if any(x in (div_id + div_class).lower() for x in ["wm-", "wayback", "archive_", "donate", "banner"]):
            div.decompose()

    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""

    date_el = soup.find("time") or soup.find(attrs={"class": re.compile(r"date|time|published", re.I)})
    published = ""
    if date_el:
        published = date_el.get("datetime", "") if date_el.has_attr("datetime") else date_el.get_text(strip=True)

    author_el = soup.find(attrs={"class": re.compile(r"author|byline", re.I)})
    author = author_el.get_text(strip=True) if author_el else ""

    content = extract_text(soup, content_selectors)

    # Filter out Wayback donation/banner/redirect text that slips through
    wb_filter_phrases = [
        "By submitting, you agree to receive donor-related emails",
        "Can You Chip In",
        "Your privacy is important to us",
        "We do not sell or trade your information",
        "Internet Archive",
        "Wayback Machine",
        "Got an HTTP 301 response at crawl time",
        "Got an HTTP 302 response at crawl time",
        "response at crawl time",
        "Wayback Machine hasn't archived that URL",
        "Page cannot be crawled or displayed",
    ]
    content_lines = content.split("\n")
    filtered_lines = [
        line for line in content_lines
        if not any(phrase in line for phrase in wb_filter_phrases)
    ]
    content = "\n".join(filtered_lines).strip()

    return title, author, published, content


def crawl_site(site_key, max_articles=50):
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    delay = cfg.get("delay", 3.0)
    content_selectors = cfg.get("content_selectors", [])
    print(f"[{site_key}] Starting Wayback Machine crawl of {base_url}")

    parsed = urlparse(base_url)
    domain = parsed.netloc.replace("www.", "")

    # Step 1: Use CDX API to discover all archived URLs
    print(f"[{site_key}] Querying CDX API for archived URLs under {domain}...")
    cdx_results = cdx_search(domain, limit=5000)
    print(f"[{site_key}] CDX returned {len(cdx_results)} archived URLs")

    if not cdx_results:
        print(f"[{site_key}] No CDX results, falling back to homepage link discovery")
        return _crawl_from_homepage(site_key, max_articles)

    # Step 2: Filter for article-like URLs
    article_urls = []
    seen = set()
    for timestamp, original_url in cdx_results:
        clean_url = original_url.split("#")[0]
        clean_url = re.sub(r"[?&]sid=[a-f0-9]+", "", clean_url)
        clean_url = re.sub(r"\?$", "", clean_url)
        if clean_url in seen:
            continue
        seen.add(clean_url)
        if is_article_url(clean_url, base_url):
            article_urls.append((timestamp, clean_url))

    article_urls.sort(key=lambda x: x[0], reverse=True)
    article_urls = article_urls[:max_articles + 50]
    print(f"[{site_key}] Found {len(article_urls)} article-like URLs from CDX")

    # Step 3: Fetch each article via Wayback Machine
    count = 0
    for timestamp, original_url in article_urls:
        if is_scraped(original_url) or count >= max_articles:
            continue
        # Try with CDX timestamp first (more reliable for getting actual content)
        wb_url = make_wayback_snapshot_url(original_url, timestamp)
        content = ""
        skip_url = False
        try:
            polite_sleep(delay)
            html = fetch_html(wb_url, timeout=30)
            # Check if this is a Wayback redirect/error page (not actual content)
            if "response at crawl time" in html or "hasn't archived that URL" in html:
                print(f"[{site_key}] Skip (redirect page): {original_url[:60]}")
                skip_url = True
            else:
                soup = parse_soup(html)
                title, author, published, content = _extract_article(site_key, original_url, soup, content_selectors)
        except Exception as e:
            print(f"[{site_key}] Error (timestamp) {original_url}: {e}")
            title, author, published = "", "", ""

        # If timestamp version failed or too short, try auto-redirect
        if not skip_url and len(content) < 100:
            wb_url = make_wayback_snapshot_url(original_url)
            try:
                polite_sleep(delay)
                html = fetch_html(wb_url, timeout=30)
                if "response at crawl time" in html or "hasn't archived that URL" in html:
                    print(f"[{site_key}] Skip (redirect page): {original_url[:60]}")
                    skip_url = True
                else:
                    soup = parse_soup(html)
                    title, author, published, content = _extract_article(site_key, original_url, soup, content_selectors)
            except Exception as e:
                print(f"[{site_key}] Error (auto) {original_url}: {e}")
                continue

        if skip_url or len(content) < 100:
            continue

        save_article(
            site=site_key, url=original_url, title=title, author=author,
            published=published, content=content, raw_html="",
        )
        count += 1
        print(f"[{site_key}] Saved ({count}): {title[:60]}")

    print(f"[{site_key}] Total saved: {count}")
    return count


def _crawl_from_homepage(site_key, max_articles=50):
    """Fallback: discover links from the archived homepage."""
    cfg = SITES[site_key]
    base_url = cfg["base_url"]
    delay = cfg.get("delay", 3.0)
    content_selectors = cfg.get("content_selectors", [])

    homepage_wb = get_wayback_url(base_url)
    if not homepage_wb:
        print(f"[{site_key}] No Wayback Machine snapshot available for {base_url}")
        return 0

    print(f"[{site_key}] Using Wayback snapshot: {homepage_wb}")

    count = 0
    try:
        html = fetch_html(homepage_wb, timeout=30)
    except Exception as e:
        print(f"[{site_key}] Error fetching Wayback snapshot: {e}")
        return 0

    soup = parse_soup(html)

    article_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or href == "#":
            continue
        if href.startswith("/"):
            href = urljoin("http://web.archive.org", href)
        if "web.archive.org" in href:
            original = wayback_url_to_original(href)
        else:
            original = href
        if not original.startswith("http"):
            original = urljoin(base_url + "/", original)
        if base_url not in original:
            continue
        original = re.sub(r"[?&]sid=[a-f0-9]+", "", original)
        original = re.sub(r"\?$", "", original)
        if is_article_url(original, base_url):
            article_links.add(original)

    article_links = list(article_links)[:max_articles + 20]
    print(f"[{site_key}] Found {len(article_links)} candidate links")

    for original_url in article_links:
        if is_scraped(original_url) or count >= max_articles:
            continue
        # Use auto-redirect format (no timestamp) so Wayback picks the best snapshot for each page
        wb_url = make_wayback_snapshot_url(original_url)
        try:
            polite_sleep(delay)
            html = fetch_html(wb_url, timeout=30)
            soup = parse_soup(html)
            title, author, published, content = _extract_article(site_key, original_url, soup, content_selectors)
            if len(content) < 50:
                continue
            save_article(
                site=site_key, url=original_url, title=title, author=author,
                published=published, content=content, raw_html="",
            )
            count += 1
            print(f"[{site_key}] Saved ({count}): {title[:60]}")
        except Exception as e:
            print(f"[{site_key}] Error scraping {original_url}: {e}")

    print(f"[{site_key}] Total saved: {count}")
    return count