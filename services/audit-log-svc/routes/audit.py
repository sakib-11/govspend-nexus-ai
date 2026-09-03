"""Audit routes — REST API for querying, verifying, and analysing audit logs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from models.audit import AuditQuery, AuditVerificationResult
from services.audit_logger import AuditLogger
from services.audit_retriever import AuditRetriever
from services.audit_verifier import AuditVerifier
from services.batch_processor import BatchProcessor
from services.data_export import DataExporter
from services.hash_chain_manager import HashChainManager
from services.metrics import MetricsCollector
from services.retention import RetentionManager
from services.webhook_alerts import WebhookAlertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _require_admin(request: Request) -> None:
    """Raise 403 if the caller is not an admin / super_admin."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "super_admin" not in roles and "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} not available")
    return svc


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class AuditEntryResponse(BaseModel):
    audit_id: str
    event_type: str
    user_id: str
    resource_type: str
    action: str
    severity: str
    status: str
    timestamp: Optional[str] = None
    verified: bool = False
    sequence_number: Optional[int] = None


class ChainStatusResponse(BaseModel):
    total_entries: int
    is_valid: bool
    last_hash: Optional[str] = None
    chain_start_hash: Optional[str] = None
    tampered_entries: int = 0
    verified_entries: int = 0


class SearchResponse(BaseModel):
    entries: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    total_entries: int
    unique_users: int
    resource_types: int
    severity_breakdown: Dict[str, int]
    error_count: int
    avg_duration_ms: float


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def search_audit(request: Request, query: AuditQuery) -> SearchResponse:
    """Search audit entries with filters."""
    _require_admin(request)
    retriever: AuditRetriever = _get_service(request, "audit_retriever")
    entries, total = retriever.search(query)
    return SearchResponse(entries=entries, total=total, limit=query.limit, offset=query.offset)


