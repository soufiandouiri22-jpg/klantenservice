"""
Abstract base class for embedding providers.
"""
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Interface for pluggable embedding backends."""

    name: str = "base"
    dimensions: int = 0

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Embed a single text. Returns a vector."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts. Returns list of vectors."""
        ...

    async def close(self):
        """Release resources."""
        pass
