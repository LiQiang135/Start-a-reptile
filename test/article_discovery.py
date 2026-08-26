"""Generic article candidate discovery and scoring.

This module intentionally does NOT hard-code a site's article URL structure.
It combines URL, DOM, and semantic signals to rank candidate links.

Designed to be shared by html_crawler.py and playwright_crawler.py.
"""

import re
from urllib.parse import urlparse


# Strong negative URL patterns: these are usually navigation/non-article pages.
DEFAULT_SKIP_PATTERNS = [
    r"^javascript:",
    r"^mailto:",
    r"^tel:",
    r"^#",
    r"/tag(?:/|$)",
    r"/tags(?:/|$)",
    r"/category(?:/|$)",
    r"/categories(?:/|$)",
    r"/author(?:/|$)",
    r"/authors(?:/|$)",
    r"/page/\d+(?:/|$)",
    r"/search(?:/|$|\?)",
    r"/login(?:/|$)",
    r"/register(?:/|$)",
    r"/wp-admin(?:/|$)",
    r"/wp-login\.php",
    r"/feed(?:/|$|\?)",
    r"/rss(?:/|$|\?)",
    r"/sitemap(?:/|$|\?)",
    r"/cart(?:/|$)",
    r"/checkout(?:/|$)",
    r"/account(?:/|$)",
]

# File extensions that should never be treated as article pages.
SKIP_EXTENSIONS = re.compile(
    r"\.(?:css|js|json|xml|txt|png|jpg|jpeg|gif|webp|svg|ico|pdf|zip|"
    r"mp3|mp4|avi|mov|woff|woff2|ttf)(?:[?#].*)?$",
    re.I,
)

# Positive URL hints. These are signals only, not requirements.
ARTICLE_PATH_HINTS = [
    (re.compile(r"/(?:news|article|articles)(?:/|$)", re.I), 2),
    (re.compile(r"/(?:story|stories)(?:/|$)", re.I), 2),
    (re.compile(r"/(?:post|posts)(?:/|$)", re.I), 2),
    (re.compile(r"/(?:detail|content)(?:/|$)", re.I), 2),
    (re.compile(r"/(?:latest|updates?)(?:/|$)", re.I), 1),
    (re.compile(r"/\d{4}/\d{1,2}(?:/\d{1,2})?(?:/|$)", re.I), 3),
]

# Common navigation-like paths. These receive a negative score rather than
# being automatically rejected, so unusual sites can still be recovered.
SOFT_NEGATIVE_PATHS = [
    (re.compile(r"/(?:about|contact|privacy|terms)(?:/|$)", re.I), -4),
    (re.compile(r"/(?:donate|membership|subscribe)(?:/|$)", re.I), -4),
    (re.compile(r"/(?:take-action|ways-to-give)(?:/|$)", re.I), -4),
]


def _normalize_url(url):
    """Normalize a URL enough for comparison/deduplication."""
    return url.split("#", 1)[0].strip()


def same_domain(url, base_url):
    """Return True when URL belongs to the same hostname as base_url."""
    try:
        return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()
    except Exception:
        return False


def should_skip_url(url, skip_patterns=None):
    """Return True for URLs that are clearly not article candidates."""
    if not url:
        return True

    url = _normalize_url(url)
    if SKIP_EXTENSIONS.search(url):
        return True

    patterns = skip_patterns or DEFAULT_SKIP_PATTERNS
    return any(re.search(pattern, url, re.I) for pattern in patterns)


def _looks_like_slug(url):
    """A path ending in a reasonably descriptive slug is a weak positive."""
    try:
        path = urlparse(url).path.strip("/")
    except Exception:
        return False

    if not path:
        return False

    last = path.rsplit("/", 1)[-1]

    # Avoid treating numeric IDs alone as article slugs.
    if re.fullmatch(r"\d+", last):
        return False

    # Hyphen/underscore separated descriptive slugs are common.
    if re.search(r"[-_]", last) and len(last) >= 8:
        return True

    return len(last) >= 12 and bool(re.search(r"[A-Za-z]", last))


def score_url(url, base_url, extra_positive_patterns=None,
              extra_negative_patterns=None):
    """Score a URL using only URL/domain signals."""
    if not url:
        return -100

    url = _normalize_url(url)

    if should_skip_url(url, extra_negative_patterns):
        return -100

    score = 0

    if same_domain(url, base_url):
        score += 2
    else:
        # External domains are normally not article pages for the site.
        score -= 8

    for pattern, points in ARTICLE_PATH_HINTS:
        if pattern.search(url):
            score += points

    if extra_positive_patterns:
        for pattern in extra_positive_patterns:
            if re.search(pattern, url, re.I):
                score += 1

    if extra_negative_patterns:
        for pattern in extra_negative_patterns:
            if re.search(pattern, url, re.I):
                score -= 3

    if _looks_like_slug(url):
        score += 2

    # Query-heavy URLs are more often navigation/filter URLs.
    try:
        parsed = urlparse(url)
        if parsed.query:
            score -= 1
    except Exception:
        pass

    return score


def score_link(link, base_url, extra_positive_patterns=None,
               extra_negative_patterns=None):
    """Score a rich link record from either crawler.

    Expected keys:
      href
      text
      inside_article
      has_heading
      has_time
      has_image
    Missing keys are fine.
    """
    href = _normalize_url(link.get("href", ""))
    if not href:
        return -100

    url_score = score_url(
        href,
        base_url,
        extra_positive_patterns=extra_positive_patterns,
        extra_negative_patterns=extra_negative_patterns,
    )

    if url_score <= -100:
        return url_score

    score = url_score

    text = (link.get("text") or "").strip()
    if text:
        score += 1
        if len(text) >= 20:
            score += 1

    if link.get("inside_article"):
        score += 4

    if link.get("has_heading"):
        score += 3

    if link.get("has_time"):
        score += 2

    if link.get("has_image"):
        score += 1

    return score


def discover_candidates(links, base_url, min_score=5,
                        max_candidates=100, extra_positive_patterns=None,
                        extra_negative_patterns=None):
    """Score, filter, deduplicate, and return candidate article links.

    Returns dictionaries sorted by descending score:
      {"href": ..., "score": ..., ...}
    """
    candidates = {}

    for link in links:
        href = _normalize_url(link.get("href", ""))
        if not href:
            continue

        score = score_link(
            link,
            base_url,
            extra_positive_patterns=extra_positive_patterns,
            extra_negative_patterns=extra_negative_patterns,
        )

        if score < min_score:
            continue

        existing = candidates.get(href)
        if existing is None or score > existing["score"]:
            item = dict(link)
            item["href"] = href
            item["score"] = score
            candidates[href] = item

    result = sorted(
        candidates.values(),
        key=lambda x: x["score"],
        reverse=True,
    )
    return result[:max_candidates]