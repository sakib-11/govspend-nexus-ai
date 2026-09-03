"""Evidence routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request

from models.evidence import EvidenceDetail, EvidenceItem
from services.evidence_service import EvidenceService

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def _get_svc(request: Request) -> EvidenceService:
    svc = getattr(request.app.state, "evidence_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Evidence service unavailable")
    return svc


def _get_user(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/case/{case_id}")
async def get_case_evidence(case_id: str, request: Request) -> dict:
    """Get evidence items for a case."""
    user = _get_user(request)
    svc = _get_svc(request)
    evidence = svc.get_evidence_for_case(
        case_id,
        user_jurisdictions=getattr(user, "jurisdictions", []),
    )
    return {"case_id": case_id, "evidence": [e.model_dump(mode="json") for e in evidence], "total": len(evidence)}


@router.get("/{evidence_id}", response_model=EvidenceDetail)
async def get_evidence_detail(evidence_id: str, request: Request) -> EvidenceDetail:
    """Get detailed evidence by ID."""
    user = _get_user(request)
    svc = _get_svc(request)
    detail = svc.get_evidence_detail(
        evidence_id,
        user_jurisdictions=getattr(user, "jurisdictions", []),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return detail
