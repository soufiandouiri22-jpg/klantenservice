"""
FAQ extractor – detect question/answer structures and produce dedicated FAQ chunks.
"""
import re
from typing import List

from .chunker import Chunk


# Patterns for Q&A structures
_QA_PATTERNS = [
    # "Vraag?" followed by answer paragraph
    re.compile(
        r"(?P<question>[^\n]{15,200}\?)\s*\n+(?P<answer>[^\n#]{20,})",
        re.MULTILINE,
    ),
]

# Heading-based FAQ: "### Vraag?" followed by text
_HEADING_QA = re.compile(
    r"^#{1,4}\s+(?P<question>[^\n]{10,200}\?)\s*\n+(?P<answer>(?:(?!^#{1,4}\s).+\n?)+)",
    re.MULTILINE,
)


def extract_faq_chunks(text: str, heading_hierarchy: list[str] | None = None) -> List[Chunk]:
    """Extract FAQ question/answer pairs as individual chunks."""
    chunks: List[Chunk] = []
    hierarchy = heading_hierarchy or []

    # Try heading-based Q&A first
    for m in _HEADING_QA.finditer(text):
        question = m.group("question").strip()
        answer = m.group("answer").strip()
        if len(answer) < 20:
            continue
        chunks.append(Chunk(
            content=f"Vraag: {question}\nAntwoord: {answer}",
            chunk_type="faq",
            section_path=" > ".join(hierarchy + ["FAQ"]) if hierarchy else "FAQ",
            heading_hierarchy=hierarchy,
            metadata={"faq_question": question},
        ))

    # If heading-based found enough, return
    if len(chunks) >= 2:
        return chunks

    # Fallback: inline Q&A patterns
    for pattern in _QA_PATTERNS:
        for m in pattern.finditer(text):
            question = m.group("question").strip()
            answer = m.group("answer").strip()
            if len(answer) < 20:
                continue
            # Avoid duplicates
            if any(question in c.metadata.get("faq_question", "") for c in chunks):
                continue
            chunks.append(Chunk(
                content=f"Vraag: {question}\nAntwoord: {answer}",
                chunk_type="faq",
                section_path=" > ".join(hierarchy + ["FAQ"]) if hierarchy else "FAQ",
                heading_hierarchy=hierarchy,
                metadata={"faq_question": question},
            ))

    return chunks
