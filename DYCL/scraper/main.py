"""Main orchestrator: runs crawlers for all configured sites."""
import argparse
import sys
import os

# Force UTF-8 output to handle Chinese/Tibetan characters on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from base import init_db
from config import SITES
import rss_crawler
import html_crawler
import playwright_crawler
import wayback_crawler


STRATEGY_MAP = {
    "rss": rss_crawler,
    "html": html_crawler,
    "playwright": playwright_crawler,
    "wayback": wayback_crawler,
}


def run(site_keys=None, max_articles=50):
    init_db()
    if not site_keys:
        site_keys = list(SITES.keys())
    total = 0
    for key in site_keys:
        if key not in SITES:
            print(f"Unknown site: {key}")
            continue
        cfg = SITES[key]
        strategy = cfg.get("strategy", "html")
        module = STRATEGY_MAP.get(strategy, html_crawler)
        print(f"\n{'='*60}")
        print(f"  Crawling: {cfg['name']} ({key}) [strategy={strategy}]")
        print(f"{'='*60}")
        try:
            count = module.crawl_site(key, max_articles=max_articles)
            total += count
        except Exception as e:
            print(f"[{key}] FATAL ERROR: {e}")
    print(f"\n{'='*60}")
    print(f"  All done. Total articles saved: {total}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Tibetan exile media websites")
    parser.add_argument("--sites", nargs="*", default=None, help="Site keys to crawl (default: all)")
    parser.add_argument("--max", type=int, default=50, help="Max articles per site (default: 50)")
    args = parser.parse_args()
    run(site_keys=args.sites, max_articles=args.max)