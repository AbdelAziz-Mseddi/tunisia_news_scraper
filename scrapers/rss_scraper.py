"""
Generic RSS scraper.

Nessma TV's feeds already contain the FULL article body inside
<description> (as CDATA-wrapped HTML with an inline image), so for this
source RSS alone is enough -- no need to visit each article page.

This class is written to be reusable for any other outlet you find
that also publishes RSS (check every new source for a feed before
reaching for HTML scraping or Playwright).
"""

import re
from datetime import datetime, timezone
from typing import Dict, List

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from models import Article
from scrapers.base import BaseScraper


def _strip_html(html_fragment: str) -> str:
    """Turn an RSS <description> CDATA HTML blob into plain text."""
    soup = BeautifulSoup(html_fragment, "lxml")
    # Drop the inline <img> tag; we keep its src separately if needed.
    for img in soup.find_all("img"):
        img.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _extract_first_image(html_fragment: str) -> str | None:
    soup = BeautifulSoup(html_fragment, "lxml")
    img = soup.find("img")
    return img["src"] if img and img.has_attr("src") else None


def _to_iso(pub_date_str: str) -> str | None:
    try:
        dt = dateutil_parser.parse(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


class RSSScraper(BaseScraper):
    """
    Parameterized over a dict of {category_name: feed_url}.
    Set respect_robots=False only if you've separately confirmed the
    feed URLs themselves are allowed (RSS feeds are usually intended
    for automated consumption, but we still check by default).
    """

    def __init__(self, source_name: str, feeds: Dict[str, str], language: str):
        super().__init__()
        self.source_name = source_name
        self.feeds = feeds
        self.language = language

    def fetch(self) -> List[Article]:
        import feedparser  # lazy import: only needed here, keeps helper
                            # functions above testable without the dependency

        articles: List[Article] = []
        for category, feed_url in self.feeds.items():
            try:
                resp = self.get(feed_url)
            except Exception as e:
                print(f"[{self.source_name}] failed to fetch feed '{category}': {e}")
                continue

            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries:
                raw_description = getattr(entry, "description", "") or ""
                body_text = _strip_html(raw_description)
                image_url = _extract_first_image(raw_description)

                articles.append(
                    Article(
                        source=self.source_name,
                        url=entry.link,
                        title=entry.title.strip(),
                        body=body_text,
                        summary=body_text[:280],
                        category=category,
                        published_at=_to_iso(getattr(entry, "published", "")),
                        language=self.language,
                        image_url=image_url,
                        method="rss",
                    )
                )
        return articles
