"""Routes for approval velocity detection."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..detectors.approval_velocity import ApprovalVelocityDetector
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_detector = ApprovalVelocityDetector()


@router.post("/detect/approval-velocity")
async def detect_approval_velocity(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Detect approval velocity anomalies.

    Required fields
    ----------------
    * ``department_id``: str
    * ``category``: str
    * ``submission_date``: ISO date
    * ``approval_date``: ISO date

    Optional fields
    ---------------
    * ``vendor_id``, ``amount``, ``transaction_date``
    * ``is_expedited``: bool
    * ``is_emergency``: bool
    * ``approver_id``: str
    """
    try:
        result = await _detector.detect(transaction)
        logger.info(
            "Approval velocity detection: signal=%.3f, severity=%s",
            result["signal_value"],
            result["severity"],
        )
        return result
    except Exception as exc:
        logger.error("Approval velocity detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/detect/approval-velocity/batch")
async def detect_approval_velocity_batch(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run approval velocity detection on a batch of transactions."""
    try:
        return [await _detector.detect(tx) for tx in transactions]
    except Exception as exc:
        logger.error("Batch velocity detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/detectors/approval-velocity/stats")
async def get_approval_velocity_stats() -> Dict[str, Any]:
    """Return configuration metadata for the velocity detector."""
    return {
        "detector": "approval_velocity",
        "weight": _detector.get_weight(),
        "required_fields": _detector.get_required_fields(),
        "fast_threshold": _detector.fast_threshold,
        "emergency_threshold": _detector.emergency_threshold,
        "min_sample_size": _detector.min_sample_size,
        "lookback_days": _detector.lookback_days,
    }


@router.get("/velocity/historical/{category}/{department_id}")
async def get_historical_velocity_stats(
    category: str, department_id: str
) -> Dict[str, Any]:
    """Retrieve cached historical velocity statistics."""
    try:
        stats = await _detector.velocity_cache.get_stats(category, department_id)
        if stats:
            return stats.model_dump(mode="json")
        return {
            "category": category,
            "department_id": department_id,
            "status": "No data available",
            "message": f"No historical statistics found for {category}/{department_id}",
        }
    except Exception as exc:
        logger.error("Failed to get historical stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
