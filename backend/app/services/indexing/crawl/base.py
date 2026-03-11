"""
Abstract base class for crawl providers.
Every provider must implement crawl_page(); crawl_site() is optional.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class CrawledPage:
    """Result of crawling a single page."""
    url: str
    final_url: str
    status_code: int
    html: str = ""
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    content_type: str = ""
    language: str = ""
    links: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and len(self.html) > 0 and self.error is None


class CrawlProvider(ABC):
    """Interface for pluggable crawl backends."""

    name: str = "base"

    @abstractmethod
    async def crawl_page(self, url: str, **kwargs) -> CrawledPage:
        """Fetch a single page and return structured result."""
        ...

    async def close(self):
        """Release any resources held by the provider."""
        pass
