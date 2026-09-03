"""Routes for duplicate / fuzzy detection."""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..detectors.duplicate_fuzzy import DuplicateFuzzyDetector
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Module-level singleton (mirrors the pattern used for price-deviation)
_duplicate_detector = DuplicateFuzzyDetector()


@router.post("/detect/duplicate")
async def detect_duplicate(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Detect duplicate or fuzzy-duplicate transactions.

    Required fields
    ----------------
    * ``vendor_token`` (or ``vendor_name``)
    * ``amount``: float
    * ``transaction_date``: ISO date
    * ``invoice_doc_hash``: str

    Optional fields
    ---------------
    * ``document_text``: full OCR / text for fuzzy matching
    * ``document_number``: invoice / PO number
    * ``line_items``: list of dicts
    """
    try:
        result = await _duplicate_detector.detect(transaction)

        logger.info(
            "Duplicate detection: signal=%.3f, match_type=%s, duplicates=%s",
            result["signal_value"],
            result["match_type"],
            result["duplicate_count"],
        )
        return result
    except Exception as exc:
        logger.error("Duplicate detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/detect/duplicate/batch")
async def detect_duplicate_batch(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run duplicate detection on a batch of transactions."""
    try:
        results: List[Dict[str, Any]] = []
        for tx in transactions:
            result = await _duplicate_detector.detect(tx)
            results.append(result)
        return results
    except Exception as exc:
        logger.error("Batch duplicate detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/detectors/duplicate/stats")
async def get_duplicate_stats() -> Dict[str, Any]:
    """Return configuration and metadata for the duplicate detector."""
    return {
        "detector": "duplicate_fuzzy",
        "weight": _duplicate_detector.get_weight(),
        "required_fields": _duplicate_detector.get_required_fields(),
        "amount_tolerance": _duplicate_detector.amount_tolerance,
        "date_window_days": _duplicate_detector.date_window_days,
        "similarity_threshold": _duplicate_detector.similarity_threshold,
    }
