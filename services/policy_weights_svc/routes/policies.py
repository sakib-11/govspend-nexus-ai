"""FastAPI routes for policy weight management."""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Query

from ..models.policy import (
    WeightPolicy,
    WeightPolicyQuery,
    CalibrationRequest,
    DetectorWeights,
    PolicyStatus,
    PolicyCreateRequest,
    PolicyUpdateRequest,
)
from ..services.policy_manager import PolicyManager
from ..services.calibration_service import CalibrationService
from ..services.audit_service import AuditService
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/policies", tags=["weight-policies"])

# Globals set by main.py lifespan
_policy_manager: Optional[PolicyManager] = None
_calibration_service: Optional[CalibrationService] = None
_audit_service: Optional[AuditService] = None


def _get_pm() -> PolicyManager:
    if not _policy_manager:
        raise HTTPException(status_code=503, detail="Policy manager not initialised")
    return _policy_manager


def _get_cs() -> CalibrationService:
    if not _calibration_service:
        raise HTTPException(status_code=503, detail="Calibration service not initialised")
    return _calibration_service


def _get_audit() -> AuditService:
    if not _audit_service:
        raise HTTPException(status_code=503, detail="Audit service not initialised")
    return _audit_service


# ── CRUD ──────────────────────────────────────────────────────────


@router.post("/create", response_model=WeightPolicy, status_code=201)
async def create_policy(request: PolicyCreateRequest, http: Request):
    """Create a new weight policy in DRAFT status."""
    pm = _get_pm()
    created_by = http.headers.get("X-User-Id", request.created_by)

    try:
        policy = await pm.create_policy(
            name=request.name,
            weights=request.weights,
            created_by=created_by,
            description=request.description,
            tags=request.tags,
            metadata=request.metadata,
        )
        return policy
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/active", response_model=WeightPolicy)
async def get_active_policy():
    """Get the currently active weight policy."""
    pm = _get_pm()
    policy = await pm.get_active_policy()
    if not policy:
        raise HTTPException(status_code=404, detail="No active policy found")
    return policy


@router.get("/{policy_id}", response_model=WeightPolicy)
async def get_policy(policy_id: str):
    """Get a policy by ID."""
    pm = _get_pm()
    policy = await pm.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.get("/version/{version}", response_model=WeightPolicy)
async def get_policy_by_version(version: str):
    """Get a policy by version string."""
    pm = _get_pm()
    policy = await pm.get_policy_by_version(version)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return policy


@router.post("/query")
async def query_policies(query: WeightPolicyQuery):
    """Query policies with filters and pagination."""
    pm = _get_pm()
    policies, total = await pm.get_all_policies(query)
    return {
        "total": total,
        "limit": query.limit,
        "offset": query.offset,
        "policies": [p.model_dump(mode="json") for p in policies],
    }


@router.put("/{policy_id}", response_model=WeightPolicy)
async def update_policy(policy_id: str, update: PolicyUpdateRequest):
    """Update a DRAFT policy's weights, name, or description."""
    pm = _get_pm()
    try:
        return await pm.update_policy(policy_id, update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Activation / deactivation ─────────────────────────────────────


@router.post("/{policy_id}/activate", response_model=WeightPolicy)
async def activate_policy(policy_id: str, http: Request):
    """Activate a policy (deactivates the current one)."""
    pm = _get_pm()
    activated_by = http.headers.get("X-User-Id", "system")
    try:
        return await pm.activate_policy(policy_id, activated_by=activated_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{policy_id}/deactivate", response_model=WeightPolicy)
async def deactivate_policy(
    policy_id: str,
    http: Request,
    reason: Optional[str] = Query(None, description="Deactivation reason"),
):
    """Deactivate a policy."""
    pm = _get_pm()
    deactivated_by = http.headers.get("X-User-Id", "system")
    try:
        return await pm.deactivate_policy(
            policy_id, deactivated_by=deactivated_by, reason=reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Calibration ───────────────────────────────────────────────────


@router.post("/calibrate", response_model=WeightPolicy, status_code=201)
async def calibrate_weights(request: CalibrationRequest):
    """Calibrate weights — creates a new policy version."""
    cs = _get_cs()
    try:
        return await cs.calibrate_weights(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{policy_id}/evaluate")
async def evaluate_calibration(
    policy_id: str,
    evaluation_data: Dict[str, Any],
    http: Request,
):
    """Record evaluation results for a calibrated policy."""
    cs = _get_cs()
    evaluated_by = http.headers.get("X-User-Id", "system")
    try:
        return await cs.evaluate_calibration(
            policy_id, evaluation_data, evaluated_by=evaluated_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Comparison ────────────────────────────────────────────────────


@router.get("/compare/{version_a}/{version_b}")
async def compare_versions(version_a: str, version_b: str):
    """Compare two policy versions."""
    pm = _get_pm()
    try:
        return await pm.compare_versions(version_a, version_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── History / audit ───────────────────────────────────────────────


@router.get("/history/{policy_id}")
async def get_policy_history(
    policy_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get audit log history for a policy."""
    audit = _get_audit()
    logs = await audit.get_audit_logs(policy_id=policy_id, limit=limit, offset=offset)
    return {
        "policy_id": policy_id,
        "total": len(logs),
        "history": [log.model_dump(mode="json") for log in logs],
    }


# ── Archive ───────────────────────────────────────────────────────


@router.post("/archive-old")
async def archive_old_policies(
    days: int = Query(default=365, ge=30, le=3650),
):
    """Archive inactive/superseded policies older than N days."""
    pm = _get_pm()
    count = await pm.archive_old_policies(days)
    return {
        "status": "archived",
        "count": count,
        "message": f"Archived {count} policies older than {days} days",
    }


# ── Stats ─────────────────────────────────────────────────────────


@router.get("/stats/summary")
async def get_policy_stats():
    """Get aggregate policy statistics."""
    pm = _get_pm()
    return await pm.get_stats()


# ── Initialization hook ──────────────────────────────────────────


def init_routes(
    policy_manager: PolicyManager,
    calibration_service: CalibrationService,
    audit_service: AuditService,
):
    """Called by main.py to inject dependencies."""
    global _policy_manager, _calibration_service, _audit_service
    _policy_manager = policy_manager
    _calibration_service = calibration_service
    _audit_service = audit_service
