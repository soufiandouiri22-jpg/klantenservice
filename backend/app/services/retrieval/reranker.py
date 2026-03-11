"""
Reranking service – cross-encoder reranking of retrieval candidates.

Uses ms-marco-TinyBERT-L-2-v2: fastest viable cross-encoder (~5x faster than
MiniLM-L-6 on CPU) while still providing meaningful relevance ordering.

Gracefully degrades: if the model cannot be loaded, returns candidates
re-sorted by their existing vector_score.
"""
import logging
import time
from typing import List, Dict

logger = logging.getLogger(__name__)

_reranker = None
_reranker_loaded = False


def _load_reranker():
    """Lazy-load cross-encoder. Returns None if unavailable."""
    global _reranker, _reranker_loaded
    if _reranker_loaded:
        return _reranker

    _reranker_loaded = True
    try:
        from sentence_transformers import CrossEncoder
        model_name = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
        logger.info("Loading cross-encoder model: %s", model_name)
        t0 = time.time()
        _reranker = CrossEncoder(model_name)
        logger.info("Cross-encoder loaded in %.1fs", time.time() - t0)
    except Exception as exc:
        logger.warning("Cross-encoder not available, reranking disabled: %s", exc)
        _reranker = None

    return _reranker


def preload():
    """Call during app startup to avoid first-request latency."""
    _load_reranker()


def rerank(
    query: str,
    candidates: List[Dict],
    top_k: int = 10,
) -> List[Dict]:
    """
    Rerank candidates using cross-encoder. Falls back to vector_score ordering.
    Adds 'rerank_score' to each candidate.
    """
    model = _load_reranker()

    if model is None or len(candidates) <= 1:
        for c in candidates:
            c["rerank_score"] = c.get("vector_score", 0.0)
        return candidates[:top_k]

    try:
        t0 = time.time()
        pairs = [[query, c.get("content", "")[:384]] for c in candidates]
        scores = model.predict(pairs)

        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        elapsed = (time.time() - t0) * 1000
        logger.info(
            "[reranker] reranked %d candidates in %.0fms, top_score=%.4f",
            len(candidates), elapsed, candidates[0]["rerank_score"] if candidates else 0,
        )
        return candidates[:top_k]

    except Exception as exc:
        logger.warning("Reranking failed, falling back to vector order: %s", exc)
        for c in candidates:
            c["rerank_score"] = c.get("vector_score", 0.0)
        return candidates[:top_k]


def is_available() -> bool:
    """Check if reranking is available."""
    return _load_reranker() is not None
