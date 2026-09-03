"""Explanation routes — REST API for explanation generation, retrieval, and validation."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request, status

from models.explanation import ExplanationRequest, ExplanationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/explanation", tags=["explanation"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} unavailable")
    return svc


def _require_auth(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def _require_admin(request: Request) -> Any:
    user = _require_auth(request)
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "super_admin" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/generate")
async def generate_explanation(
    body: ExplanationRequest,
    request: Request,
    force_regenerate: bool = Query(default=False),
) -> Dict[str, Any]:
    """Generate an explanation for a case."""
    _require_auth(request)
    svc = _get_service(request, "explanation_service")

    try:
        result = await svc.generate(body, force_regenerate=force_regenerate)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Explanation generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{case_id}")
async def get_explanation(case_id: str, request: Request) -> Dict[str, Any]:
    """Get the explanation for a case."""
    _require_auth(request)
    svc = _get_service(request, "explanation_service")

    result = await svc.get_explanation(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Explanation not found")
    return result.model_dump(mode="json")


@router.post("/validate")
async def validate_explanation(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Validate an explanation against input data."""
    _require_auth(request)
    svc = _get_service(request, "explanation_service")

    explanation_data = body.get("explanation")
    input_data = body.get("input_data")
    if not explanation_data or not input_data:
        raise HTTPException(status_code=400, detail="Both 'explanation' and 'input_data' are required")

    try:
        exp_obj = ExplanationResponse(**explanation_data)
        result = await svc.validator.validate(exp_obj, input_data)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/cache/{case_id}")
async def clear_cache(case_id: str, request: Request) -> Dict[str, str]:
    """Clear cached explanation (admin only)."""
    _require_admin(request)
    svc = _get_service(request, "explanation_service")
    await svc.cache.delete(case_id)
    return {"status": "cache cleared", "case_id": case_id}


@router.get("/health/detailed")
async def detailed_health(request: Request) -> Dict[str, Any]:
    """Detailed health with LLM and cache status."""
    cache_svc = getattr(request.app.state, "cache_service", None)
    llm_client = getattr(request.app.state, "llm_client", None)

    groq_ok = False
    openai_ok = False
    if llm_client:
        if llm_client.primary:
            groq_ok = await llm_client.primary.health_check()
        if llm_client.fallback:
            openai_ok = await llm_client.fallback.health_check()

    return {
        "status": "healthy",
        "service": "explanation-svc",
        "groq_healthy": groq_ok,
        "openai_healthy": openai_ok,
        "cache": cache_svc.get_stats() if cache_svc else None,
    }
