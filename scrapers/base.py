"""
Common scraper base class.

Every concrete scraper (RSS-based, HTML-based, Playwright-based) should
subclass BaseScraper and implement fetch(). This centralizes:
  - a shared requests.Session with a proper identifying User-Agent
  - robots.txt checking (fail closed: if we can't confirm we're
    allowed, we don't scrape)
  - a politeness delay between requests
  - retry logic on transient network errors
"""

import time
import urllib.robotparser
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from typing import List

import requests

from config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY_SECONDS
from models import Article


class RobotsBlocked(Exception):
    """Raised when robots.txt disallows fetching a given URL."""


class BaseScraper(ABC):
    source_name: str = "unknown"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request_time: dict[str, float] = {}

    # -- robots.txt -------------------------------------------------
    def _get_robots(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = urlparse(url).netloc
        if domain not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"https://{domain}/robots.txt")
            try:
                rp.read()
            except Exception:
                # If robots.txt is unreachable, be conservative and treat
                # everything as disallowed rather than assuming allowed.
                rp = None
            self._robots_cache[domain] = rp
        return self._robots_cache[domain]

    def _check_allowed(self, url: str) -> bool:
        rp = self._get_robots(url)
        if rp is None:
            return False
        return rp.can_fetch(USER_AGENT, url)

    # -- politeness ---------------------------------------------------
    def _throttle(self, url: str) -> None:
        domain = urlparse(url).netloc
        last = self._last_request_time.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time[domain] = time.time()

    # -- HTTP GET with manual exponential-backoff retry ------------------
    # (kept dependency-free/inline rather than pulling in `tenacity`)
    def get(
        self,
        url: str,
        respect_robots: bool = True,
        max_attempts: int = 3,
        **kwargs,
    ) -> requests.Response:
        if respect_robots and not self._check_allowed(url):
            raise RobotsBlocked(f"robots.txt disallows fetching: {url}")

        self._throttle(url)
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
                resp.raise_for_status()
                return resp
            except (requests.RequestException,) as e:
                last_exc = e
                if attempt < max_attempts:
                    time.sleep(2 ** attempt)  # 2s, 4s, 8s...
        raise last_exc  # type: ignore[misc]

    @abstractmethod
    def fetch(self) -> List[Article]:
        """Return a list of freshly scraped Article objects."""
        raise NotImplementedError
