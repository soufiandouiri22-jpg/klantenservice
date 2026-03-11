"""
Cloudflare Browser Rendering provider.

Uses the /content endpoint to get fully-rendered HTML (JS executed).
Activate by setting CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID env vars.
"""
import json
import logging
import os
from typing import List
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import CrawlProvider, CrawledPage
from .url_utils import is_same_domain, should_skip_url, normalize_url

logger = logging.getLogger(__name__)


class CloudflareCrawlProvider(CrawlProvider):
    name = "cloudflare"

    def __init__(self):
        self._token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        self._account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def available(self) -> bool:
        return bool(self._token and self._account_id)

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def crawl_page(self, url: str, **kwargs) -> CrawledPage:
        if not self.available:
            return CrawledPage(
                url=url, final_url=url, status_code=0,
                error="Cloudflare credentials not configured",
            )

        await self._ensure_client()
        base_domain = kwargs.get("base_domain", "")

        api_url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self._account_id}/browser-rendering/content"
        )

        try:
            resp = await self._client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "gotoOptions": {"waitUntil": "networkidle0"},
                    "rejectResourceTypes": ["image", "font", "media"],
                },
            )

            if resp.status_code != 200:
                return CrawledPage(
                    url=url, final_url=url,
                    status_code=resp.status_code,
                    error=f"Cloudflare API error: {resp.status_code} {resp.text[:200]}",
                )

            # /content returns JSON: {"success": true, "result": "<html>..."}
            try:
                data = resp.json()
                html = data.get("result", "") if data.get("success") else ""
            except (json.JSONDecodeError, ValueError):
                html = resp.text

            if not html:
                return CrawledPage(
                    url=url, final_url=url, status_code=200,
                    error="Cloudflare returned empty HTML",
                )

            logger.info("Cloudflare rendered %s: %d bytes", url, len(html))
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
                final_url=url,
                status_code=200,
                html=html,
                title=title,
                meta_description=meta_desc,
                h1=h1,
                content_type="text/html",
                language=lang,
                links=links,
            )

        except httpx.TimeoutException:
            return CrawledPage(url=url, final_url=url, status_code=0, error="cloudflare timeout")
        except Exception as exc:
            logger.error("Cloudflare crawl error for %s: %s", url, exc)
            return CrawledPage(url=url, final_url=url, status_code=0, error=str(exc))

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
