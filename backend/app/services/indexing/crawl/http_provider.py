"""
HTTP crawl provider – lightweight, works for static & SSR sites.
Falls back gracefully; no external render service required.
"""
import logging
import re
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import CrawlProvider, CrawledPage
from .url_utils import is_same_domain, should_skip_url, normalize_url

logger = logging.getLogger(__name__)

_USER_AGENT = "klantenservice-ai-bot/2.0 (+https://klantenservice.ai)"


class HttpCrawlProvider(CrawlProvider):
    name = "http"

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
                timeout=self._timeout,
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def crawl_page(self, url: str, **kwargs) -> CrawledPage:
        await self._ensure_client()
        base_domain = kwargs.get("base_domain", "")

        try:
            resp = await self._client.get(url)
        except httpx.TimeoutException:
            return CrawledPage(url=url, final_url=url, status_code=0, error="timeout")
        except httpx.HTTPError as exc:
            return CrawledPage(url=url, final_url=url, status_code=0, error=str(exc))

        final_url = str(resp.url)
        ct = resp.headers.get("content-type", "")

        if resp.status_code != 200 or "text/html" not in ct:
            return CrawledPage(
                url=url, final_url=final_url,
                status_code=resp.status_code,
                content_type=ct,
                error=f"non-html or bad status ({resp.status_code})",
            )

        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        title = (soup.title.get_text(strip=True) if soup.title else "")
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].strip()

        h1 = ""
        h1_tag = soup.find("h1")
        if h1_tag:
            h1 = h1_tag.get_text(strip=True)

        lang = ""
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang = html_tag["lang"]

        links = self._extract_links(soup, url, base_domain)

        return CrawledPage(
            url=url,
            final_url=final_url,
            status_code=resp.status_code,
            html=html,
            title=title,
            meta_description=meta_desc,
            h1=h1,
            content_type=ct,
            language=lang,
            links=links,
        )

    @staticmethod
    def _extract_links(soup: BeautifulSoup, page_url: str, base_domain: str) -> List[str]:
        seen = set()
        result = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            full = urljoin(page_url, href)
            norm = normalize_url(full)
            if norm in seen:
                continue
            seen.add(norm)
            if not is_same_domain(full, base_domain):
                continue
            if should_skip_url(full):
                continue
            result.append(norm)
        return result
