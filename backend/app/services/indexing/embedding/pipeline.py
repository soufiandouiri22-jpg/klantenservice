"""
Embedding pipeline – idempotent, batched, with hash-check to skip unchanged chunks.
"""
import logging
from typing import List, Optional

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

EMBEDDING_VERSION = "v1"


class EmbeddingPipeline:
    """Orchestrate embedding generation for chunks."""

    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider
        self.model_name = provider.name
        self.version = EMBEDDING_VERSION

    async def embed_chunks(
        self,
        chunks: list[dict],
        existing_hashes: Optional[set[str]] = None,
    ) -> list[dict]:
        """
        Embed a list of chunk dicts (must have 'content' and 'content_hash' keys).
        Skips chunks whose content_hash is in existing_hashes (idempotent re-embed).
        Returns the same list with 'embedding', 'embedding_model', 'embedding_version' added.
        """
        existing = existing_hashes or set()
        to_embed_indices: list[int] = []
        texts: list[str] = []

        for i, chunk in enumerate(chunks):
            if chunk.get("content_hash") in existing:
                logger.debug("Skipping unchanged chunk %s", chunk["content_hash"])
                continue
            to_embed_indices.append(i)
            texts.append(chunk["content"])

        if not texts:
            logger.info("All chunks already embedded, nothing to do")
            return chunks

        logger.info("Embedding %d chunks (skipped %d unchanged)", len(texts), len(chunks) - len(texts))

        try:
            embeddings = await self.provider.embed_batch(texts)
        except Exception as exc:
            logger.error("Embedding pipeline failed: %s", exc)
            raise

        for idx, embedding in zip(to_embed_indices, embeddings):
            chunks[idx]["embedding"] = embedding
            chunks[idx]["embedding_model"] = self.model_name
            chunks[idx]["embedding_version"] = self.version

        return chunks

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single search query."""
        return await self.provider.embed(query)

    async def close(self):
        await self.provider.close()
