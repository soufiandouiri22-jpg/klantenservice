"""
Context assembler – build the final context string for the LLM
from scored and filtered chunks.

Deduplicates, orders by relevance, and formats with source info.
"""
from typing import List, Dict


MAX_CONTEXT_TOKENS = 3000


def assemble_context(
    candidates: List[Dict],
    max_tokens: int = MAX_CONTEXT_TOKENS,
    min_confidence: float = 0.15,
) -> tuple[str, List[Dict], int]:
    """
    Build context from scored candidates.

    Returns:
        (context_text, included_candidates, total_tokens)
    """
    # Filter by minimum score
    viable = [c for c in candidates if (c.get("final_score") or 0) >= min_confidence]

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

    # Accumulate chunks up to token budget
    included = []
    total_tokens = 0

    for c in deduped:
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

    return context_text, included, total_tokens
