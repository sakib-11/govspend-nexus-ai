"""Admin dashboard routes — overview panels for policy management."""

from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException

from ..services.policy_manager import PolicyManager
from ..services.calibration_service import CalibrationService
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_policy_manager: Optional[PolicyManager] = None
_calibration_service: Optional[CalibrationService] = None


def init_admin_routes(
    policy_manager: PolicyManager,
    calibration_service: CalibrationService,
):
    global _policy_manager, _calibration_service
    _policy_manager = policy_manager
    _calibration_service = calibration_service


@router.get("/dashboard")
async def admin_dashboard():
    """Full admin dashboard with policy overview."""
    pm = _policy_manager
    if not pm:
        raise HTTPException(status_code=503, detail="Service not initialised")

    policies, total = await pm.get_all_policies()
    active = await pm.get_active_policy()

    # Status counts
    by_status: Dict[str, int] = {}
    for p in policies:
        by_status[p.status.value] = by_status.get(p.status.value, 0) + 1

    # Weight trends (last 10 versions)
    weight_trends = []
    perf_trends = []
    for p in policies[:10]:
        trend = p.weights.as_dict()
        trend["version"] = p.version
        trend["status"] = p.status.value
        weight_trends.append(trend)

        if p.performance_metrics:
            perf = p.performance_metrics.copy()
            perf["version"] = p.version
            perf_trends.append(perf)

    return {
        "summary": {
            "total_policies": total,
            "active_version": active.version if active else None,
            "by_status": by_status,
            "latest_version": policies[0].version if policies else "v0.0",
        },
        "active_weights": active.weights.as_dict() if active else None,
        "weight_trends": weight_trends,
        "performance_trends": perf_trends,
    }


@router.get("/calibration/panel")
async def calibration_panel():
    """Calibration management panel with available options."""
    cs = _calibration_service
    if not cs:
        raise HTTPException(status_code=503, detail="Service not initialised")

    history = await cs.get_calibration_history(limit=20)

    return {
        "calibration_history": history,
        "available_types": [t.value for t in __import__("..models.policy", fromlist=["CalibrationType"]).CalibrationType],
        "available_reasons": [r.value for r in __import__("..models.policy", fromlist=["WeightChangeReason"]).WeightChangeReason],
    }


@router.get("/version/{policy_id}")
async def version_detail(policy_id: str):
    """Detailed version info for a specific policy."""
    pm = _policy_manager
    if not pm:
        raise HTTPException(status_code=503, detail="Service not initialised")

    policy = await pm.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Get related versions (same name or lineage)
    all_policies, _ = await pm.get_all_policies()
    related = [
        {
            "version": p.version,
            "status": p.status.value,
            "created_at": p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else str(p.created_at),
            "weights": p.weights.as_dict(),
        }
        for p in all_policies
        if p.name == policy.name or p.previous_version == policy.version
    ]

    return {
        "policy": {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "name": policy.name,
            "status": policy.status.value,
            "weights": policy.weights.as_dict(),
            "weights_sum": policy.weights_sum,
            "calibration_type": policy.calibration_type.value if policy.calibration_type else None,
            "performance_metrics": policy.performance_metrics,
        },
        "related_versions": related,
    }
