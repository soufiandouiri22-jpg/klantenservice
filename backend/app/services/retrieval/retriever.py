"""
Retrieval service – hybrid search combining vector similarity, metadata filters,
and full-text search, followed by reranking, scoring, and context assembly.

This is the main entry point for all knowledge retrieval.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.services.indexing.models import IdxChunk, IdxSite
from app.services.indexing.embedding import OpenAIEmbeddingProvider, EmbeddingPipeline

from .query_classifier import classify_query
from .scorer import score_candidates, compute_confidence
from .reranker import rerank
from .context_assembler import assemble_context
from .debug_logger import log_retrieval_event

logger = logging.getLogger(__name__)


class RetrievalService:
    """Main retrieval service for searching the knowledge base."""

    def __init__(self, db: Session):
        self.db = db

    async def search(
        self,
        company_id: str,
        query: str,
        limit: int = 8,
        site_id: Optional[str] = None,
    ) -> Dict:
        """
        Full retrieval pipeline:
        1. Classify query
        2. Hybrid search (vector + metadata + fulltext)
        3. Rerank
        4. Score with boosts/penalties
        5. Assemble context
        6. Log for debugging

        Returns dict with keys: ok, results, context, confidence, debug
        """
        start = time.time()

        # Step 1: classify query
        query_classification = classify_query(query)

        # Step 2: hybrid search
        candidates = await self._hybrid_search(
            company_id=company_id,
            query=query,
            query_classification=query_classification,
            limit=limit * 4,  # Fetch more for reranking
            site_id=site_id,
        )

        if not candidates:
            latency_ms = int((time.time() - start) * 1000)
            log_retrieval_event(
                db=self.db, company_id=company_id, query=query,
                query_classification=query_classification,
                retrieval_strategy={"type": "hybrid", "site_id": site_id},
                filters_applied={}, candidates=[], confidence=0.0,
                context_tokens=0, latency_ms=latency_ms,
            )
            return {
                "ok": True,
                "results": [],
                "context": "",
                "confidence": 0.0,
                "message": "Geen relevante informatie gevonden.",
            }

        # Step 3: rerank
        reranked = rerank(query, candidates, top_k=limit * 2)

        # Step 4: score with boosts/penalties
        scored = score_candidates(reranked, query_classification)

        # Step 5: assemble context
        context_text, included, context_tokens = assemble_context(scored, max_tokens=3000)

        # Step 6: confidence
        confidence = compute_confidence(included)

        latency_ms = int((time.time() - start) * 1000)

        # Step 7: log
        log_retrieval_event(
            db=self.db, company_id=company_id, query=query,
            query_classification=query_classification,
            retrieval_strategy={"type": "hybrid", "site_id": site_id},
            filters_applied={"chunk_type_boost": query_classification},
            candidates=scored,
            confidence=confidence,
            context_tokens=context_tokens,
            latency_ms=latency_ms,
            reranked=True,
        )

        # Format results for the caller (tool_search_knowledge)
        results = [
            {
                "content": c["content"],
                "url": c.get("url", ""),
                "title": c.get("page_title", ""),
                "chunk_type": c.get("chunk_type", "general"),
                "section_path": c.get("section_path", ""),
                "score": c.get("final_score", 0.0),
            }
            for c in included
        ]

        message = self._build_message(results, confidence)

        return {
            "ok": True,
            "results": results,
            "context": context_text,
            "confidence": confidence,
            "message": message,
            "debug": {
                "query_classification": query_classification,
                "candidates_found": len(candidates),
                "reranked": True,
                "latency_ms": latency_ms,
            },
        }

    async def _hybrid_search(
        self,
        company_id: str,
        query: str,
        query_classification: str,
        limit: int,
        site_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Hybrid search combining:
        - Vector similarity (pgvector cosine distance)
        - Metadata filter (chunk_type boost via WHERE)
        - Full-text search (tsvector matching)
        """
        # Embed query
        query_embedding = await self._embed_query(query)
        if not query_embedding:
            return []

        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Build WHERE clause
        where_parts = ["c.company_id = :company_id", "c.embedding IS NOT NULL"]
        params: Dict = {
            "company_id": company_id,
            "embedding": embedding_str,
            "limit": limit,
        }

        if site_id:
            where_parts.append("c.site_id = :site_id")
            params["site_id"] = site_id

        # Full-text query (simple tokenisation for Dutch)
        ts_query_parts = [w for w in query.lower().split() if len(w) > 2]
        ts_query = " | ".join(ts_query_parts) if ts_query_parts else query.lower()
        params["ts_query"] = ts_query

        where_clause = " AND ".join(where_parts)

        # Hybrid scoring: combine vector similarity with full-text relevance
        sql = text(f"""
            SELECT
                c.id,
                c.content,
                c.url,
                c.page_title,
                c.page_type,
                c.chunk_type,
                c.section_path,
                c.heading_hierarchy,
                c.token_count,
                c.content_hash,
                c.metadata,
                (1.0 - (c.embedding <=> CAST(:embedding AS vector))) AS vector_sim,
                ts_rank_cd(c.content_tsv, to_tsquery('simple', :ts_query), 1) AS text_rank
            FROM idx_chunks c
            WHERE {where_clause}
            ORDER BY
                (1.0 - (c.embedding <=> CAST(:embedding AS vector))) DESC
            LIMIT :limit
        """)

        try:
            rows = self.db.execute(sql, params).fetchall()
        except Exception as exc:
            logger.error("Hybrid search query failed: %s", exc)
            return []

        candidates = []
        for row in rows:
            # Combined score: 80% vector + 20% text rank
            vector_sim = float(row.vector_sim) if row.vector_sim else 0.0
            text_rank = float(row.text_rank) if row.text_rank else 0.0
            combined = 0.8 * vector_sim + 0.2 * min(text_rank, 1.0)

            candidates.append({
                "chunk_id": str(row.id),
                "content": row.content,
                "url": row.url or "",
                "page_title": row.page_title or "",
                "page_type": row.page_type or "unknown",
                "chunk_type": row.chunk_type or "general",
                "section_path": row.section_path or "",
                "heading_hierarchy": row.heading_hierarchy or [],
                "token_count": row.token_count or 0,
                "content_hash": row.content_hash or "",
                "metadata": row.metadata or {},
                "vector_score": round(combined, 4),
            })

        return candidates

    async def _embed_query(self, query: str) -> Optional[List[float]]:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set, cannot embed query")
            return None

        provider = OpenAIEmbeddingProvider(settings.OPENAI_API_KEY)
        try:
            return await provider.embed(query)
        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)
            return None
        finally:
            await provider.close()

    @staticmethod
    def _build_message(results: List[Dict], confidence: float) -> str:
        if not results:
            return "Geen relevante informatie gevonden in de kennisbank."

        if confidence < 0.2:
            return (
                "Ik heb beperkte informatie gevonden. Het antwoord is mogelijk niet volledig. "
                "Gevonden informatie:\n\n" + "\n".join(r["content"][:300] for r in results[:2])
            )

        return "\n\n".join(r["content"] for r in results)
