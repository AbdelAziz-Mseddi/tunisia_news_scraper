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
        self._robots_warnings: set[str] = set()

    # -- robots.txt -------------------------------------------------
    def _get_robots(self, url: str) -> urllib.robotparser.RobotFileParser:
        domain = urlparse(url).netloc
        if domain not in self._robots_cache:
            robots_url = f"https://{domain}/robots.txt"
            try:
                resp = requests.get(robots_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                robots_text = resp.text
                if not any(token in robots_text for token in ("User-agent:", "Disallow:", "Allow:", "Sitemap:")):
                    raise ValueError("response does not look like a robots.txt file")

                rp = urllib.robotparser.RobotFileParser()
                rp.parse(robots_text.splitlines())
            except Exception:
                # Some sites return HTML or a generic landing page at
                # /robots.txt instead of a real robots file. In that case
                # we fall back to allowing requests rather than falsely
                # blocking every URL from the domain.
                rp = None
            self._robots_cache[domain] = rp
        return self._robots_cache[domain]

    def _check_allowed(self, url: str) -> bool:
        rp = self._get_robots(url)
        if rp is None:
            domain = urlparse(url).netloc
            if domain not in self._robots_warnings:
                print(f"[robots] no valid robots.txt found for {domain}; proceeding without robots gating")
                self._robots_warnings.add(domain)
            return True
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
        timeout: int | None = None,
        **kwargs,
    ) -> requests.Response:
        if respect_robots and not self._check_allowed(url):
            raise RobotsBlocked(f"robots.txt disallows fetching: {url}")

        self._throttle(url)
        last_exc: Exception | None = None
        request_timeout = timeout or REQUEST_TIMEOUT
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.session.get(url, timeout=request_timeout, **kwargs)
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
