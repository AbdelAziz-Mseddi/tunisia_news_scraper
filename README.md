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
uv venv
source .venv/bin/activate
uv sync

# Only needed if you'll use MosaiquePlaywrightScraper:
uv run playwright install chromium

# Optional: install the analysis extras if you want sentiment scoring
# (this includes the tokenizer deps needed by the Hugging Face model)
uv sync --extra analysis
```

The SQLite database file is created automatically the first time you run
`uv run tunisia-scrape` or `uv run tunisia-analyze`. No manual database
setup is needed.

## Usage

```bash
# Scrape Nessma (RSS) + El Watania (HTML)
uv run tunisia-scrape

# Also crawl Mosaique via headless browser (slower)
uv run tunisia-scrape --with-mosaique-playwright

# Just check what's in the DB so far
uv run tunisia-scrape --stats

# Analyze saved articles
uv run tunisia-analyze
uv run tunisia-analyze --no-sentiment
uv run tunisia-analyze --stats
```

Re-running the scraper is safe — articles are deduplicated by URL, so
a cron job that runs this hourly will only insert genuinely new items.

## Database Queries

The SQLite database lives at `tunisia_news.db` in the project root and
is created automatically the first time you run the scraper or the
analyzer. To inspect it interactively, use the SQLite shell:

```bash
sqlite3 tunisia_news.db
```

Inside the shell, useful commands are:

```sql
.tables
.schema articles
.schema article_insights
.headers on
.mode column
```

Ready-to-run queries:

```sql
-- Count articles by source and category
SELECT source, category, COUNT(*) AS count
FROM articles
GROUP BY source, category
ORDER BY source, category;

-- Show the 20 most recent articles
SELECT source, category, title, published_at, scraped_at, url
FROM articles
ORDER BY scraped_at DESC
LIMIT 20;

-- Find articles that still have no analysis row for the current model
SELECT a.id, a.source, a.category, a.title, a.published_at
FROM articles a
LEFT JOIN article_insights i
  ON a.id = i.article_id AND i.model_version = 'v1_gazetteer_xlmr_keywords'
WHERE i.id IS NULL
ORDER BY a.scraped_at DESC
LIMIT 50;

-- Breakdown of analysis results for the current model
SELECT region, sentiment, urgency, COUNT(*) AS count
FROM article_insights
WHERE model_version = 'v1_gazetteer_xlmr_keywords'
GROUP BY region, sentiment, urgency
ORDER BY count DESC;

-- Mosaique regional articles only
SELECT title, published_at, url
FROM articles
WHERE source = 'mosaique' AND category = 'regional'
ORDER BY published_at DESC;
```

## Discovering Mosaique article URLs

`MosaiqueMetaScraper` takes a list of URLs rather than crawling on its
own, because listing pages need JS to render. Three ways to get URLs:

1. **`MosaiquePlaywrightScraper.discover_article_urls()`** — renders
   the listing page with a headless browser and scrolls to load more.
  Slowest but most self-contained; see `uv run tunisia-scrape --with-mosaique-playwright`.
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

## What's NOT done yet (by design)

- Analytics/dashboard layer (final step, comes last per project plan).
- Scheduling (cron/Airflow) — `uv run tunisia-scrape` and `uv run
  tunisia-analyze` are cron-friendly, but nothing schedules them yet.

## Analysis module (region + sentiment + urgency)

Second stage of the pipeline: `uv run tunisia-analyze` pulls every
scraped article that doesn't yet have insights, runs three independent
detectors, and stores results in a separate `article_insights` table
(one-to-many with `articles`, joined on `article_id`).

**Why a separate table instead of adding columns to `articles`:**
- You can re-run analysis (better gazetteer, new model) without
  touching raw scraped data — old and new results can coexist,
  distinguished by `model_version`, so you can compare before/after.
- Keeps the scraping module and the analysis module fully decoupled —
  either can be rebuilt independently.

### Region detection (`analysis/region_detector.py` + `analysis/gazetteer.py`)

Gazetteer-based, no ML: matches the title first (falls back to body at
lower confidence) against a bilingual (FR/AR) dictionary of Tunisia's
24 governorates plus ~90 delegations/cities mapped to their parent
governorate. Delegation matches ("Ain Draham" → Jendouba) are checked
before bare governorate names, since Tunisian news headlines almost
always name the specific town, not the governorate.

**Tested against real scraped titles** (see `README` git history /
conversation for the test transcript) — 100% correct on a 12-title
sample after fixing an Arabic-specific bug (see below), including
correctly returning no region for non-regional news.

**Known limitation handled:** Arabic attaches prepositions/conjunctions
(ب, ل, ك, ف, و) directly to the next word with no space — e.g.
"بالقيروان" ("in Kairouan") — which breaks naive word-boundary regex
matching. Fixed by registering prefixed variants of every Arabic
gazetteer term. If you see a missed region during real use, check
whether it's this same class of issue on an uncommon prefix combo.

**Extending the gazetteer:** `analysis/gazetteer.py` is a plain Python
dict — add new delegations as you encounter them in real scraped
data. The official INS (Institut National de la Statistique) list of
all ~350 Tunisian delegations would let you make this exhaustive.

### Sentiment (`analysis/sentiment_analyzer.py`)

Uses `cardiffnlp/twitter-xlm-roberta-base-sentiment`, an open-weights
HuggingFace model covering French AND Arabic in one model. Per your
requirement (local, free, runs on your own machine):
- First run downloads ~1GB of weights (needs internet once).
- Every run after that is fully offline and free — no API calls, no
  per-request cost.
- Runs fine on CPU; a GPU only helps if you're processing huge volumes
  and want it faster.

Not runnable/tested in the sandbox this project was built in (no
network access to download model weights) — install the analysis extra
from `pyproject.toml` and test it yourself with:
```bash
python -c "from analysis.sentiment_analyzer import analyze_sentiment; print(analyze_sentiment('Une belle réussite pour la Tunisie'))"
```

If you don't want to install transformers/torch yet, `uv run
tunisia-analyze --no-sentiment` runs region + urgency only (both
dependency-free) so you're not blocked.

### Urgency/severity (`analysis/urgency_detector.py`)

Keyword-based (FR + AR), no ML: three tiers (urgent/moderate/routine)
based on curated word lists (deaths, explosions, disasters → urgent;
strikes, protests, accidents → moderate; everything else → routine).
**Tested against real headlines** — correctly flagged a terrorist
attack and a fatal shipwreck as urgent, a strike as moderate, and
tourism/economic stats as routine. This lexicon is deliberately a
starting point — extend `URGENT_KEYWORDS_*` / `MODERATE_KEYWORDS_*` as
you see real missed cases (e.g. drug-bust stories currently fall
through to "routine" since no matching keyword exists yet).

### Running it

```bash
uv run tunisia-analyze                  # full run: region + sentiment + urgency
uv run tunisia-analyze --no-sentiment   # region + urgency only, no transformers/torch needed
uv run tunisia-analyze --limit 100      # cap batch size
uv run tunisia-analyze --stats          # print counts by region/sentiment/urgency
```

