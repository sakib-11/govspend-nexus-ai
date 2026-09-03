"""Routes for Detection Core Engine."""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional

from ..engine.orchestrator import DetectionOrchestrator
from ..models.signals import DetectionType, SignalStatus
from ..config import settings
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Global orchestrator instance (set in main.py)
orchestrator: DetectionOrchestrator = None

@router.post("/process")
async def process_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single transaction through all detectors
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        result = await orchestrator.process_transaction(transaction)
        return result
    except Exception as e:
        logger.error(f"Failed to process transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/batch")
async def process_transactions_batch(
    transactions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Process a batch of transactions"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        results = await orchestrator.process_batch(transactions)
        return results
    except Exception as e:
        logger.error(f"Batch processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/detectors")
async def list_detectors():
    """List all registered detectors"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    return orchestrator.registry.get_all_detectors_metadata()

@router.get("/detectors/{detector_id}")
async def get_detector_info(detector_id: str):
    """Get detector information"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    metadata = orchestrator.registry.get_detector_metadata(detector_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Detector {detector_id} not found")

    return metadata

@router.get("/status")
async def get_engine_status():
    """Get engine status"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    return {
        "status": "running",
        "max_concurrent_transactions": orchestrator.max_concurrent,
        "active_transactions": len(orchestrator._active_transactions),
        "detectors_registered": len(orchestrator.registry.get_all_detectors())
    }