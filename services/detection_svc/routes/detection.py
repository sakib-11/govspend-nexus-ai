"""Detection routes for the Detection Service."""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..detectors.price_deviation import PriceDeviationDetector
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Initialize detector
price_deviation_detector = PriceDeviationDetector()


@router.post("/detect/price-deviation")
async def detect_price_deviation(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect price deviation for a transaction.

    Required fields:
    - category: str
    - region: str
    - quantity: float
    - unit_price: float
    - total_amount: float
    - transaction_date: date (ISO format)
    """
    try:
        result = await price_deviation_detector.detect(transaction)
        return result
    except Exception as e:
        logger.error(f"Price deviation detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect/price-deviation/batch")
async def detect_price_deviation_batch(
    transactions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect price deviations for multiple transactions."""
    try:
        results = []
        for transaction in transactions:
            result = await price_deviation_detector.detect(transaction)
            results.append(result)
        return results
    except Exception as e:
        logger.error(f"Batch detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detectors/price-deviation/stats")
async def get_price_deviation_stats() -> Dict[str, Any]:
    """Get statistics about price deviation detector."""
    return {
        "detector": "price_deviation",
        "weight": price_deviation_detector.get_weight(),
        "required_fields": price_deviation_detector.get_required_fields(),
        "lookback_days": price_deviation_detector.lookback_days,
        "min_samples": price_deviation_detector.min_samples
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "detection-svc",
        "timestamp": datetime.utcnow().isoformat()
    }