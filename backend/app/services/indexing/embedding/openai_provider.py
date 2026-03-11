"""
OpenAI embedding provider – text-embedding-3-small (1536 dims).
Batched, with retry and rate-limit handling.
"""
import asyncio
import logging
from typing import List

import httpx

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
MAX_BATCH = 100  # OpenAI limit per request
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"
    dimensions = DIMENSIONS

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        await self._ensure_client()
        all_embeddings: List[List[float]] = []

        # Split into batches of MAX_BATCH
        for i in range(0, len(texts), MAX_BATCH):
            batch = texts[i : i + MAX_BATCH]
            embeddings = await self._request_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _request_with_retry(self, texts: List[str]) -> List[List[float]]:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "input": texts,
                    },
                )

                if resp.status_code == 429:
                    wait = RETRY_BACKOFF * (attempt + 1)
                    logger.warning("OpenAI rate limit, retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()["data"]
                # Sort by index to preserve order
                data.sort(key=lambda x: x["index"])
                return [item["embedding"] for item in data]

            except httpx.TimeoutException:
                logger.warning("OpenAI embedding timeout, attempt %d/%d", attempt + 1, MAX_RETRIES)
                await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
            except Exception as exc:
                logger.error("OpenAI embedding error: %s", exc)
                if attempt == MAX_RETRIES - 1:
                    raise

        raise RuntimeError(f"Failed to embed after {MAX_RETRIES} retries")
