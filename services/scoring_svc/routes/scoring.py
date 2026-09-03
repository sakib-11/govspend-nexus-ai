"""Routes for the Scoring Service."""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..models.scoring import (
    BulkScoringRequest,
    RiskTier,
    ScoringRequest,
    ScoringResult,
)
from ..services import ScoringEngine, SignalFetcher
from ..utils.weights_policy import WeightPolicyManager

router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])

# Global instances (set by main.py)
signal_fetcher: SignalFetcher = None
scoring_engine: ScoringEngine = None
weight_manager: WeightPolicyManager = None


@router.post("/score", response_model=ScoringResult)
async def score_transaction(request: ScoringRequest):
    """Score a single transaction."""
    if not signal_fetcher or not scoring_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Fetch signals
        signals = await signal_fetcher.fetch_signals_for_transaction(
            request.transaction_id,
            min_confidence=settings.MIN_CONFIDENCE,
        )

        if not signals:
            raise HTTPException(
                status_code=404,
                detail=f"No signals found for transaction {request.transaction_id}",
            )

        # Score
        result = await scoring_engine.score_transaction(
            signals,
            weights_version=request.weights_version,
            min_confidence=settings.MIN_CONFIDENCE,
            confidence_floor=settings.CONFIDENCE_FLOOR,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/score/bulk", response_model=list[ScoringResult])
async def score_transactions_bulk(request: BulkScoringRequest):
    """Score multiple transactions."""
    if not signal_fetcher or not scoring_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Fetch signals in bulk
        signals_map = await signal_fetcher.fetch_signals_bulk(
            request.transaction_ids,
            min_confidence=settings.MIN_CONFIDENCE,
        )

        # Score
        results = await scoring_engine.score_transactions_bulk(
            signals_map,
            weights_version=request.weights_version,
            min_confidence=settings.MIN_CONFIDENCE,
            confidence_floor=settings.CONFIDENCE_FLOOR,
        )

        return list(results.values())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tiers", response_model=list[str])
async def get_tiers():
    """Get available risk tiers."""
    return [tier.value for tier in RiskTier]


@router.get("/weights/versions")
async def get_weights_versions():
    """Get available weight policy versions."""
    if not weight_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return {
        "versions": weight_manager.list_versions(),
        "current": weight_manager.get_weights().version,
    }


class WeightsCreateRequest(BaseModel):
    """Request to create new weight version."""
    weights: dict
    description: str | None = ""


@router.post("/weights/create")
async def create_weights_version(request: WeightsCreateRequest):
    """Create a new weight version."""
    if not weight_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        config = weight_manager.create_version(
            request.weights,
            request.description,
        )
        return {
            "version": config.version,
            "weights": config.weights,
            "description": config.description,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/transaction/{transaction_id}/status")
async def get_transaction_status(transaction_id: str):
    """Get scoring status for a transaction."""
    if not signal_fetcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    signals = await signal_fetcher.fetch_signals_for_transaction(
        transaction_id,
        min_confidence=0.0,  # Get all signals
    )

    return {
        "transaction_id": transaction_id,
        "signals_found": len(signals),
        "has_signals": len(signals) > 0,
        "detectors": list({s.detector_type for s in signals}),
    }