"""
Retrieval service – hybrid search combining vector similarity, metadata filters,
and full-text search, followed by reranking, scoring, and context assembly.

Tuned for realtime voice: fetch 15, rerank, pass top 5 to context.
"""
import logging
import time
from typing import Dict, List, Optional
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

FETCH_LIMIT = 15
RERANK_TOP_K = 10
CONTEXT_MAX_CHUNKS = 5
CONTEXT_MAX_TOKENS = 2000


class RetrievalService:
    """Main retrieval service for searching the knowledge base."""

    def __init__(self, db: Session):
        self.db = db

    async def search(
        self,
        company_id: str,
        query: str,
        limit: int = 5,
        site_id: Optional[str] = None,
    ) -> Dict:
        """
        Full retrieval pipeline:
        1. Classify query
        2. Hybrid search (vector + metadata + fulltext) — fetch 15
        3. Rerank — keep top 10
        4. Score with boosts/penalties + junk filter
        5. Assemble context — top 5
        6. Log for debugging
        """
        start = time.time()

        # Step 1: classify query
        query_classification = classify_query(query)
        logger.info("[retriever] query=%r classification=%s", query, query_classification)

        # Step 2: hybrid search
        candidates = await self._hybrid_search(
            company_id=company_id,
            query=query,
            query_classification=query_classification,
            limit=FETCH_LIMIT,
            site_id=site_id,
        )

        if not candidates:
            latency_ms = int((time.time() - start) * 1000)
            logger.info("[retriever] no candidates found, latency=%dms", latency_ms)
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

        logger.info("[retriever] hybrid search returned %d candidates", len(candidates))

        # Log top candidates before reranking
        for i, c in enumerate(candidates[:5]):
            logger.info(
                "[retriever] pre-rerank #%d: score=%.4f type=%s url=%s title=%r preview=%r",
                i + 1, c.get("vector_score", 0), c.get("chunk_type", "?"),
                c.get("url", "")[:80], (c.get("page_title") or "")[:60],
                c.get("content", "")[:250].replace("\n", " "),
            )

        # Step 3: rerank
        reranked = rerank(query, candidates, top_k=RERANK_TOP_K)

        # Log top candidates after reranking
        logger.info("[retriever] post-rerank top %d:", min(5, len(reranked)))
        for i, c in enumerate(reranked[:5]):
            logger.info(
                "[retriever] post-rerank #%d: rerank_score=%.4f vector_score=%.4f "
                "type=%s url=%s title=%r preview=%r",
                i + 1, c.get("rerank_score", 0), c.get("vector_score", 0),
                c.get("chunk_type", "?"), c.get("url", "")[:80],
                (c.get("page_title") or "")[:60],
                c.get("content", "")[:250].replace("\n", " "),
            )

        # Step 4: score with boosts/penalties + junk filter
        scored = score_candidates(reranked, query_classification)

        # Step 5: assemble context (max 5 chunks)
        context_text, included, context_tokens = assemble_context(
            scored,
            max_tokens=CONTEXT_MAX_TOKENS,
            max_chunks=CONTEXT_MAX_CHUNKS,
        )

        # Step 6: confidence
        confidence = compute_confidence(included)

        latency_ms = int((time.time() - start) * 1000)

        logger.info(
            "[retriever] done: %d candidates -> %d reranked -> %d scored -> %d in context, "
            "confidence=%.3f, latency=%dms",
            len(candidates), len(reranked), len(scored), len(included),
            confidence, latency_ms,
        )

        # Log final context for debugging
        if context_text:
            logger.info(
                "[retriever] final_context (%d chars, %d tokens):\n%s",
                len(context_text), context_tokens, context_text[:1500],
            )

        # Step 7: log to DB
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
                "included": len(included),
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
        Hybrid search: vector similarity + full-text + optional type priority.

        For typed queries (pricing, contact, etc.), fetches type-matched chunks
        first, then backfills with general results.
        """
        query_embedding = await self._embed_query(query)
        if not query_embedding:
            return []

        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Full-text query
        ts_query_parts = [w for w in query.lower().split() if len(w) > 2]
        ts_query = " | ".join(ts_query_parts) if ts_query_parts else query.lower()

        # For specific query types, fetch type-matched chunks first and
        # backfill with general results. Even a single typed match is valuable
        # (e.g. a company with only 2 pricing chunks must not lose them).
        if query_classification not in ("general",):
            typed_candidates = await self._fetch_candidates(
                company_id=company_id,
                embedding_str=embedding_str,
                ts_query=ts_query,
                limit=limit,
                site_id=site_id,
                chunk_type_filter=query_classification,
            )
            if typed_candidates:
                remaining = limit - len(typed_candidates)
                if remaining > 0:
                    general_candidates = await self._fetch_candidates(
                        company_id=company_id,
                        embedding_str=embedding_str,
                        ts_query=ts_query,
                        limit=remaining,
                        site_id=site_id,
                    )
                    seen_ids = {c["chunk_id"] for c in typed_candidates}
                    for c in general_candidates:
                        if c["chunk_id"] not in seen_ids:
                            typed_candidates.append(c)
                logger.info(
                    "[retriever] type-priority fetch: %d %s chunks + backfill = %d total",
                    len([c for c in typed_candidates if c.get("chunk_type") == query_classification]),
                    query_classification, len(typed_candidates),
                )
                return typed_candidates

            # No typed chunks found — try content-based fallback for pricing
            if query_classification == "pricing":
                pricing_fallback = await self._fetch_candidates(
                    company_id=company_id,
                    embedding_str=embedding_str,
                    ts_query=ts_query,
                    limit=limit,
                    site_id=site_id,
                    content_contains="€",
                )
                if pricing_fallback:
                    logger.info(
                        "[retriever] pricing content fallback: %d chunks containing €",
                        len(pricing_fallback),
                    )
                    return pricing_fallback

        # Default: fetch without type filter
        return await self._fetch_candidates(
            company_id=company_id,
            embedding_str=embedding_str,
            ts_query=ts_query,
            limit=limit,
            site_id=site_id,
        )

    async def _fetch_candidates(
        self,
        company_id: str,
        embedding_str: str,
        ts_query: str,
        limit: int,
        site_id: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
        content_contains: Optional[str] = None,
    ) -> List[Dict]:
        """Execute the hybrid search SQL query."""
        where_parts = ["c.company_id = :company_id", "c.embedding IS NOT NULL"]
        params: Dict = {
            "company_id": company_id,
            "embedding": embedding_str,
            "limit": limit,
            "ts_query": ts_query,
        }

        if site_id:
            where_parts.append("c.site_id = :site_id")
            params["site_id"] = site_id

        if chunk_type_filter:
            where_parts.append("(c.chunk_type = :chunk_type OR c.page_type = :chunk_type)")
            params["chunk_type"] = chunk_type_filter

        if content_contains:
            where_parts.append("c.content LIKE :content_pattern")
            params["content_pattern"] = f"%{content_contains}%"

        where_clause = " AND ".join(where_parts)

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
