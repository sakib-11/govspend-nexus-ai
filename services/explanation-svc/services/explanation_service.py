"""Explanation service — main orchestrator for explanation generation pipeline."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from config import ExplanationConfig
from models.explanation import (
    ExplanationRequest,
    ExplanationResponse,
    ExplanationStatus,
)
from services.cache_service import CacheService
from services.fallback_service import FallbackService
from services.llm_client import LLMClientService
from services.regeneration_service import RegenerationService
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class ExplanationService:
    """Orchestrate: cache → LLM → validate → regenerate → fallback → store."""

    def __init__(
        self,
        db_pool=None,
        llm_client: Optional[LLMClientService] = None,
        validation_service: Optional[ValidationService] = None,
        regeneration_service: Optional[RegenerationService] = None,
        fallback_service: Optional[FallbackService] = None,
        cache_service: Optional[CacheService] = None,
        config: Optional[ExplanationConfig] = None,
    ) -> None:
        self.db_pool = db_pool
        self.config = config or ExplanationConfig()
        self.llm = llm_client
        self.validator = validation_service or ValidationService(self.config)
        self.regenerator = regeneration_service
        self.fallback = fallback_service or FallbackService(self.config)
        self.cache = cache_service or CacheService(config=self.config)

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    async def generate(
        self,
        request: ExplanationRequest,
        force_regenerate: bool = False,
    ) -> ExplanationResponse:
        """Full pipeline: cache → LLM → validate → regenerate → fallback."""

        # 1. Cache
        if not force_regenerate and self.config.CACHE_ENABLED:
            cached = await self.cache.get(request.case_id)
            if cached:
                logger.info("Cache hit for case %s", request.case_id)
                return cached

        # 2. LLM generation
        try:
            response = await self.llm.generate_explanation(request)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return await self._fallback(request, str(exc))

        # 3. Validate
        validation = await self.validator.validate(response, request.model_dump())

        if validation.is_valid:
            response.status = ExplanationStatus.VALIDATED
            response.validated = True
            response.grounding_score = validation.grounding_score
            await self._store(request, response)
            return response

        # 4. Regenerate
        if self.regenerator and self.config.MAX_REGENERATION_ATTEMPTS > 0:
            regenerated = await self.regenerator.regenerate(request, response, validation)
            if regenerated:
                regenerated.status = ExplanationStatus.VALIDATED
                regenerated.validated = True
                await self._store(request, regenerated)
                return regenerated

        # 5. Fallback
        return await self._fallback(
            request,
            f"Validation failed: {'; '.join(validation.errors[:3])}",
        )

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    async def get_explanation(self, case_id: str) -> Optional[ExplanationResponse]:
        """Get an explanation by case ID (cache → DB)."""
        cached = await self.cache.get(case_id)
        if cached:
            return cached

        if self.db_pool is None:
            return None

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM case_explanations
                    WHERE case_id = $1
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                    case_id,
                )
            if not row:
                return None
            response = self._row_to_response(row)
            await self.cache.set(case_id, response)
            return response
        except Exception:
            logger.exception("DB fetch failed for case %s", case_id)
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _fallback(self, request: ExplanationRequest, reason: str) -> ExplanationResponse:
        response = await self.fallback.generate(request, error_message=reason)
        await self._store(request, response)
        return response

    async def _store(self, request: ExplanationRequest, response: ExplanationResponse) -> None:
        """Persist to cache and DB."""
        await self.cache.set(request.case_id, response)
        if self.db_pool is None:
            return
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO case_explanations
                        (explanation_id, case_id, transaction_id, summary, confidence,
                         explanations, grounding_score, citations_used, total_evidence,
                         total_policies, status, llm_model, llm_provider,
                         generation_time_ms, token_count, validated, validation_attempts,
                         validation_errors, is_fallback, fallback_reason, generated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                    """,
                    response.explanation_id,
                    response.case_id,
                    response.transaction_id,
                    response.summary,
                    response.confidence,
                    json.dumps([pt.model_dump(mode="json") for pt in response.explanations], default=str),
                    response.grounding_score,
                    response.citations_used,
                    response.total_evidence,
                    response.total_policies,
                    response.status.value,
                    response.llm_model,
                    response.llm_provider,
                    response.generation_time_ms,
                    response.token_count,
                    response.validated,
                    response.validation_attempts,
                    json.dumps(response.validation_errors, default=str),
                    response.is_fallback,
                    response.fallback_reason,
                    response.generated_at,
                )
        except Exception:
            logger.exception("Failed to store explanation for case %s", request.case_id)

    def _row_to_response(self, row) -> ExplanationResponse:
        from models.explanation import ExplanationPoint
        exps_raw = row["explanations"]
        if isinstance(exps_raw, str):
            exps_raw = json.loads(exps_raw)
        explanations = [ExplanationPoint(**e) for e in exps_raw]

        errs_raw = row["validation_errors"]
        if isinstance(errs_raw, str):
            errs_raw = json.loads(errs_raw)

        return ExplanationResponse(
            explanation_id=str(row["explanation_id"]),
            case_id=row["case_id"],
            transaction_id=row["transaction_id"],
            summary=row["summary"],
            confidence=row["confidence"],
            explanations=explanations,
            grounding_score=row["grounding_score"],
            citations_used=row["citations_used"],
            total_evidence=row["total_evidence"],
            total_policies=row["total_policies"],
            status=ExplanationStatus(row["status"]),
            llm_model=row["llm_model"],
            llm_provider=row["llm_provider"],
            generation_time_ms=row["generation_time_ms"],
            token_count=row["token_count"],
            validated=row["validated"],
            validation_attempts=row["validation_attempts"],
            validation_errors=errs_raw or [],
            is_fallback=row["is_fallback"],
            fallback_reason=row["fallback_reason"],
            generated_at=row["generated_at"],
        )
