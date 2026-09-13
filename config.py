"""
Central configuration for all sources.

Add new outlets here rather than hardcoding URLs inside scraper classes,
so the project stays easy to extend (each new site is usually just a
new dict entry + picking the right scraper class in main.py).
"""

USER_AGENT = (
    "TunisiaRegionalNewsBot/0.1 (+contact: youremail@example.com; "
    "research project on regional news coverage in Tunisia)"
)

REQUEST_TIMEOUT = 15          # seconds
REQUEST_DELAY_SECONDS = 2.0   # politeness delay between requests to the same domain

# --- Nessma TV -------------------------------------------------------
# Fully server-rendered + real RSS feeds per category. Easiest source.
NESSMA_RSS_FEEDS = {
    "national": "https://www.nessma.tv/fr/rss/news/7",
    "economie": "https://www.nessma.tv/fr/rss/news/1",
    "regions": "https://www.nessma.tv/fr/rss/news/3",
    "sport": "https://www.nessma.tv/fr/rss/news/4",
    "culture": "https://www.nessma.tv/fr/rss/news/5",
    "international": "https://www.nessma.tv/fr/rss/news/8",
    "hightech": "https://www.nessma.tv/fr/rss/news/15",
    "sante": "https://www.nessma.tv/fr/rss/news/49",
    "environnement": "https://www.nessma.tv/fr/rss/news/67",
}
NESSMA_LANGUAGE = "fr"

# --- Mosaique FM -------------------------------------------------------
# Next.js SPA: article body is client-rendered, but <meta og:title>,
# <meta og:description> and og:image are present in the raw HTML for
# every article, so a plain request gets title + short summary for free.
# Category listing pages are ALSO client-rendered, so we cannot discover
# new article URLs with plain requests; this scraper needs either:
#   (a) a Playwright-rendered listing page (see playwright_scraper.py), or
#   (b) a manually/otherwise supplied list of article URLs (e.g. from
#       their sitemap.xml, which you should check for directly once you
#       have real network access -- it was not reachable from this
#       research session's tooling).
MOSAIQUE_BASE = "https://www.mosaiquefm.net"
MOSAIQUE_REGIONAL_LISTING = f"{MOSAIQUE_BASE}/fr/actualite-regional-tunisie"
MOSAIQUE_LANGUAGE = "fr"  # site also has an Arabic version at /ar/...

# --- El Watania (Tunisian public TV, tunisiatv.tn) --------------------
# Fully server-rendered Arabic HTML. Category IDs found on the homepage:
WATANIA_BASE = "https://www.tunisiatv.tn"
WATANIA_CATEGORIES = {
    "national": "https://www.tunisiatv.tn/ar/articles/1/694b905b041dd11d25acc3a0/وطنية",
    "regional": "https://www.tunisiatv.tn/ar/articles/1/6948feb033a1f451fbc614ea/جهويّة",
    "international": "https://www.tunisiatv.tn/ar/articles/1/694b9138041dd11d25acc455/عالمية",
    "politique": "https://www.tunisiatv.tn/ar/articles/1/694b9152041dd11d25acc484/سياسة",
    "economie": "https://www.tunisiatv.tn/ar/articles/1/694b9173041dd11d25acc49a/اقتصاد",
}
WATANIA_LANGUAGE = "ar"

# --- El Hiwar Ettounsi -------------------------------------------------
# robots.txt disallows automated access as of this writing. Respect it:
# do not scrape their website directly. If you need their coverage,
# either request permission/API access from the outlet, or limit
# yourself to whatever they publish openly via RSS (none found) or
# their public social media API (subject to that platform's own ToS).
ELHIWAR_BASE = "https://www.elhiwarettounsi.com"
ELHIWAR_SCRAPING_ALLOWED = False

# --- Storage -----------------------------------------------------------
DB_PATH = "tunisia_news.db"
