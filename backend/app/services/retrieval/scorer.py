"""
Scoring & confidence – compute final scores with type boosts/penalties.

Design goals:
- Boost chunks whose type matches the query classification.
- Penalize generic homepage/marketing chunks when query is specific.
- Penalize near-duplicate chunks.
- Compute overall confidence from score distribution.
"""
from typing import List, Dict, Optional


# Boost multiplier when chunk_type matches query_classification
TYPE_MATCH_BOOST = 0.15

# Penalty for homepage/general chunks when query is specific
GENERIC_PENALTY = -0.10

# Penalty for chunks with very little information (< 50 tokens)
LOW_INFO_PENALTY = -0.08


def score_candidates(
    candidates: List[Dict],
    query_classification: str,
) -> List[Dict]:
    """
    Score and sort candidates. Each candidate dict should have:
      - vector_score (float, 0-1, higher = more similar)
      - chunk_type (str)
      - page_type (str)
      - token_count (int)
      - content (str)

    Adds 'metadata_boost' and 'final_score' to each candidate.
    Returns candidates sorted by final_score descending.
    """
    for c in candidates:
        boost = 0.0
        vs = c.get("vector_score", 0.0)

        # Type match boost
        if query_classification != "general" and c.get("chunk_type") == query_classification:
            boost += TYPE_MATCH_BOOST

        # Generic penalty for homepage chunks on specific queries
        if query_classification != "general":
            if c.get("page_type") == "home" and c.get("chunk_type") == "general":
                boost += GENERIC_PENALTY

        # Low info penalty
        if (c.get("token_count") or 0) < 50:
            boost += LOW_INFO_PENALTY

        c["metadata_boost"] = round(boost, 4)
        c["final_score"] = round(vs + boost, 4)

    # Sort descending by final_score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates


def compute_confidence(candidates: List[Dict], top_n: int = 5) -> float:
    """
    Compute a confidence score (0-1) based on the top candidates.
    High confidence = top scores are high and close together (strong evidence).
    Low confidence = top scores are low or spread (weak/conflicting evidence).
    """
    if not candidates:
        return 0.0

    top = candidates[:top_n]
    scores = [c.get("final_score", 0.0) for c in top]
    top_score = scores[0]

    if top_score <= 0.0:
        return 0.0

    # Base confidence from top score (vector similarity + boosts)
    # vector_score is cosine similarity (0-1), so final_score is roughly in that range
    confidence = min(1.0, max(0.0, top_score))

    # If only 1 candidate, reduce confidence slightly
    if len(scores) == 1:
        confidence *= 0.8

    return round(confidence, 3)
