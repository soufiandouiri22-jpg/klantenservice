"""
Reranking service – pass-through that preserves the vector_score ordering.

Cross-encoder reranking is disabled: the multilingual mmarco model adds ~5s
latency on CPU which causes ElevenLabs tool-call timeouts and inconsistent
voice responses.  The vector search (OpenAI text-embedding-3-small, natively
multilingual) combined with type boosts and policy penalties in the scorer
provides sufficient ranking quality at <300ms total latency.

The rerank() interface is kept so the rest of the pipeline doesn't need changes.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def preload():
    """No-op — cross-encoder is disabled."""
    pass


def rerank(
    query: str,
    candidates: List[Dict],
    top_k: int = 10,
) -> List[Dict]:
    """
    Pass-through: copies vector_score to rerank_score and trims to top_k.
    """
    for c in candidates:
        c["rerank_score"] = c.get("vector_score", 0.0)

    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates[:top_k]


def is_available() -> bool:
    """Cross-encoder is disabled; always returns False."""
    return False
