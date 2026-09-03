"""Versioned portal API.  Authorisation is centralised in the request context."""
from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from services.nexus_service import NexusService

router = APIRouter(prefix="/api/v1", tags=["portal-v1"])

class Principal(BaseModel):
    subject: str
    role: Literal["auditor", "institution"]
    jurisdictions: set[str] = Field(min_length=1)
    institution_id: str | None = None

def principal(request: Request) -> Principal:
    """Temporary development identity adapter.

    The deployment gateway must set these headers only after OIDC/JWT MFA
    validation.  They are intentionally rejected when the production flag is set.
    """
    if request.app.state.production: raise HTTPException(401, "Gateway identity required")
    role = request.headers.get("X-GovSpend-Role")
    subject = request.headers.get("X-GovSpend-Subject", "demo-user")
    jurisdictions = set(filter(None, request.headers.get("X-GovSpend-Jurisdictions", "district:nashik").split(",")))
    if role not in {"auditor", "institution"}: raise HTTPException(401, "Authenticated portal role required")
    return Principal(subject=subject, role=role, jurisdictions=jurisdictions, institution_id=request.headers.get("X-GovSpend-Institution"))

def service(request: Request) -> NexusService: return request.app.state.nexus_service
def auditor(p: Principal = Depends(principal)) -> Principal:
    if p.role != "auditor": raise HTTPException(403, "Auditor role required")
    return p
def institution(institution_id: str, p: Principal = Depends(principal)) -> Principal:
    if p.role != "institution" or p.institution_id != institution_id: raise HTTPException(403, "Institution scope required")
    return p

class Decision(BaseModel): action: Literal["approve", "reject", "escalate"]; comment: str = Field(min_length=3, max_length=2000)
class UnmaskRequest(BaseModel): field: str = Field(min_length=2, max_length=64); reason: str = Field(min_length=10, max_length=1000)
class UnmaskResponse(BaseModel): approve: bool; reason: str = Field(min_length=3, max_length=1000)
class InvoiceInput(BaseModel): jurisdiction: str; tender_reference: str; category: str; amount: float = Field(gt=0); line_items: list[dict]; gst: str | None = None; pan: str | None = None; upi: str | None = None; bank_account: str | None = None

@router.get("/public/metrics/summary")
def public_metrics(s: NexusService = Depends(service)): return s.public_metrics()
@router.get("/public/departments/spend-health")
def spend_health(): return {"data": [{"region": "State aggregate A", "band": "healthy", "count": 18}, {"region": "State aggregate B", "band": "needs_attention", "count": 8}, {"region": "State aggregate C", "band": "under_review", "count": 3}]}
@router.get("/public/funnel")
def public_funnel(): return {"flagged": 1248, "under_review": 386, "resolved": 218}

@router.get("/cases")
def list_cases(risk_band: str | None = None, department: str | None = None, p: Principal = Depends(auditor), s: NexusService = Depends(service)): return {"cases": s.list_cases(p.jurisdictions, risk_band, department)}
@router.get("/cases/{case_id}")
def get_case(case_id: str, p: Principal = Depends(auditor), s: NexusService = Depends(service)):
    try: return s.allowed_case(case_id, p.jurisdictions)
    except KeyError: raise HTTPException(404, "Case not found")
@router.get("/cases/{case_id}/audit-trail")
def audit_trail(case_id: str, p: Principal = Depends(auditor), s: NexusService = Depends(service)):
    try: s.allowed_case(case_id, p.jurisdictions)
    except KeyError: raise HTTPException(404, "Case not found")
    return {"entries": s.audit.get(case_id, [])}
@router.post("/cases/{case_id}/decision")
def decision(case_id: str, body: Decision, p: Principal = Depends(auditor), s: NexusService = Depends(service)):
    try: return s.decide(case_id, p.jurisdictions, p.subject, body.action, body.comment)
    except KeyError: raise HTTPException(404, "Case not found")
@router.post("/cases/{case_id}/unmask-request")
def unmask(case_id: str, body: UnmaskRequest, p: Principal = Depends(auditor), s: NexusService = Depends(service)):
    try: return s.request_unmask(case_id, p.jurisdictions, p.subject, body.field, body.reason)
    except KeyError: raise HTTPException(404, "Case not found")
@router.get("/cases/{case_id}/audit-trail/verify")
def verify(case_id: str, p: Principal = Depends(auditor), s: NexusService = Depends(service)):
    try: return s.verify_audit(case_id, p.jurisdictions)
    except KeyError: raise HTTPException(404, "Case not found")

@router.post("/institutions/{institution_id}/invoices")
def submit_invoice(institution_id: str, body: InvoiceInput, p: Principal = Depends(principal), s: NexusService = Depends(service)):
    institution(institution_id, p)
    try: return s.ingest_invoice(institution_id, p.jurisdictions, body.model_dump())
    except PermissionError: raise HTTPException(403, "Institution is outside caller scope")
@router.get("/institutions/{institution_id}/cases")
def institution_cases(institution_id: str, p: Principal = Depends(principal), s: NexusService = Depends(service)):
    institution(institution_id, p)
    return {"cases": [c for c in s.list_cases(p.jurisdictions) if c["institution_id"] == institution_id]}
@router.get("/institutions/{institution_id}/unmask-requests")
def institution_unmasks(institution_id: str, p: Principal = Depends(principal), s: NexusService = Depends(service)):
    institution(institution_id, p)
    return {"requests": [r for r in s.unmask_requests.values() if r["institution_id"] == institution_id]}
@router.post("/institutions/{institution_id}/unmask-requests/{request_id}/respond")
def respond_unmask(institution_id: str, request_id: str, body: UnmaskResponse, p: Principal = Depends(principal), s: NexusService = Depends(service)):
    institution(institution_id, p)
    try: return s.respond_unmask(request_id, institution_id, p.subject, body.approve, body.reason)
    except KeyError: raise HTTPException(404, "Request not found")
    except PermissionError: raise HTTPException(403, "Maker-checker violation")
