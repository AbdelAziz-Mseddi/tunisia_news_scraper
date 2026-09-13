"""
Mosaique FM scraper.

Mosaique's site is a Next.js SPA: category listing pages are rendered
client-side (a plain `requests.get` on a listing page returns almost no
usable HTML), but individual ARTICLE pages have their <title>,
og:title, and og:description server-rendered into <head>, even though
the body text is not. See config.py for more context.

This module ships two strategies:

1. MosaiqueMetaScraper: takes a list of already-known article URLs
   (e.g. collected from Google/Bing search results, their public RSS
   if you find one, or manual/other discovery) and extracts title +
   short summary from each via plain HTTP requests. Cheap and fast,
   but gives you title + ~1-sentence summary only, not full body.

2. MosaiquePlaywrightScraper: uses a headless browser to actually
   render the listing page's JavaScript, so it can discover article
   URLs on its own, and can optionally also render each article page
   to extract the full body text. Slower and requires
   `playwright install chromium` to have been run once.

Use (1) for a lightweight, high-frequency title-only feed (matches
your "detect region mainly from the title" requirement almost for
free), and (2) periodically (e.g. once a day) to backfill full bodies
for articles you want deeper NLP confirmation on.
"""

import re
from typing import List, Optional

import requests

from bs4 import BeautifulSoup

from config import MOSAIQUE_BASE, MOSAIQUE_REGIONAL_LISTING, MOSAIQUE_LANGUAGE, USER_AGENT, REQUEST_TIMEOUT
from models import Article
from scrapers.base import BaseScraper


class MosaiqueMetaScraper(BaseScraper):
    """Cheap title+summary extraction for a known list of article URLs."""

    source_name = "mosaique"

    def __init__(self, article_urls: List[str]):
        super().__init__()
        self.article_urls = article_urls

    def fetch(self) -> List[Article]:
        articles: List[Article] = []
        for url in self.article_urls:
            try:
                articles.append(self._fetch_one(url))
            except Exception as e:
                print(f"[mosaique] failed to fetch {url}: {e}")
        return articles

    def _fetch_one(self, url: str) -> Article:
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._meta(soup, "og:title") or (soup.title.string if soup.title else "")
        summary = self._meta(soup, "og:description") or ""
        image_url = self._meta(soup, "og:image")
        category = "regional" if "actualite-regional-tunisie" in url else None

        return Article(
            source=self.source_name,
            url=url,
            title=(title or "").strip(),
            body="",              # not available without rendering JS
            summary=summary.strip(),
            category=category,
            published_at=None,    # not exposed in <head>; needs Playwright or an API
            language=MOSAIQUE_LANGUAGE,
            image_url=image_url,
            method="meta_only",
        )

    @staticmethod
    def _meta(soup: BeautifulSoup, prop: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find(
            "meta", attrs={"name": prop}
        )
        return tag["content"].strip() if tag and tag.has_attr("content") else None


class MosaiquePlaywrightScraper:
    """
    Renders the JS listing page to discover article URLs, then
    optionally renders each article page to pull the full body.

    Not a BaseScraper subclass because Playwright's async/sync API
    doesn't mix cleanly with the simple requests.Session used
    elsewhere; kept as its own small, explicit class instead.

    Usage:
        scraper = MosaiquePlaywrightScraper()
        urls = scraper.discover_article_urls(max_scroll=5)
        articles = scraper.fetch_full_articles(urls)
    """

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "playwright is required for MosaiquePlaywrightScraper. "
                "Install with `pip install playwright` then `playwright install chromium`."
            ) from e

    def _discover_from_sitemap(self) -> List[str]:
        sitemap_url = "https://www.mosaiquefm.net/fr/sitemap/news.xml"
        resp = requests.get(sitemap_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()

        urls = set()
        for match in re.findall(r"https://www\.mosaiquefm\.net/fr/actualite-regional-tunisie/\d+/[^\s<]+", resp.text):
            urls.add(match)
        return list(urls)

    def discover_article_urls(
        self, listing_url: str = MOSAIQUE_REGIONAL_LISTING, max_scroll: int = 5
    ) -> List[str]:
        try:
            urls = self._discover_from_sitemap()
            if urls:
                return urls
        except Exception as e:
            print(f"[mosaique] sitemap discovery failed, falling back to Playwright: {e}")

        from playwright.sync_api import sync_playwright

        urls = set()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(listing_url, wait_until="commit", timeout=60000)
            page.wait_for_timeout(5000)

            for _ in range(max_scroll):
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(1000)  # let lazy-loaded content settle

            anchors = page.query_selector_all("a[href*='/fr/actualite-regional-tunisie/']")
            for a in anchors:
                href = a.get_attribute("href")
                if href:
                    urls.add(href if href.startswith("http") else MOSAIQUE_BASE + href)

            browser.close()
        return list(urls)

    def fetch_full_articles(self, urls: List[str]) -> List[Article]:
        from playwright.sync_api import sync_playwright

        articles: List[Article] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for url in urls:
                try:
                    page.goto(url, wait_until="commit", timeout=60000)
                    page.wait_for_timeout(2000)
                    title = page.title()
                    # Heuristic: Next.js apps usually render the main
                    # article text inside <article> or <main>; adjust
                    # this selector once you've inspected real devtools
                    # output for this site.
                    body_el = page.query_selector("article") or page.query_selector("main")
                    body = body_el.inner_text() if body_el else ""

                    articles.append(
                        Article(
                            source="mosaique",
                            url=url,
                            title=title.strip(),
                            body=body.strip(),
                            category="regional" if "actualite-regional-tunisie" in url else None,
                            language=MOSAIQUE_LANGUAGE,
                            method="playwright",
                        )
                    )
                except Exception as e:
                    print(f"[mosaique/playwright] failed on {url}: {e}")

            browser.close()
        return articles
