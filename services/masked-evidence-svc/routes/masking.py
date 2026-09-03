"""Masking routes — dedicated endpoints for masking operations and token management."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from models.masking import EntityType, MaskingLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/masking", tags=["masking"])


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


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------

class BatchMaskRequest(BaseModel):
    items: List[Dict[str, Any]]
    fields_to_mask: List[str]
    entity_type: str = "generic"
    preserve_fields: List[str] = []


class BatchMaskResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_items: int
    total_tokens: int


class MaskingLevelRequest(BaseModel):
    data: Dict[str, Any]
    user_roles: List[str]
    entity_type: str = "generic"


class MaskingLevelResponse(BaseModel):
    level: str
    masked_data: Dict[str, Any]
    tokens: Dict[str, str]


class PiiDetectionRequest(BaseModel):
    data: Dict[str, Any]


class PiiDetectionResponse(BaseModel):
    fields_with_pii: List[str]
    total_fields: int


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/batch", response_model=BatchMaskResponse)
async def batch_mask(body: BatchMaskRequest, request: Request) -> BatchMaskResponse:
    """Mask multiple data items in a single request."""
    _require_auth(request)
    masking_svc = _get_service(request, "masking_service")

    results = []
    total_tokens = 0

    for item in body.items:
        masked_data, tokens = await masking_svc.mask_data(
            raw_data=item,
            fields_to_mask=body.fields_to_mask,
            entity_type=body.entity_type,
            preserve_fields=body.preserve_fields,
        )
        results.append(masked_data)
        total_tokens += len(tokens)

    return BatchMaskResponse(
        results=results,
        total_items=len(results),
        total_tokens=total_tokens,
    )


@router.post("/level", response_model=MaskingLevelResponse)
async def mask_for_level(body: MaskingLevelRequest, request: Request) -> MaskingLevelResponse:
    """Apply masking appropriate for the user's role level."""
    _require_auth(request)
    masking_svc = _get_service(request, "masking_service")

    level = masking_svc.get_masking_level(body.user_roles)
    masked_data, tokens = await masking_svc.mask_for_level(
        body.data, level, entity_type=body.entity_type,
    )

    return MaskingLevelResponse(
        level=level.value,
        masked_data=masked_data,
        tokens=tokens,
    )


@router.post("/detect-pii", response_model=PiiDetectionResponse)
async def detect_pii(body: PiiDetectionRequest, request: Request) -> PiiDetectionResponse:
    """Detect which fields in the data contain PII patterns."""
    _require_auth(request)
    from utils.validation_utils import field_looks_like_pii

    pii_fields = [k for k in body.data if field_looks_like_pii(k)]

    return PiiDetectionResponse(
        fields_with_pii=pii_fields,
        total_fields=len(body.data),
    )


@router.get("/entity-types")
async def get_entity_types(request: Request) -> Dict[str, Any]:
    """List supported entity types."""
    _require_auth(request)
    return {
        "entity_types": [t.value for t in EntityType],
        "count": len(EntityType),
    }


@router.get("/levels")
async def get_masking_levels(request: Request) -> Dict[str, Any]:
    """List masking levels and their descriptions."""
    _require_auth(request)
    return {
        "levels": [
            {"level": "full", "description": "All data visible — no masking"},
            {"level": "partial", "description": "PII fields masked, other data visible"},
            {"level": "minimal", "description": "Only aggregate/safe fields visible"},
        ]
    }
