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

CREATE TABLE IF NOT EXISTS article_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    region TEXT,                   -- e.g. "Sidi Bouzid" (governorate name, normalized)
    region_confidence REAL,
    region_method TEXT,            -- "gazetteer_title" | "gazetteer_body" | "none"
    region_matches TEXT,           -- JSON list of all raw matches found (for audit/debug)
    sentiment TEXT,                -- "positive" | "negative" | "neutral"
    sentiment_confidence REAL,
    urgency TEXT,                  -- "routine" | "moderate" | "urgent"
    urgency_score REAL,
    urgency_signals TEXT,          -- JSON list of matched keywords (for audit/debug)
    model_version TEXT NOT NULL,   -- lets you re-run analysis and compare versions
    analyzed_at TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
CREATE INDEX IF NOT EXISTS idx_insights_article_id ON article_insights(article_id);
CREATE INDEX IF NOT EXISTS idx_insights_region ON article_insights(region);
CREATE INDEX IF NOT EXISTS idx_insights_model_version ON article_insights(model_version);
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


def get_unanalyzed_articles(db_path: str, model_version: str, limit: int = 500) -> List[dict]:
    """
    Articles that don't yet have an insights row for this model_version.
    Passing a new model_version re-analyzes everything (useful when you
    improve the gazetteer/sentiment model and want a fresh pass without
    losing the old results, since old rows stay under the old version).
    """
    with get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT a.id, a.url, a.title, a.body, a.language, a.source, a.category
            FROM articles a
            LEFT JOIN article_insights i
                ON a.id = i.article_id AND i.model_version = ?
            WHERE i.id IS NULL
            LIMIT ?
            """,
            (model_version, limit),
        )
        return [dict(row) for row in cur.fetchall()]


def save_insight(db_path: str, insight: dict) -> None:
    """
    insight must contain: article_id, region, region_confidence,
    region_method, region_matches (list), sentiment, sentiment_confidence,
    urgency, urgency_score, urgency_signals (list), model_version.
    """
    import json as _json

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO article_insights
                (article_id, region, region_confidence, region_method, region_matches,
                 sentiment, sentiment_confidence, urgency, urgency_score, urgency_signals,
                 model_version, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight["article_id"],
                insight.get("region"),
                insight.get("region_confidence"),
                insight.get("region_method"),
                _json.dumps(insight.get("region_matches", []), ensure_ascii=False),
                insight.get("sentiment"),
                insight.get("sentiment_confidence"),
                insight.get("urgency"),
                insight.get("urgency_score"),
                _json.dumps(insight.get("urgency_signals", []), ensure_ascii=False),
                insight["model_version"],
                insight["analyzed_at"],
            ),
        )


def get_insight_stats(db_path: str, model_version: str) -> List[tuple]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT region, sentiment, urgency, COUNT(*)
            FROM article_insights
            WHERE model_version = ?
            GROUP BY region, sentiment, urgency
            ORDER BY COUNT(*) DESC
            """,
            (model_version,),
        )
        return cur.fetchall()
