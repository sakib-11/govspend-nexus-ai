"""Routes for contract splitting detection."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..detectors.contract_splitting import ContractSplittingDetector
from ..utils.logging import get_logger
from ..utils.threshold_utils import ThresholdUtils

router = APIRouter()
logger = get_logger(__name__)

_detector = ContractSplittingDetector()


@router.post("/detect/contract-splitting")
async def detect_contract_splitting(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Detect contract splitting for a transaction.

    Required fields
    ----------------
    * ``vendor_id``, ``vendor_name``
    * ``department_id``, ``department_name``
    * ``amount``: float
    * ``po_date``: ISO date
    * ``po_id``: str

    Optional fields
    ---------------
    * ``category``: str
    * ``review_threshold``: float
    * ``window_days``: int (default 14)
    """
    try:
        result = await _detector.detect(transaction)
        logger.info(
            "Contract splitting detection: signal=%.3f, groups=%d",
            result["signal_value"],
            len(result.get("splitting_groups", [])),
        )
        return result
    except Exception as exc:
        logger.error("Contract splitting detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/detect/contract-splitting/batch")
async def detect_contract_splitting_batch(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run contract splitting detection on a batch of transactions."""
    try:
        return [await _detector.detect(tx) for tx in transactions]
    except Exception as exc:
        logger.error("Batch contract splitting detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/detectors/contract-splitting/stats")
async def get_contract_splitting_stats() -> Dict[str, Any]:
    """Return configuration metadata for the contract-splitting detector."""
    return {
        "detector": "contract_splitting",
        "weight": _detector.get_weight(),
        "required_fields": _detector.get_required_fields(),
        "window_days": _detector.window_days,
        "min_pos_for_splitting": _detector.min_pos_for_splitting,
        "default_threshold": _detector.default_threshold,
    }


@router.get("/threshold/recommend")
async def get_recommended_threshold(
    category: Optional[str] = Query(None, description="Category"),
    department_id: Optional[str] = Query(None, description="Department ID"),
    vendor_risk: Optional[str] = Query(None, description="Vendor risk level"),
) -> Dict[str, Any]:
    """Return the recommended review threshold for given context."""
    threshold = ThresholdUtils.get_review_threshold(
        category=category,
        department_id=department_id,
        vendor_risk=vendor_risk,
    )
    return {
        "recommended_threshold": threshold,
        "category": category,
        "department_id": department_id,
        "vendor_risk": vendor_risk,
        "timestamp": datetime.utcnow().isoformat(),
    }
