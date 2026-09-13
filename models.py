"""
Shared data model for every scraper.

Every scraper in this project (regardless of how it gets its data -
RSS, plain HTML, or a headless browser) must ultimately produce a list
of Article objects. This keeps storage, deduplication, and downstream
NLP region-detection completely decoupled from *how* each site was
scraped.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import hashlib


@dataclass
class Article:
    source: str                 # e.g. "nessma", "mosaique", "watania"
    url: str                    # canonical article URL (also used as external id)
    title: str
    body: str = ""              # full text if available, else the RSS/meta summary
    summary: str = ""           # short description / dek, if separate from body
    category: Optional[str] = None   # editorial category as given by the source
    published_at: Optional[str] = None  # ISO 8601 string, UTC, if known
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    language: Optional[str] = None   # "ar" or "fr" (best guess, refined later by NLP)
    image_url: Optional[str] = None
    method: Optional[str] = None     # "rss" | "html" | "meta_only" | "playwright"

    def content_hash(self) -> str:
        """Stable hash used for dedup / change-detection independent of URL."""
        payload = (self.title.strip() + "||" + (self.body or self.summary).strip())
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)
