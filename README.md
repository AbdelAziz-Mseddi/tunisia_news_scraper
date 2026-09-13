# Tunisia Regional News Scraper

Scrapes Tunisian news outlets into a common `Article` schema stored in
SQLite, as the first stage of a pipeline that will later detect which
region/governorate each article is about (from title primarily, body
secondarily) and produce analytics.

## Status per outlet (from live feasibility testing)

| Source | Method | Confidence | Notes |
|---|---|---|---|
| **Nessma TV** | RSS (`scrapers/rss_scraper.py`) | ✅ Tested against real feed data | Full article body is in the RSS `<description>`. Cheapest, most reliable source. Has a dedicated "Régions" feed. |
| **El Watania** (tunisiatv.tn) | HTML (`scrapers/watania_scraper.py`) | ⚠️ Logic tested (date parsing, extraction helpers), but CSS selectors were written from a rendered snapshot, not raw devtools HTML — **verify selectors against the live page before relying on it** | Server-rendered Arabic HTML, has a dedicated "جهوية" (Regional) category. |
| **Mosaique FM** | Meta-tags (cheap) or Playwright (full) — `scrapers/mosaique_scraper.py` | ⚠️ Meta-tag logic is simple/standard but untested against a live fetch in this environment | Next.js SPA. Article `<head>` has `og:title`/`og:description` server-rendered; full body needs a headless browser. `MosaiqueMetaScraper` needs a list of article URLs as input — see "Discovering Mosaique article URLs" below. |
| **El Hiwar Ettounsi** | — | ❌ Not implemented | robots.txt disallows automated access. Respect it: either get permission from the outlet or skip this source. |

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Only needed if you'll use MosaiquePlaywrightScraper:
playwright install chromium
```

## Usage

```bash
# Scrape Nessma (RSS) + El Watania (HTML)
python main.py

# Also crawl Mosaique via headless browser (slower)
python main.py --with-mosaique-playwright

# Just check what's in the DB so far
python main.py --stats
```

Re-running `main.py` is safe — articles are deduplicated by URL, so a
cron job that runs this hourly will only insert genuinely new items.

## Discovering Mosaique article URLs

`MosaiqueMetaScraper` takes a list of URLs rather than crawling on its
own, because listing pages need JS to render. Three ways to get URLs:

1. **`MosaiquePlaywrightScraper.discover_article_urls()`** — renders
   the listing page with a headless browser and scrolls to load more.
   Slowest but most self-contained; see `main.py --with-mosaique-playwright`.
2. **Check for a sitemap.xml** once you have real network access —
   most Next.js news sites publish one at `/sitemap.xml` even when the
   HTML pages are client-rendered. This research session's tooling
   could not fetch arbitrary unlisted URLs to confirm one exists for
   Mosaique — check this first, it may make Playwright unnecessary.
2b. Sitemaps are also usually linked from `robots.txt` — worth checking there too.
3. **Google/Bing site-search** (`site:mosaiquefm.net/fr/actualite-regional-tunisie`)
   as a manual/occasional backfill method.

## Design notes

- **`models.Article`** is the single shared schema every scraper
  outputs, regardless of method (RSS/HTML/Playwright). Downstream
  region-detection code should only ever depend on this shape.
- **`scrapers/base.py`** centralizes robots.txt checking (fail-closed:
  if robots.txt can't be read, the request is blocked, not allowed by
  default), a per-domain politeness delay, and retry-with-backoff — so
  every scraper inherits good citizenship automatically.
- **`storage.py`** is deliberately just SQLite + stdlib. Swap it for
  Postgres later without touching scraper code — only `save_articles`
  / `get_stats` need reimplementing.
- Add a new outlet by: (1) adding its config to `config.py`, (2) either
  reusing `RSSScraper` if it has a feed, or writing a small new
  `BaseScraper` subclass, (3) wiring it into `main.py`.

## What's NOT done yet (by design — scraping first)

- Region/governorate detection (gazetteer + NER) — next phase.
- Analytics/dashboard layer.
- Scheduling (cron/Airflow) — `main.py` is written to be cron-friendly
  but nothing schedules it yet.
