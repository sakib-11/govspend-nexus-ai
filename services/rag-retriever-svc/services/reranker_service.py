"""Reranker service — cross-encoder reranking for improved relevance."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from config import RAGRetrieverConfig
from models.retrieval import RetrievalResult

logger = logging.getLogger(__name__)


class RerankerService:
    """Rerank retrieval results using a cross-encoder model.

    Falls back gracefully when ``sentence-transformers`` is not installed
    or the model fails to load.
    """

    def __init__(self, config: RAGRetrieverConfig) -> None:
        self.config = config
        self._model = None
        self._ready = False

    async def initialize(self) -> None:
        """Attempt to load the cross-encoder model."""
        if self._ready:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.config.RERANK_MODEL, device="cpu")
            self._ready = True
            logger.info("Reranker loaded: %s", self.config.RERANK_MODEL)
        except ImportError:
            logger.warning("sentence-transformers not installed — reranking disabled")
        except Exception:
            logger.exception("Failed to load reranker model")

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """Rerank *results* for *query* using the cross-encoder.

        If the model is unavailable the original ordering is preserved.
        """
        if not self._ready or not results:
            return results

        top_k = top_k or self.config.RERANK_TOP_K
        candidates = results[: top_k]
        remainder = results[top_k :]

        # Truncate content for the cross-encoder
        pairs = [[query, r.content[:512]] for r in candidates]

        try:
            scores = await asyncio.to_thread(self._model.predict, pairs)

            for i, result in enumerate(candidates):
                result.rerank_score = float(scores[i])
                # Blend rerank score with existing similarity
                if result.similarity > 0:
                    result.similarity = (result.similarity + float(scores[i])) / 2
                else:
                    result.similarity = float(scores[i])
                result.relevance_confidence = round(result.similarity, 6)

            candidates.sort(key=lambda x: x.rerank_score or 0, reverse=True)
            candidates.extend(remainder)
            return candidates

        except Exception:
            logger.exception("Reranking failed — returning original order")
            return results
