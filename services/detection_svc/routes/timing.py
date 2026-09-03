"""Routes for timing anomaly detection."""

from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from ..detectors.timing_anomaly import TimingAnomalyDetector
from ..services.fiscal_service import FiscalService
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_timing_detector = TimingAnomalyDetector()
_fiscal_service = FiscalService()


@router.post("/detect/timing-anomaly")
async def detect_timing_anomaly(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Detect timing anomalies in transaction approval.

    Required fields
    ----------------
    * ``department_id``: str
    * ``vendor_id``: str
    * ``amount``: float
    * ``transaction_date``: ISO date
    * ``submission_date``: ISO date
    * ``approval_date``: ISO date
    """
    try:
        result = await _timing_detector.detect(transaction)
        logger.info(
            "Timing anomaly detection: signal=%.3f, z_score=%.2f",
            result["signal_value"],
            result["z_score"],
        )
        return result
    except Exception as exc:
        logger.error("Timing anomaly detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/fiscal/context")
async def get_fiscal_context(
    date_obj: date = Query(..., description="Date to analyze"),
    department_type: str = Query("STATE", description="Department type"),
) -> Dict[str, Any]:
    """Return fiscal-year context for a given date."""
    try:
        return await _fiscal_service.get_fiscal_context(date_obj, department_type)
    except Exception as exc:
        logger.error("Fiscal context fetch failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/detectors/timing/stats")
async def get_timing_stats() -> Dict[str, Any]:
    """Return configuration metadata for the timing detector."""
    return {
        "detector": "timing_anomaly",
        "weight": _timing_detector.get_weight(),
        "required_fields": _timing_detector.get_required_fields(),
        "z_score_threshold": _timing_detector.z_score_threshold,
        "fiscal_end_window": _timing_detector.fiscal_end_window,
        "min_sample_size": _timing_detector.min_sample_size,
    }
