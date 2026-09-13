"""
Minimal SQLite storage layer.

Deliberately simple (single file, stdlib sqlite3) so the scraping
project has zero external DB dependency to get started. Swapping this
for Postgres later is just a matter of replacing this module -- the
rest of the code only calls save_articles() / get_stats().
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterable, List

from models import Article

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT,
    summary TEXT,
    category TEXT,
    published_at TEXT,
    scraped_at TEXT NOT NULL,
    language TEXT,
    image_url TEXT,
    method TEXT,
    content_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
"""


@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def save_articles(db_path: str, articles: Iterable[Article]) -> int:
    """
    Insert articles, skipping ones whose URL already exists.
    Returns the number of NEW rows inserted.
    """
    inserted = 0
    with get_conn(db_path) as conn:
        cur = conn.cursor()
        for art in articles:
            try:
                cur.execute(
                    """
                    INSERT INTO articles
                        (source, url, title, body, summary, category,
                         published_at, scraped_at, language, image_url,
                         method, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        art.source, art.url, art.title, art.body, art.summary,
                        art.category, art.published_at, art.scraped_at,
                        art.language, art.image_url, art.method,
                        art.content_hash(),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # URL already present -> skip silently (this is expected
                # on every re-run once you're polling the same feeds).
                continue
    return inserted


def get_stats(db_path: str) -> List[tuple]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT source, category, COUNT(*) FROM articles "
            "GROUP BY source, category ORDER BY source, category"
        )
        return cur.fetchall()
