"""
Reranking service – optional cross-encoder reranking of retrieval candidates.

Gracefully degrades: if no reranker model is available, returns candidates unchanged.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_reranker = None
_reranker_loaded = False


def _load_reranker():
    """Lazy-load cross-encoder model. Returns None if unavailable."""
    global _reranker, _reranker_loaded
    if _reranker_loaded:
        return _reranker

    _reranker_loaded = True
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        logger.info("Cross-encoder reranker loaded")
    except Exception as exc:
        logger.info("Cross-encoder not available, reranking disabled: %s", exc)
        _reranker = None

    return _reranker


def rerank(
    query: str,
    candidates: List[Dict],
    top_k: int = 10,
) -> List[Dict]:
    """
    Rerank candidates using a cross-encoder. Falls back to original order if unavailable.
    Each candidate dict must have 'content' key.
    Adds 'rerank_score' to each candidate.
    """
    model = _load_reranker()

    if model is None or len(candidates) <= 1:
        for c in candidates:
            c["rerank_score"] = c.get("vector_score", 0.0)
        return candidates[:top_k]

    try:
        pairs = [[query, c.get("content", "")[:512]] for c in candidates]
        scores = model.predict(pairs)

        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_k]

    except Exception as exc:
        logger.warning("Reranking failed, using vector order: %s", exc)
        for c in candidates:
            c["rerank_score"] = c.get("vector_score", 0.0)
        return candidates[:top_k]


def is_available() -> bool:
    """Check if reranking is available."""
    return _load_reranker() is not None