@router.get("/{audit_id}")
async def get_audit_entry(audit_id: str, request: Request) -> Dict[str, Any]:
    """Get a single audit entry by ID."""
    _require_admin(request)
    logger_svc: AuditLogger = _get_service(request, "audit_logger")
    entry = await logger_svc.get_entry(audit_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found")
    return entry.model_dump(mode="json")


@router.get("/user/{user_id}")
async def get_user_audit(
    user_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Get audit entries for a specific user."""
    caller = getattr(request.state, "user", None)
    if caller is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    caller_id = getattr(caller, "user_id", None)
    caller_roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(caller, "roles", [])]

    if caller_id != user_id and "super_admin" not in caller_roles:
        raise HTTPException(status_code=403, detail="Not authorised to view this user's audit logs")

    retriever: AuditRetriever = _get_service(request, "audit_retriever")
    entries, total = retriever.get_user_audit(user_id, limit=limit, offset=offset)
    return {"user_id": user_id, "entries": entries, "total": total, "limit": limit, "offset": offset}


@router.get("/chain/verify")
async def verify_audit_chain(
    request: Request,
    start_sequence: Optional[int] = Query(default=None, ge=1),
) -> Dict[str, Any]:
    """Verify the audit hash chain integrity."""
    _require_admin(request)
    verifier: AuditVerifier = _get_service(request, "audit_verifier")
    return verifier.verify_chain(start_sequence)


@router.get("/chain/status", response_model=ChainStatusResponse)
async def get_chain_status(request: Request) -> ChainStatusResponse:
    """Get the audit chain status."""
    _require_admin(request)
    chain: HashChainManager = _get_service(request, "hash_chain_manager")
    status_ = chain.get_chain_status()
    return ChainStatusResponse(
        total_entries=status_.total_entries,
        is_valid=status_.is_valid,
        last_hash=status_.last_hash,
        chain_start_hash=status_.chain_start_hash,
        tampered_entries=status_.tampered_entries,
        verified_entries=status_.verified_entries,
    )


@router.post("/verify/{audit_id}")
async def verify_entry(audit_id: str, request: Request) -> AuditVerificationResult:
    """Verify a specific audit entry."""
    _require_admin(request)
    verifier: AuditVerifier = _get_service(request, "audit_verifier")
    return verifier.verify_entry(audit_id)


@router.get("/tampered")
async def get_tampered_entries(request: Request) -> Dict[str, Any]:
    """List all tampered audit entries."""
    _require_admin(request)
    verifier: AuditVerifier = _get_service(request, "audit_verifier")
    tampered = verifier.detect_tampering()
    return {"tampered_entries": tampered, "total": len(tampered)}


@router.get("/stats", response_model=StatsResponse)
async def get_audit_stats(
    request: Request,
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
) -> StatsResponse:
    """Get aggregate audit statistics."""
    _require_admin(request)
    retriever: AuditRetriever = _get_service(request, "audit_retriever")
    stats = retriever.get_stats(from_date, to_date)
    return StatsResponse(**stats)


# ------------------------------------------------------------------
# Production endpoints: Metrics, Health, Export, Retention
# ------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics(request: Request) -> Dict[str, Any]:
    """Prometheus-compatible metrics endpoint."""
    metrics: Optional[MetricsCollector] = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return {"error": "metrics collector not available"}
    return metrics.get_all_metrics()


@router.get("/health/detailed")
async def detailed_health(request: Request) -> Dict[str, Any]:
    """Detailed health check with chain status and service metrics."""
    chain: Optional[HashChainManager] = _get_service(request, "hash_chain_manager")
    metrics: Optional[MetricsCollector] = getattr(request.app.state, "metrics", None)
    batch: Optional[BatchProcessor] = getattr(request.app.state, "batch_processor", None)
    rate_limiter = getattr(request.app.state, "rate_limiter", None)

    chain_status = chain.get_chain_status() if chain else None

    return {
        "status": "healthy",
        "service": "audit-logging-svc",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chain": {
            "total_entries": chain_status.total_entries if chain_status else 0,
            "is_valid": chain_status.is_valid if chain_status else True,
            "last_hash": chain_status.last_hash if chain_status else None,
            "tampered_entries": chain_status.tampered_entries if chain_status else 0,
        },
        "metrics": metrics.get_all_metrics() if metrics else None,
        "batch_processor": batch.get_stats() if batch else None,
        "rate_limiter": rate_limiter.get_stats() if rate_limiter else None,
    }


# ------------------------------------------------------------------
# Export endpoints
# ------------------------------------------------------------------


class ExportRequest(BaseModel):
    format: str = "json"  # json, ndjson, csv
    user_id: Optional[str] = None
    event_type: Optional[List[str]] = None
    resource_type: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = 1000


class ExportResponse(BaseModel):
    format: str
    entry_count: int
    data: str
    generated_at: str


@router.post("/export", response_model=ExportResponse)
async def export_audit_data(
    request: Request,
    export_req: ExportRequest,
) -> ExportResponse:
    """Export audit entries in CSV, JSON, or NDJSON format."""
    _require_admin(request)
    retriever: AuditRetriever = _get_service(request, "audit_retriever")
    exporter = DataExporter(retriever)

    # Build query
    event_types = None
    if export_req.event_type:
        from models.audit import AuditEventType
        event_types = [AuditEventType(e) for e in export_req.event_type]

    query = AuditQuery(
        user_id=export_req.user_id,
        event_type=event_types,
        resource_type=export_req.resource_type,
        from_date=export_req.from_date,
        to_date=export_req.to_date,
        limit=export_req.limit,
    )

    entries, total = retriever.search(query)

    if export_req.format == "csv":
        data = exporter.export_csv(entries)
    elif export_req.format == "ndjson":
        data = exporter.export_ndjson(entries)
    else:
        data = exporter.export_json(entries)

    return ExportResponse(
        format=export_req.format,
        entry_count=len(entries),
        data=data,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/export/summary")
async def export_summary_report(
    request: Request,
    export_req: ExportRequest,
) -> Dict[str, Any]:
    """Generate an aggregate summary report."""
    _require_admin(request)
    retriever: AuditRetriever = _get_service(request, "audit_retriever")
    exporter = DataExporter(retriever)

    query = AuditQuery(
        user_id=export_req.user_id,
        resource_type=export_req.resource_type,
        from_date=export_req.from_date,
        to_date=export_req.to_date,
        limit=export_req.limit,
    )

    entries, _ = retriever.search(query)
    return exporter.generate_summary_report(entries)


# ------------------------------------------------------------------
# Retention management
# ------------------------------------------------------------------


@router.get("/retention/status")
async def get_retention_status(request: Request) -> Dict[str, Any]:
    """Get retention and archival status."""
    _require_admin(request)
    retention: Optional[RetentionManager] = getattr(request.app.state, "retention_manager", None)
    if retention is None:
        return {"error": "retention manager not available"}
    return retention.get_retention_status()


@router.post("/retention/archive")
async def archive_entries(request: Request) -> Dict[str, Any]:
    """Archive entries older than the archive threshold."""
    _require_admin(request)
    retention: Optional[RetentionManager] = getattr(request.app.state, "retention_manager", None)
    if retention is None:
        return {"error": "retention manager not available"}
    return await retention.archive_entries()


@router.post("/retention/cleanup")
async def cleanup_expired(request: Request) -> Dict[str, Any]:
    """Delete entries that exceed the retention period."""
    _require_admin(request)
    retention: Optional[RetentionManager] = getattr(request.app.state, "retention_manager", None)
    if retention is None:
        return {"error": "retention manager not available"}
    return await retention.cleanup_expired()


# ------------------------------------------------------------------
# Webhook alert stats
# ------------------------------------------------------------------


@router.get("/alerts/stats")
async def get_alert_stats(request: Request) -> Dict[str, Any]:
    """Get webhook alert statistics."""
    _require_admin(request)
    alerts: Optional[WebhookAlertService] = getattr(request.app.state, "webhook_alerts", None)
    if alerts is None:
        return {"error": "webhook alert service not available"}
    return alerts.get_stats()


# ------------------------------------------------------------------
# Batch processor stats
# ------------------------------------------------------------------


@router.get("/batch/stats")
async def get_batch_stats(request: Request) -> Dict[str, Any]:
    """Get batch processor statistics."""
    _require_admin(request)
    batch: Optional[BatchProcessor] = getattr(request.app.state, "batch_processor", None)
    if batch is None:
        return {"error": "batch processor not available"}
    return batch.get_stats()
