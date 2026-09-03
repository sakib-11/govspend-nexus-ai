"""Evidence routes — REST API for masked evidence CRUD and queries."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from models.evidence import (
    EvidenceQuery,
    MaskedCase,
    MaskedEvidenceRecord,
    MaskingRequest,
    MaskingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


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


def _get_user_jurisdiction(user: Any) -> Optional[str]:
    jurisdictions = getattr(user, "jurisdictions", [])
    if jurisdictions:
        return jurisdictions[0]
    return getattr(user, "jurisdiction_id", None)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("/case/{case_id}", response_model=MaskedCase)
async def get_masked_case(case_id: UUID, request: Request) -> MaskedCase:
    """Get a masked case by ID, enforcing jurisdiction."""
    user = _require_auth(request)
    evidence_svc = _get_service(request, "evidence_service")

    jurisdiction_id = _get_user_jurisdiction(user)
    case = await evidence_svc.get_masked_case(case_id, jurisdiction_id=jurisdiction_id)

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found or access denied",
        )
    return case


@router.get("/{evidence_id}", response_model=MaskedEvidenceRecord)
async def get_masked_evidence(evidence_id: UUID, request: Request) -> MaskedEvidenceRecord:
    """Get a masked evidence record by ID."""
    _require_auth(request)
    evidence_svc = _get_service(request, "evidence_service")

    record = await evidence_svc.get_masked_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )
    return record


@router.post("/mask", response_model=MaskingResponse)
async def mask_data(body: MaskingRequest, request: Request) -> MaskingResponse:
    """Mask sensitive data fields in the request payload."""
    _require_auth(request)
    masking_svc = _get_service(request, "masking_service")

    masked_data, tokens = await masking_svc.mask_data(
        raw_data=body.raw_data,
        fields_to_mask=body.fields_to_mask,
        entity_type=body.entity_type,
        preserve_fields=body.preserve_fields,
    )

    return MaskingResponse(
        masked_data=masked_data,
        tokens=tokens,
        field_count=len(masked_data),
        token_count=len(tokens),
    )


@router.get("/tokens/{entity_type}")
async def get_tokens(entity_type: str, request: Request) -> Dict[str, Any]:
    """List all tokens for an entity type (admin only)."""
    _require_admin(request)
    evidence_svc = _get_service(request, "evidence_service")

    tokens = await evidence_svc.tokenization.get_tokens_for_entity(entity_type)
    return {"entity_type": entity_type, "tokens": tokens, "count": len(tokens)}


@router.post("/verify-token")
async def verify_token(
    token: str = Query(..., description="Token to verify"),
    request: Request = None,
) -> Dict[str, Any]:
    """Verify whether a token exists in the mapping table."""
    _require_auth(request)
    evidence_svc = _get_service(request, "evidence_service")

    exists = await evidence_svc.tokenization.verify_token(token)
    return {"token": token, "exists": exists}


@router.get("/query", response_model=List[Dict[str, Any]])
async def query_evidence(
    request: Request,
    case_id: Optional[UUID] = Query(default=None),
    evidence_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> List[Dict[str, Any]]:
    """Query masked evidence with optional filters."""
    _require_auth(request)
    evidence_svc = _get_service(request, "evidence_service")

    query = EvidenceQuery(
        case_id=case_id,
        evidence_type=evidence_type,
        limit=limit,
        offset=offset,
    )
    return await evidence_svc.query_evidence(query)


# ------------------------------------------------------------------
# Store endpoints (for ingesting raw data)
# ------------------------------------------------------------------

class StoreTransactionRequest(BaseModel):
    transaction_id: UUID
    raw_data: Dict[str, Any]


class StoreCaseRequest(BaseModel):
    case_id: UUID
    transaction_id: UUID
    case_data: Dict[str, Any]
    risk_score: float = 0.0
    tier: str = "unknown"
    jurisdiction_id: str = "unknown"


class StoreEvidenceRequest(BaseModel):
    case_id: UUID
    evidence_type: str
    evidence_data: Dict[str, Any]


@router.post("/store/transaction")
async def store_transaction(body: StoreTransactionRequest, request: Request) -> Dict[str, Any]:
    """Mask and store a transaction (admin only)."""
    _require_admin(request)
    evidence_svc = _get_service(request, "evidence_service")

    result = await evidence_svc.store_masked_transaction(
        transaction_id=body.transaction_id,
        raw_data=body.raw_data,
    )
    return result.model_dump(mode="json")


@router.post("/store/case")
async def store_case(body: StoreCaseRequest, request: Request) -> Dict[str, Any]:
    """Mask and store a case (admin only)."""
    _require_admin(request)
    evidence_svc = _get_service(request, "evidence_service")

    result = await evidence_svc.store_masked_case(
        case_id=body.case_id,
        transaction_id=body.transaction_id,
        case_data=body.case_data,
        risk_score=body.risk_score,
        tier=body.tier,
        jurisdiction_id=body.jurisdiction_id,
    )
    return result.model_dump(mode="json")


@router.post("/store/evidence")
async def store_evidence(body: StoreEvidenceRequest, request: Request) -> Dict[str, Any]:
    """Mask and store evidence (admin only)."""
    _require_admin(request)
    evidence_svc = _get_service(request, "evidence_service")

    result = await evidence_svc.store_masked_evidence(
        case_id=body.case_id,
        evidence_type=body.evidence_type,
        evidence_data=body.evidence_data,
    )
    return result.model_dump(mode="json")
