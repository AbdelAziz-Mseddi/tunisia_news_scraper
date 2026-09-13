"""
Orchestrator: run every configured scraper and persist results.

Usage:
    uv run tunisia-scrape                # run all "cheap" scrapers (RSS + HTML)
    uv run tunisia-scrape --with-mosaique-playwright   # also crawl Mosaique via headless browser
    uv run tunisia-scrape --stats        # just print DB stats and exit

This is intentionally simple (a straight-line script, no task queue)
so it's easy to run by hand or drop into a daily cron job:
    0 * * * *  cd /path/to/project && uv run tunisia-scrape >> scrape.log 2>&1
"""

import argparse

from config import (
    DB_PATH,
    NESSMA_RSS_FEEDS, NESSMA_LANGUAGE,
    ELHIWAR_SCRAPING_ALLOWED,
)
from storage import init_db, save_articles, get_stats
from scrapers.rss_scraper import RSSScraper
from scrapers.watania_scraper import WataniaScraper


def run_nessma() -> int:
    scraper = RSSScraper("nessma", NESSMA_RSS_FEEDS, NESSMA_LANGUAGE)
    articles = scraper.fetch()
    print(f"[nessma] fetched {len(articles)} articles")
    return save_articles(DB_PATH, articles)


def run_watania() -> int:
    scraper = WataniaScraper()
    articles = scraper.fetch()
    print(f"[watania] fetched {len(articles)} articles")
    return save_articles(DB_PATH, articles)


def run_mosaique_playwright() -> int:
    from scrapers.mosaique_scraper import MosaiquePlaywrightScraper

    scraper = MosaiquePlaywrightScraper()
    urls = scraper.discover_article_urls()
    print(f"[mosaique] discovered {len(urls)} article URLs")
    articles = scraper.fetch_full_articles(urls)
    print(f"[mosaique] rendered {len(articles)} full articles")
    return save_articles(DB_PATH, articles)


def print_stats():
    print("\n--- DB stats (source, category, count) ---")
    for source, category, count in get_stats(DB_PATH):
        print(f"  {source:12s} {category or '-':15s} {count}")


def main():
    parser = argparse.ArgumentParser(description="Tunisia regional news scraper")
    parser.add_argument(
        "--with-mosaique-playwright",
        action="store_true",
        help="Also crawl Mosaique FM via a headless browser (slower, needs `playwright install chromium`).",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Just print DB stats and exit."
    )
    args = parser.parse_args()

    init_db(DB_PATH)

    if args.stats:
        print_stats()
        return

    total_new = 0
    total_new += run_nessma()
    total_new += run_watania()

    if not ELHIWAR_SCRAPING_ALLOWED:
        print("[elhiwar] skipped: robots.txt disallows automated access "
              "(see config.py -- request permission from the outlet if you need this source)")

    if args.with_mosaique_playwright:
        total_new += run_mosaique_playwright()
    else:
        print("[mosaique] skipped full crawl (pass --with-mosaique-playwright to enable). "
              "Use MosaiqueMetaScraper directly if you already have a list of article URLs.")

    print(f"\nTotal new articles saved this run: {total_new}")
    print_stats()


if __name__ == "__main__":
    main()
