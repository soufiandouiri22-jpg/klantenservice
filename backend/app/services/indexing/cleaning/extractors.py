"""
Main content extraction – find the most relevant content block in a page.

Uses a scoring heuristic: <main> > <article> > largest text block in <body>.
"""
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag


class MainContentExtractor:
    """Extract the primary content element from a cleaned HTML tree."""

    CANDIDATE_TAGS = ["main", "article", "[role=main]"]

    def extract(self, soup: BeautifulSoup) -> Optional[Tag]:
        for selector in self.CANDIDATE_TAGS:
            el = soup.select_one(selector)
            if el and self._text_len(el) > 100:
                return el

        body = soup.find("body")
        if not body:
            return None

        return self._largest_text_block(body)

    @staticmethod
    def _text_len(tag: Tag) -> int:
        return len(tag.get_text(strip=True))

    def _largest_text_block(self, root: Tag) -> Optional[Tag]:
        """Find the div/section with the most text, likely the main content."""
        best: Optional[Tag] = None
        best_len = 0

        for tag in root.find_all(["div", "section"]):
            tl = self._text_len(tag)
            if tl > best_len:
                best_len = tl
                best = tag

        if best and best_len > 100:
            return best
        return root
