"""
Content cleaning pipeline – HTML -> clean markdown/plain text.

Pipeline: raw HTML -> boilerplate removal -> main content extraction
          -> heading-aware markdown conversion -> whitespace normalisation.
"""
import hashlib
import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from .boilerplate import BoilerplateRemover
from .extractors import MainContentExtractor


class ContentCleaner:
    """Convert raw HTML into clean, heading-structured text."""

    def __init__(self):
        self._boilerplate = BoilerplateRemover()
        self._extractor = MainContentExtractor()

    def clean(self, html: str) -> Optional[str]:
        """Return cleaned text or None if nothing useful remains."""
        if not html or len(html) < 100:
            return None

        soup = BeautifulSoup(html, "lxml")
        self._boilerplate.clean(soup)
        main = self._extractor.extract(soup)

        if main is None:
            return None

        text = self._to_structured_text(main)
        text = self._normalize_whitespace(text)

        if len(text.strip()) < 50:
            return None

        return text.strip()

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # HTML -> structured text with heading markers
    # ------------------------------------------------------------------

    def _to_structured_text(self, root: Tag) -> str:
        """Walk the DOM and produce text that preserves heading hierarchy, lists, tables."""
        parts: list[str] = []
        self._walk(root, parts)
        return "\n".join(parts)

    def _walk(self, node, parts: list[str]):
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parts.append(text)
            return

        if not isinstance(node, Tag):
            return

        tag = node.name

        # Headings -> markdown-style
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text = node.get_text(strip=True)
            if text:
                parts.append("")
                parts.append(f"{'#' * level} {text}")
                parts.append("")
            return

        # Paragraphs
        if tag == "p":
            text = node.get_text(strip=True)
            if text:
                parts.append(text)
                parts.append("")
            return

        # Lists
        if tag in ("ul", "ol"):
            for li in node.find_all("li", recursive=False):
                text = li.get_text(strip=True)
                if text:
                    parts.append(f"- {text}")
            parts.append("")
            return

        # Tables -> simple text rows
        if tag == "table":
            self._table_to_text(node, parts)
            return

        # Line breaks
        if tag == "br":
            parts.append("")
            return

        # Recurse into other elements
        for child in node.children:
            self._walk(child, parts)

    @staticmethod
    def _table_to_text(table: Tag, parts: list[str]):
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if any(cells):
                parts.append(" | ".join(cells))
        parts.append("")

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines)
