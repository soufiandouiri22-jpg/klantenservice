"""
Scoring & confidence – compute final scores with type boosts, penalties,
and content quality filters.

Filters out junk chunks (JSON dumps, metadata, prompt fragments, etc.)
before scoring.
"""
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

TYPE_MATCH_BOOST = 0.20
GENERIC_PENALTY = -0.12
LOW_INFO_PENALTY = -0.10
JUNK_PENALTY = -0.40

# Patterns that indicate junk / non-informational content
_JUNK_PATTERNS = [
    re.compile(r"^\s*\{.*\}\s*$", re.DOTALL),  # JSON object
    re.compile(r"^\s*\[.*\]\s*$", re.DOTALL),  # JSON array
    re.compile(r"(system_prompt|user_message|assistant_message|<\|im_start\|>)", re.I),
    re.compile(r"(\"type\":\s*\"|\bschema\b.*\bproperties\b)", re.I),
    re.compile(r"(charset=|content-type:|<!DOCTYPE|<html|<head>)", re.I),
    re.compile(r"(__webpack|module\.exports|import\s+\{|require\()", re.I),
    re.compile(r"(cookie.?policy|privacy.?policy|terms.?of.?service).{0,30}(accept|decline|agree)", re.I),
]


def _is_junk(content: str) -> bool:
    """Detect chunks that contain prompt-like text, metadata, JSON, or boilerplate."""
    if not content or len(content.strip()) < 20:
        return True
    for pat in _JUNK_PATTERNS:
        if pat.search(content[:500]):
            return True
    return False


def score_candidates(
    candidates: List[Dict],
    query_classification: str,
) -> List[Dict]:
    """
    Score and sort candidates. Filters junk, applies type boosts/penalties.
    Adds 'metadata_boost', 'final_score', and 'is_junk' to each candidate.
    """
    scored = []
    junk_count = 0

    for c in candidates:
        content = c.get("content", "")
        if _is_junk(content):
            c["is_junk"] = True
            c["metadata_boost"] = JUNK_PENALTY
            c["final_score"] = max(0.0, c.get("rerank_score", c.get("vector_score", 0.0)) + JUNK_PENALTY)
            junk_count += 1
            continue

        c["is_junk"] = False
        boost = 0.0
        base_score = c.get("rerank_score", c.get("vector_score", 0.0))

        # Type match boost (stronger for pricing)
        if query_classification != "general":
            if c.get("chunk_type") == query_classification:
                boost += TYPE_MATCH_BOOST
            elif c.get("page_type") == query_classification:
                boost += TYPE_MATCH_BOOST * 0.6

        # Generic homepage penalty on specific queries
        if query_classification != "general":
            if c.get("page_type") == "home" and c.get("chunk_type") == "general":
                boost += GENERIC_PENALTY

        # Low info penalty
        if (c.get("token_count") or 0) < 50:
            boost += LOW_INFO_PENALTY

        c["metadata_boost"] = round(boost, 4)
        c["final_score"] = round(base_score + boost, 4)
        scored.append(c)

    if junk_count:
        logger.info("[scorer] filtered %d junk chunks out of %d", junk_count, len(candidates))

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored


def compute_confidence(candidates: List[Dict], top_n: int = 5) -> float:
    """
    Confidence score (0-1) from top candidates.
    High = strong evidence, low = weak/conflicting.
    """
    if not candidates:
        return 0.0

    top = candidates[:top_n]
    scores = [c.get("final_score", 0.0) for c in top]
    top_score = scores[0]

    if top_score <= 0.0:
        return 0.0

    confidence = min(1.0, max(0.0, top_score))

    if len(scores) == 1:
        confidence *= 0.8

    return round(confidence, 3)
