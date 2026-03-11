"""
Crawler service – orchestrates crawling a full site using a CrawlProvider.

Handles BFS traversal, sitemap discovery, depth/page limits, dedup,
retry on failure, and structured logging of skipped URLs.
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from .base import CrawlProvider, CrawledPage
from .http_provider import HttpCrawlProvider
from .cloudflare_provider import CloudflareCrawlProvider
from .url_utils import normalize_url, is_same_domain, should_skip_url

logger = logging.getLogger(__name__)


class CrawlerService:
    """Crawl an entire site via BFS + sitemap, returning structured pages."""

    def __init__(
        self,
        provider: str = "http",
        max_pages: int = 100,
        max_depth: int = 3,
        blocked_paths: Optional[List[str]] = None,
        concurrency: int = 5,
        retry_count: int = 1,
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.blocked_paths = blocked_paths or ["/admin", "/login", "/wp-admin"]
        self.concurrency = concurrency
        self.retry_count = retry_count

        self._provider = self._make_provider(provider)
        self._visited: Set[str] = set()
        self._pages: List[CrawledPage] = []
        self._skip_log: List[Dict] = []

    @staticmethod
    def _make_provider(name: str) -> CrawlProvider:
        if name == "cloudflare":
            cf = CloudflareCrawlProvider()
            if cf.available:
                logger.info("Using Cloudflare Browser Rendering provider")
                return cf
            logger.warning("Cloudflare credentials not set, falling back to HTTP provider")
        return HttpCrawlProvider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def crawl_site(self, base_url: str) -> List[CrawledPage]:
        """Crawl from base_url. Returns list of successfully crawled pages."""
        base_url = base_url.rstrip("/")
        domain = urlparse(base_url).netloc

        queue: List[tuple[str, int, Optional[str]]] = [(base_url, 0, None)]

        sitemap_urls = await self._discover_sitemap(base_url)
        for surl in sitemap_urls:
            norm = normalize_url(surl)
            if norm != normalize_url(base_url):
                queue.append((surl, 1, "sitemap"))

        sem = asyncio.Semaphore(self.concurrency)

        while queue and len(self._pages) < self.max_pages:
            batch = []
            while queue and len(batch) < self.concurrency:
                url, depth, discovered_from = queue.pop(0)
                norm = normalize_url(url)
                if norm in self._visited:
                    continue
                if should_skip_url(url, self.blocked_paths):
                    self._skip_log.append({"url": url, "reason": "blocked_or_skip_ext"})
                    continue
                self._visited.add(norm)
                batch.append((url, depth, discovered_from))

            if not batch:
                break

            tasks = [
                self._fetch_with_retry(url, domain, sem)
                for url, _, _ in batch
            ]
            results = await asyncio.gather(*tasks)

            for (url, depth, discovered_from), page in zip(batch, results):
                if page is None or not page.ok:
                    reason = page.error if page else "empty result"
                    self._skip_log.append({"url": url, "reason": reason})
                    continue

                self._pages.append(page)
                logger.info(
                    "Crawled [%d/%d] %s (%d bytes)",
                    len(self._pages), self.max_pages, url, len(page.html),
                )

                if depth < self.max_depth:
                    for link in page.links:
                        if normalize_url(link) not in self._visited:
                            queue.append((link, depth + 1, url))

            await asyncio.sleep(0.3)

        await self._provider.close()
        logger.info("Crawl finished: %d pages fetched, %d skipped", len(self._pages), len(self._skip_log))
        return self._pages

    async def _fetch_with_retry(
        self, url: str, base_domain: str, sem: asyncio.Semaphore,
    ) -> Optional[CrawledPage]:
        async with sem:
            for attempt in range(1 + self.retry_count):
                page = await self._provider.crawl_page(url, base_domain=base_domain)
                if page.ok:
                    return page
                if attempt < self.retry_count:
                    await asyncio.sleep(1.0 * (attempt + 1))
            return page

    async def _discover_sitemap(self, base_url: str) -> List[str]:
        urls: List[str] = []
        domain = urlparse(base_url).netloc
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{base_url}/sitemap.xml")
                if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                    for match in re.finditer(r"<loc>(.*?)</loc>", resp.text):
                        u = match.group(1).strip()
                        if is_same_domain(u, domain) and not should_skip_url(u):
                            urls.append(normalize_url(u))
                    logger.info("Sitemap: found %d URLs for %s", len(urls), domain)
        except Exception:
            pass
        return urls

    def get_skip_log(self) -> List[Dict]:
        return list(self._skip_log)

    def get_stats(self) -> Dict:
        return {
            "urls_discovered": len(self._visited),
            "pages_fetched": len(self._pages),
            "pages_skipped": len(self._skip_log),
        }
