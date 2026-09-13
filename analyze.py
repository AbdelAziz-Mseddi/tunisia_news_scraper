"""
Analysis orchestrator.

Pulls articles that don't yet have insights for the current
MODEL_VERSION, runs region detection + sentiment + urgency on each,
and saves results into `article_insights`.

Usage:
    uv run tunisia-analyze             # analyze everything new
    uv run tunisia-analyze --limit 100 # cap batch size
    uv run tunisia-analyze --no-sentiment   # skip sentiment (e.g. if you
                                        # haven't installed transformers/torch yet,
                                        # or just want fast region+urgency first)
    uv run tunisia-analyze --stats     # print insight stats and exit
"""

import argparse
from datetime import datetime, timezone

from config import DB_PATH
from storage import init_db, get_unanalyzed_articles, save_insight, get_insight_stats
from analysis.region_detector import detect_region
from analysis.urgency_detector import detect_urgency

# Bump this whenever you meaningfully change the gazetteer, sentiment
# model, or urgency keyword lists -- it lets you re-run analysis on
# everything without losing/overwriting the previous run's results,
# so you can compare before/after.
MODEL_VERSION = "v2_strict_local_body_context"


def analyze_batch(limit: int = 500, use_sentiment: bool = True) -> int:
    init_db(DB_PATH)
    articles = get_unanalyzed_articles(DB_PATH, MODEL_VERSION, limit=limit)
    print(f"Found {len(articles)} articles to analyze.")

    sentiment_fn = None
    if use_sentiment:
        try:
            from analysis.sentiment_analyzer import analyze_sentiment
            sentiment_fn = analyze_sentiment
        except ImportError as e:
            print(f"[analyze] sentiment analysis unavailable, skipping: {e}")

    analyzed_count = 0
    for art in articles:
        title = art["title"] or ""
        body = art["body"] or ""

        region_result = detect_region(
            title,
            body,
            source=art.get("source"),
            category=art.get("category"),
            url=art.get("url"),
        )
        urgency_result = detect_urgency(title, body)

        sentiment = None
        sentiment_confidence = None
        if sentiment_fn:
            # Sentiment on title + first part of body: keeps it fast
            # and avoids the model's token limit on long articles.
            text_for_sentiment = (title + ". " + body[:300]).strip()
            sres = sentiment_fn(text_for_sentiment)
            sentiment = sres.sentiment
            sentiment_confidence = sres.confidence

        save_insight(DB_PATH, {
            "article_id": art["id"],
            "region": region_result.region,
            "region_confidence": region_result.confidence,
            "region_method": region_result.method,
            "region_matches": region_result.matches,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
            "urgency": urgency_result.urgency,
            "urgency_score": urgency_result.score,
            "urgency_signals": urgency_result.signals,
            "model_version": MODEL_VERSION,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })
        analyzed_count += 1

    return analyzed_count


def print_stats():
    print(f"\n--- Insight stats for model_version='{MODEL_VERSION}' ---")
    print(f"{'region':15} {'sentiment':10} {'urgency':10} count")
    for region, sentiment, urgency, count in get_insight_stats(DB_PATH, MODEL_VERSION):
        print(f"{(region or '-'):15} {(sentiment or '-'):10} {(urgency or '-'):10} {count}")


def main():
    parser = argparse.ArgumentParser(description="Analyze scraped articles: region, sentiment, urgency")
    parser.add_argument("--limit", type=int, default=500, help="Max articles to analyze this run")
    parser.add_argument("--no-sentiment", action="store_true", help="Skip sentiment analysis")
    parser.add_argument("--stats", action="store_true", help="Print insight stats and exit")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    n = analyze_batch(limit=args.limit, use_sentiment=not args.no_sentiment)
    print(f"\nAnalyzed {n} articles (model_version={MODEL_VERSION}).")
    print_stats()


if __name__ == "__main__":
    main()
