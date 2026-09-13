"""
El Watania (tunisiatv.tn) scraper.

The site is fully server-rendered, which is why plain requests +
BeautifulSoup works at all here (unlike Mosaique's Next.js SPA).

IMPORTANT: the CSS selectors below are written from a *rendered
markdown snapshot* of the page (this project's research phase did not
have raw-HTML / devtools access). They target the stable, semantic
parts of the page (link hrefs matching /ar/article/..., <h3>/<h2>
headline text, dates in a recognizable Arabic month-name format) which
tend to survive redesigns better than exact class names, but you
SHOULD verify them against the live HTML (browser devtools ->
Elements) before relying on this in production, and adjust the
`ARTICLE_LINK_PATTERN` / body extraction if the markup differs.
"""

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import WATANIA_BASE, WATANIA_CATEGORIES, WATANIA_LANGUAGE
from models import Article
from scrapers.base import BaseScraper

ARTICLE_LINK_PATTERN = re.compile(r"/ar/article/[a-f0-9]+/")

# Matches "13 سبتمبر 2026 07:51" style datetimes seen on the site.
ARABIC_MONTHS = {
    "جانفي": 1, "فيفري": 2, "مارس": 3, "أفريل": 4, "افريل": 4, "ماي": 5,
    "جوان": 6, "جويلية": 7, "أوت": 8, "اوت": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
DATE_PATTERN = re.compile(
    r"(\d{1,2})\s+(" + "|".join(ARABIC_MONTHS.keys()) + r")\s+(\d{4})\s+(\d{1,2}):(\d{2})"
)


def _parse_arabic_date(text: str) -> Optional[str]:
    m = DATE_PATTERN.search(text)
    if not m:
        return None
    day, month_name, year, hour, minute = m.groups()
    month = ARABIC_MONTHS[month_name]
    # Tunisia is UTC+1 (no DST); keep it simple and naive here, refine
    # later if exact UTC precision matters for your analytics.
    return f"{year}-{month:02d}-{int(day):02d}T{int(hour):02d}:{minute}:00+01:00"


class WataniaScraper(BaseScraper):
    source_name = "watania"
    request_timeout_seconds = 45
    max_attempts = 4

    def fetch(self, max_articles_per_category: int = 30) -> List[Article]:
        articles: List[Article] = []
        for category, listing_url in WATANIA_CATEGORIES.items():
            try:
                links = self._list_article_links(listing_url)
            except Exception as e:
                print(f"[watania] failed to list category '{category}': {e}")
                continue

            for url in links[:max_articles_per_category]:
                try:
                    article = self._fetch_article(url, category)
                    if article:
                        articles.append(article)
                except Exception as e:
                    print(f"[watania] failed to fetch article {url}: {e}")
        return articles

    def _list_article_links(self, listing_url: str) -> List[str]:
        resp = self.get(
            listing_url,
            timeout=self.request_timeout_seconds,
            max_attempts=self.max_attempts,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        hrefs = set()
        for a in soup.find_all("a", href=True):
            if ARTICLE_LINK_PATTERN.search(a["href"]):
                hrefs.add(urljoin(WATANIA_BASE, a["href"]))
        return list(hrefs)

    def _fetch_article(self, url: str, category: str) -> Optional[Article]:
        resp = self.get(
            url,
            timeout=self.request_timeout_seconds,
            max_attempts=self.max_attempts,
        )
        soup = BeautifulSoup(resp.text, "lxml")

        title = self._meta(soup, "og:title") or (soup.title.string if soup.title else "")
        summary = self._meta(soup, "og:description") or ""
        image_url = self._meta(soup, "og:image")

        # Heuristic body extraction: prefer an <article> tag if present,
        # else fall back to the largest cluster of <p> tags on the page.
        body = self._extract_body(soup)

        page_text = soup.get_text(" ")
        published_at = _parse_arabic_date(page_text)

        return Article(
            source=self.source_name,
            url=url,
            title=(title or "").strip(),
            body=body,
            summary=summary.strip(),
            category=category,
            published_at=published_at,
            language=WATANIA_LANGUAGE,
            image_url=image_url,
            method="html",
        )

    @staticmethod
    def _meta(soup: BeautifulSoup, prop: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find(
            "meta", attrs={"name": prop}
        )
        return tag["content"].strip() if tag and tag.has_attr("content") else None

    @staticmethod
    def _extract_body(soup: BeautifulSoup) -> str:
        article_tag = soup.find("article")
        container = article_tag if article_tag else soup

        paragraphs = [
            p.get_text(" ").strip()
            for p in container.find_all("p")
            if len(p.get_text(strip=True)) > 30  # skip nav/footer boilerplate
        ]
        return "\n".join(paragraphs).strip()
