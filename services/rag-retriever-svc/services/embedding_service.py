"""Embedding service — generate vector embeddings for text."""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional

from config import RAGRetrieverConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate vector embeddings using the configured provider.

    Supports OpenAI ``text-embedding-ada-002`` (1536-d) by default and
    falls back to a deterministic hash-based embedding when the API is
    unavailable (useful for development and testing).
    """

    def __init__(self, config: RAGRetrieverConfig) -> None:
        self.config = config
        self._client = None
        self._dimension = config.EMBEDDING_DIMENSION

    async def _get_client(self):
        if self._client is None and self.config.OPENAI_API_KEY:
            try:
                import openai

                kwargs: dict = {"api_key": self.config.OPENAI_API_KEY}
                if self.config.OPENAI_API_BASE:
                    kwargs["base_url"] = self.config.OPENAI_API_BASE
                self._client = openai.AsyncOpenAI(**kwargs)
            except ImportError:
                logger.warning("openai package not installed — using fallback embeddings")
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a list of *texts*.

        Returns one embedding per text.  If the API call fails for a
        particular text, a fallback embedding is returned.
        """
        if not texts:
            return []

        client = await self._get_client()
        if client is None:
            return [self._fallback_embedding(t) for t in texts]

        try:
            response = await client.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=texts,
            )
            # Sort by index to match input order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception:
            logger.exception("Embedding API call failed — using fallback")
            return [self._fallback_embedding(t) for t in texts]

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a single embedding."""
        results = await self.generate_embeddings([text])
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Fallback (hash-based deterministic embedding)
    # ------------------------------------------------------------------

    def _fallback_embedding(self, text: str) -> List[float]:
        """Deterministic hash-based embedding for dev / testing.

        Produces a *dimension*-length vector of floats in [-1, 1] derived
        from SHA-512 of the input text.  This is NOT semantically meaningful
        but allows the pipeline to run without an API key.
        """
        digest = hashlib.sha512(text.encode("utf-8")).hexdigest()
        # Repeat digest to fill the dimension
        raw = ""
        while len(raw) < self._dimension * 2:
            raw += digest
            digest = hashlib.sha512(digest.encode("utf-8")).hexdigest()

        embedding: List[float] = []
        for i in range(self._dimension):
            hex_pair = raw[i * 2 : i * 2 + 2]
            val = (int(hex_pair, 16) / 127.5) - 1.0  # map to [-1, 1]
            embedding.append(val)

        # Normalise to unit length
        norm = sum(v * v for v in embedding) ** 0.5
        if norm > 0:
            embedding = [v / norm for v in embedding]
        return embedding
