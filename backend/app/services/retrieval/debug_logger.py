"""
Retrieval debug logger – persist every search event for inspection.
Writes to rtv_events and rtv_results tables.
"""
import logging
from typing import List, Dict, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.indexing.models import RtvEvent, RtvResult

logger = logging.getLogger(__name__)


def log_retrieval_event(
    db: Session,
    company_id: str,
    query: str,
    query_classification: str,
    retrieval_strategy: Dict,
    filters_applied: Dict,
    candidates: List[Dict],
    confidence: float,
    context_tokens: int,
    latency_ms: int,
    reranked: bool = False,
) -> Optional[str]:
    """Log a retrieval event and its results. Returns the event ID."""
    try:
        event = RtvEvent(
            id=uuid4(),
            company_id=company_id,
            query=query,
            query_classification=query_classification,
            retrieval_strategy=retrieval_strategy,
            filters_applied=filters_applied,
            candidates_found=len(candidates),
            reranked=reranked,
            top_score=candidates[0].get("final_score") if candidates else None,
            confidence=confidence,
            chunks_returned=sum(1 for c in candidates if c.get("included_in_context")),
            context_tokens=context_tokens,
            latency_ms=latency_ms,
        )
        db.add(event)

        for c in candidates:
            result = RtvResult(
                id=uuid4(),
                event_id=event.id,
                chunk_id=c.get("chunk_id"),
                rank=c.get("rank", 0),
                vector_score=c.get("vector_score"),
                rerank_score=c.get("rerank_score"),
                metadata_boost=c.get("metadata_boost", 0.0),
                final_score=c.get("final_score"),
                included_in_context=c.get("included_in_context", False),
            )
            db.add(result)

        db.commit()
        return str(event.id)

    except Exception as exc:
        logger.error("Failed to log retrieval event: %s", exc)
        db.rollback()
        return None
