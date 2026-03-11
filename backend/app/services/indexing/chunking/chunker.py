"""
Semantic chunker – splits cleaned text into coherent, typed chunks
based on heading structure rather than blind token counts.

Strategy:
1. Split text into sections by headings (H1-H4).
2. Run special extractors (FAQ, pricing, contact) on each section.
3. Oversized sections get split on paragraph boundaries.
4. Each chunk gets heading hierarchy, section path, and type classification.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .classifiers import classify_chunk_type


@dataclass
class Chunk:
    """A single semantic chunk ready for embedding."""
    content: str
    chunk_type: str = "general"
    section_path: str = ""
    heading_hierarchy: list[str] = field(default_factory=list)
    position_on_page: int = 0
    token_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


# Approximate tokens by splitting on whitespace
def _approx_tokens(text: str) -> int:
    return len(text.split())


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Target max ~400 tokens per chunk; never under 30 tokens
MAX_TOKENS = 400
MIN_TOKENS = 30


class SemanticChunker:
    """Split structured text into heading-aware semantic chunks."""

    def __init__(self, max_tokens: int = MAX_TOKENS, min_tokens: int = MIN_TOKENS):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    def chunk(
        self,
        text: str,
        page_type: str = "unknown",
        url: str = "",
    ) -> List[Chunk]:
        if not text or not text.strip():
            return []

        sections = self._split_by_headings(text)
        chunks: List[Chunk] = []
        position = 0

        for section in sections:
            section_chunks = self._process_section(
                section, page_type=page_type, position_start=position,
            )
            for c in section_chunks:
                c.position_on_page = position
                position += 1
            chunks.extend(section_chunks)

        # Filter out very small chunks
        chunks = [c for c in chunks if _approx_tokens(c.content) >= self.min_tokens]

        # Re-number positions
        for i, c in enumerate(chunks):
            c.position_on_page = i
            c.token_count = _approx_tokens(c.content)

        return chunks

    def _split_by_headings(self, text: str) -> list[dict]:
        """Split text into sections delineated by headings."""
        sections = []
        lines = text.split("\n")
        current_heading = ""
        current_level = 0
        current_lines: list[str] = []
        heading_stack: list[str] = []

        for line in lines:
            m = _HEADING_RE.match(line.strip())
            if m:
                # Save previous section
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        sections.append({
                            "heading": current_heading,
                            "level": current_level,
                            "body": body,
                            "heading_hierarchy": list(heading_stack),
                        })
                # Update heading stack
                level = len(m.group(1))
                heading_text = m.group(2).strip()
                heading_stack = heading_stack[:max(0, level - 1)]
                heading_stack.append(heading_text)
                current_heading = heading_text
                current_level = level
                current_lines = []
            else:
                current_lines.append(line)

        # Last section
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "body": body,
                    "heading_hierarchy": list(heading_stack),
                })

        # If no headings found, treat entire text as one section
        if not sections and text.strip():
            sections.append({
                "heading": "",
                "level": 0,
                "body": text.strip(),
                "heading_hierarchy": [],
            })

        return sections

    def _process_section(
        self,
        section: dict,
        page_type: str,
        position_start: int,
    ) -> List[Chunk]:
        body = section["body"]
        heading = section["heading"]
        hierarchy = section["heading_hierarchy"]
        section_path = " > ".join(hierarchy) if hierarchy else ""

        # Prefix heading to body for context
        full_text = f"{heading}\n{body}" if heading else body

        tokens = _approx_tokens(full_text)

        if tokens <= self.max_tokens:
            ctype = classify_chunk_type(
                full_text, page_type=page_type,
                section_path=section_path, heading=heading,
            )
            return [Chunk(
                content=full_text.strip(),
                chunk_type=ctype,
                section_path=section_path,
                heading_hierarchy=hierarchy,
                metadata={"heading": heading} if heading else {},
            )]

        # Oversized: split on paragraphs
        return self._split_oversized(
            full_text, heading=heading, hierarchy=hierarchy,
            section_path=section_path, page_type=page_type,
        )

    def _split_oversized(
        self,
        text: str,
        heading: str,
        hierarchy: list[str],
        section_path: str,
        page_type: str,
    ) -> List[Chunk]:
        """Split oversized section on paragraph boundaries."""
        paragraphs = re.split(r"\n{2,}", text)
        chunks: List[Chunk] = []
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            pt = _approx_tokens(para)

            if current_tokens + pt > self.max_tokens and current_parts:
                chunk_text = "\n\n".join(current_parts).strip()
                ctype = classify_chunk_type(
                    chunk_text, page_type=page_type,
                    section_path=section_path, heading=heading,
                )
                chunks.append(Chunk(
                    content=chunk_text,
                    chunk_type=ctype,
                    section_path=section_path,
                    heading_hierarchy=hierarchy,
                    metadata={"heading": heading} if heading else {},
                ))
                current_parts = []
                current_tokens = 0

            current_parts.append(para)
            current_tokens += pt

        if current_parts:
            chunk_text = "\n\n".join(current_parts).strip()
            ctype = classify_chunk_type(
                chunk_text, page_type=page_type,
                section_path=section_path, heading=heading,
            )
            chunks.append(Chunk(
                content=chunk_text,
                chunk_type=ctype,
                section_path=section_path,
                heading_hierarchy=hierarchy,
                metadata={"heading": heading} if heading else {},
            ))

        return chunks
