"""FastAPI routes for evidence bundle management."""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends

from ..models.evidence_bundle import (
    EvidenceBundle,
    BundleReference,
    BundleQueryRequest,
    BundleAssembleRequest,
    BundleBulkAssembleRequest,
    BundleStatus,
)
from ..services.bundle_assembler import BundleAssembler
from ..services.bundle_storage import BundleStorage
from ..utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["evidence-bundles"])

# Globals set by main.py lifespan
_bundle_assembler: Optional[BundleAssembler] = None
_bundle_storage: Optional[BundleStorage] = None


def _get_assembler() -> BundleAssembler:
    if not _bundle_assembler:
        raise HTTPException(status_code=503, detail="Bundle assembler not initialised")
    return _bundle_assembler


def _get_storage() -> BundleStorage:
    if not _bundle_storage:
        raise HTTPException(status_code=503, detail="Bundle storage not initialised")
    return _bundle_storage


# ── Assembly endpoints ────────────────────────────────────────────


@router.post("/assemble", response_model=EvidenceBundle, status_code=201)
async def assemble_bundle(request: BundleAssembleRequest):
    """Explicitly assemble an evidence bundle for one transaction."""
    assembler = _get_assembler()

    try:
        bundle = await assembler.assemble_bundle(
            transaction_id=request.transaction_id,
            scoring_result=request.scoring_result,
            include_benchmarks=request.include_benchmarks,
            bundle_format=request.bundle_format,
        )
        return bundle
    except Exception as e:
        logger.error("Assembly failed for %s: %s", request.transaction_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assemble/bulk", status_code=201)
async def assemble_bundles_bulk(request: BundleBulkAssembleRequest):
    """Assemble bundles for multiple transactions."""
    assembler = _get_assembler()

    scoring_results = {
        item.transaction_id: item.scoring_result for item in request.items
    }

    try:
        bundles = await assembler.assemble_bundles_bulk(scoring_results)
        return {
            "total": len(bundles),
            "assembled": sum(
                1 for b in bundles.values() if b.status != BundleStatus.ERROR
            ),
            "errors": sum(
                1 for b in bundles.values() if b.status == BundleStatus.ERROR
            ),
            "bundles": {
                tx_id: b.to_dict(compact=True) for tx_id, b in bundles.items()
            },
        }
    except Exception as e:
        logger.error("Bulk assembly failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Retrieval endpoints ───────────────────────────────────────────


@router.get("/{bundle_id}", response_model=EvidenceBundle)
async def get_bundle(bundle_id: str):
    """Get a complete evidence bundle by ID."""
    storage = _get_storage()

    bundle = await storage.retrieve_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    return bundle


@router.get("/transaction/{transaction_id}", response_model=EvidenceBundle)
async def get_bundle_by_transaction(transaction_id: str):
    """Get the latest bundle for a transaction."""
    storage = _get_storage()

    bundle = await storage.retrieve_by_transaction(transaction_id)
    if not bundle:
        raise HTTPException(
            status_code=404,
            detail=f"No bundle found for transaction {transaction_id}",
        )

    return bundle


# ── Query endpoint ────────────────────────────────────────────────


@router.post("/query")
async def query_bundles(request: BundleQueryRequest):
    """Query bundles with filters."""
    storage = _get_storage()

    results = await storage.query_bundles(
        transaction_id=request.transaction_id,
        risk_tier=request.risk_tier,
        detector_types=request.detector_types,
        from_date=request.from_date,
        to_date=request.to_date,
        status=request.status,
        limit=request.limit,
        offset=request.offset,
    )

    return {
        "total": len(results),
        "limit": request.limit,
        "offset": request.offset,
        "bundles": results,
    }


# ── Detector evidence endpoint ────────────────────────────────────


@router.get("/{bundle_id}/detectors")
async def get_detector_evidences(bundle_id: str):
    """Get detector evidence summaries from a bundle."""
    storage = _get_storage()

    bundle = await storage.retrieve_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    return {
        "bundle_id": bundle_id,
        "transaction_id": bundle.transaction_id,
        "risk_score": bundle.risk_score,
        "risk_tier": bundle.risk_tier,
        "detectors": [
            {
                "type": d.detector_type,
                "signal_value": d.signal_value,
                "confidence": d.confidence,
                "evidence_count": len(d.evidence_items),
                "has_benchmarks": d.benchmark_data is not None,
            }
            for d in bundle.detector_evidences
        ],
    }


# ── Evidence items endpoint ───────────────────────────────────────


@router.get("/{bundle_id}/evidence")
async def get_evidence_items(
    bundle_id: str,
    source: Optional[str] = Query(None, description="Filter by evidence source"),
    limit: int = Query(default=200, ge=1, le=5000),
):
    """Get individual evidence items from a bundle, with optional source filter."""
    storage = _get_storage()

    bundle = await storage.retrieve_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    items = bundle.get_all_evidence_items()

    if source:
        items = [i for i in items if i.source.value == source]

    return {
        "bundle_id": bundle_id,
        "total_count": len(items),
        "returned_count": min(len(items), limit),
        "items": [i.model_dump(mode="json") for i in items[:limit]],
    }


# ── Archive endpoint ──────────────────────────────────────────────


@router.post("/{bundle_id}/archive")
async def archive_bundle(
    bundle_id: str,
    reason: str = Query(default="user_requested", description="Archive reason"),
):
    """Soft-delete (archive) a bundle."""
    storage = _get_storage()

    success = await storage.archive_bundle(bundle_id, reason)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Bundle not found or already archived",
        )

    return {
        "status": "archived",
        "bundle_id": bundle_id,
        "reason": reason,
    }


# ── Stats endpoint ────────────────────────────────────────────────


@router.get("/stats/summary")
async def get_bundle_stats():
    """Get aggregate bundle statistics."""
    storage = _get_storage()
    return await storage.get_stats()


# ── Initialization hook ──────────────────────────────────────────


def init_routes(assembler: BundleAssembler, storage: BundleStorage):
    """Called by main.py to inject service dependencies into routes."""
    global _bundle_assembler, _bundle_storage
    _bundle_assembler = assembler
    _bundle_storage = storage
