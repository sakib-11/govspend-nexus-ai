"""AI explanation routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from models.explanation import CaseExplanation
from services.explanation_service import ExplanationService

router = APIRouter(prefix="/api/explanation", tags=["explanation"])


def _get_svc(request: Request) -> ExplanationService:
    svc = getattr(request.app.state, "explanation_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Explanation service unavailable")
    return svc


def _get_user(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/case/{case_id}", response_model=CaseExplanation)
async def get_case_explanation(case_id: str, request: Request) -> CaseExplanation:
    """Get or generate AI explanation for a case."""
    user = _get_user(request)
    svc = _get_svc(request)

    # Check cache first
    cached = svc.get_cached(case_id)
    if cached:
        return cached

    # Try to get case data from case service
    case_service = getattr(request.app.state, "case_service", None)
    if case_service:
        detail = case_service.get_case_detail(case_id, user_jurisdictions=getattr(user, "jurisdictions", []))
        if detail:
            explanation = svc.generate(
                case_id,
                risk_score=detail.risk_score,
                signals=detail.signals,
                transaction_id=detail.transaction_id,
            )
            return explanation

    raise HTTPException(status_code=404, detail="Case not found — cannot generate explanation")
