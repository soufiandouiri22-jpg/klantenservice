"""
Context assembler – build the final context string for the LLM
from scored and filtered chunks.

Deduplicates, caps at MAX_CHUNKS, orders by relevance, and formats.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

MAX_CONTEXT_TOKENS = 2000
MAX_CHUNKS = 5
MIN_CONFIDENCE = 0.15


def assemble_context(
    candidates: List[Dict],
    max_tokens: int = MAX_CONTEXT_TOKENS,
    min_confidence: float = MIN_CONFIDENCE,
    max_chunks: int = MAX_CHUNKS,
) -> tuple[str, List[Dict], int]:
    """
    Build context from scored candidates.

    Returns:
        (context_text, included_candidates, total_tokens)
    """
    viable = [
        c for c in candidates
        if (c.get("final_score") or 0) >= min_confidence and not c.get("is_junk")
    ]

    if not viable:
        return "", [], 0

    # Deduplicate near-identical chunks (same content_hash)
    seen_hashes = set()
    deduped = []
    for c in viable:
        h = c.get("content_hash", "")
        if h and h in seen_hashes:
            continue
        if h:
            seen_hashes.add(h)
        deduped.append(c)

    included = []
    total_tokens = 0

    for c in deduped:
        if len(included) >= max_chunks:
            break
        tokens = c.get("token_count") or len(c.get("content", "").split())
        if total_tokens + tokens > max_tokens and included:
            break
        c["included_in_context"] = True
        c["rank"] = len(included) + 1
        included.append(c)
        total_tokens += tokens

    # Format context
    parts = []
    for c in included:
        source_label = ""
        url = c.get("url", "")
        title = c.get("page_title", "")
        if title and url:
            source_label = f"[Bron: {title} — {url}]"
        elif url:
            source_label = f"[Bron: {url}]"

        section = c.get("section_path", "")
        if section:
            source_label += f" (sectie: {section})"

        parts.append(f"{source_label}\n{c['content']}" if source_label else c["content"])

    context_text = "\n\n---\n\n".join(parts)

    # Log assembled context for debugging
    logger.info(
        "[context_assembler] assembled %d chunks, %d tokens, context_len=%d chars",
        len(included), total_tokens, len(context_text),
    )
    for i, c in enumerate(included):
        logger.info(
            "[context_assembler] chunk %d: type=%s score=%.4f url=%s title=%r preview=%r",
            i + 1,
            c.get("chunk_type", "?"),
            c.get("final_score", 0),
            c.get("url", "")[:80],
            (c.get("page_title") or "")[:60],
            c.get("content", "")[:150].replace("\n", " "),
        )

    return context_text, included, total_tokens
