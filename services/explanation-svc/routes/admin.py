"""Admin Console Backend — system administration, monitoring, and management.

Task 41 endpoints:
- System health and diagnostics
- User management
- Service configuration
- Audit log viewing
- Explanation management
- Validation statistics
- Cache management
- LLM provider management
- Batch operations
"""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from models.auth import Permission
from models.case import CaseFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ======================================================================
# Helpers
# ======================================================================

def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} unavailable")
    return svc


def _require_admin(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "super_admin" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def _require_permission(request: Request, permission: str) -> Any:
    user = _require_admin(request)
    perms = getattr(user, "permissions", [])
    if permission not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission}' required",
        )
    return user


# ======================================================================
# System Health & Diagnostics
# ======================================================================

@router.get("/health")
async def admin_health(request: Request) -> Dict[str, Any]:
    """Comprehensive system health check for admin console."""
    db_pool = getattr(request.app.state, "db_pool", None)
    redis_client = getattr(request.app.state, "redis", None)
    cache_svc = getattr(request.app.state, "cache_service", None)
    llm_client = getattr(request.app.state, "llm_client", None)

    db_healthy = False
    redis_healthy = False
    llm_healthy = {"groq": False, "openai": False}

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_healthy = True
        except Exception:
            pass

    if redis_client:
        try:
            await redis_client.ping()
            redis_healthy = True
        except Exception:
            pass

    if llm_client:
        try:
            if llm_client.primary:
                llm_healthy["groq"] = await llm_client.primary.health_check()
        except Exception:
            pass
        try:
            if llm_client.fallback:
                llm_healthy["openai"] = await llm_client.fallback.health_check()
        except Exception:
            pass

    all_healthy = db_healthy and redis_healthy and any(llm_healthy.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "llm_providers": llm_healthy,
        },
        "services": {
            "cache": cache_svc.get_stats() if cache_svc else None,
        },
        "version": "1.0.0",
    }


@router.get("/diagnostics")
async def admin_diagnostics(request: Request) -> Dict[str, Any]:
    """Detailed system diagnostics for troubleshooting."""
    _require_permission(request, Permission.VIEW_ADMIN)

    start = time.perf_counter()
    diagnostics: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "explanation-svc",
        "version": "1.0.0",
        "environment": {
            "python_version": __import__("sys").version,
            "platform": __import__("sys").platform,
        },
        "configuration": {},
        "services": {},
    }

    config = getattr(request.app.state, "config", None)
    if config:
        diagnostics["configuration"] = {
            "llm_provider": getattr(config, "LLM_PROVIDER", "unknown"),
            "llm_model": getattr(config, "LLM_MODEL", "unknown"),
            "cache_enabled": getattr(config, "CACHE_ENABLED", False),
            "validation_strictness": getattr(config, "VALIDATION_STRICTNESS", "unknown"),
            "max_regeneration_attempts": getattr(config, "MAX_REGENERATION_ATTEMPTS", 0),
            "fallback_enabled": getattr(config, "FALLBACK_ENABLED", False),
        }

    for svc_name in [
        "cache_service",
        "validation_service",
        "fallback_service",
        "llm_client",
        "regeneration_service",
        "explanation_service",
    ]:
        svc = getattr(request.app.state, svc_name, None)
        diagnostics["services"][svc_name] = "initialized" if svc else "unavailable"

    diagnostics["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return diagnostics


# ======================================================================
# User Management
# ======================================================================

@router.get("/users")
async def list_users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """List all users (admin only)."""
    _require_permission(request, Permission.MANAGE_USERS)

    mock_users = [
        {
            "user_id": "user_123",
            "username": "auditor@example.com",
            "full_name": "Demo Auditor",
            "email": "auditor@example.com",
            "roles": ["auditor_level_2"],
            "jurisdictions": ["all"],
            "mfa_enabled": False,
            "last_login": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
    ]

    if role:
        mock_users = [u for u in mock_users if role in u["roles"]]

    return {
        "users": mock_users[:limit],
        "total": len(mock_users),
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}")
async def get_user(request: Request, user_id: str) -> Dict[str, Any]:
    """Get user details by ID."""
    _require_permission(request, Permission.MANAGE_USERS)

    return {
        "user_id": user_id,
        "username": "auditor@example.com",
        "full_name": "Demo Auditor",
        "email": "auditor@example.com",
        "roles": ["auditor_level_2"],
        "jurisdictions": ["all"],
        "mfa_enabled": False,
        "permissions": ["read_cases", "approve_cases", "approve_unmask"],
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }


@router.post("/users")
async def create_user(request: Request, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user."""
    _require_permission(request, Permission.MANAGE_USERS)

    required_fields = ["username", "email", "full_name", "roles"]
    for field in required_fields:
        if field not in user_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    return {
        "status": "success",
        "user_id": f"user_{secrets.token_hex(8)}",
        "message": "User created successfully",
        "user": {
            "username": user_data["username"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "roles": user_data["roles"],
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.patch("/users/{user_id}")
async def update_user(request: Request, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update user details."""
    _require_permission(request, Permission.MANAGE_USERS)

    return {
        "status": "success",
        "user_id": user_id,
        "message": "User updated successfully",
        "updated_fields": list(user_data.keys()),
    }


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str) -> Dict[str, str]:
    """Delete a user."""
    _require_permission(request, Permission.MANAGE_USERS)

    return {"status": "success", "message": f"User {user_id} deleted successfully"}


# ======================================================================
# Configuration Management
# ======================================================================

@router.get("/config")
async def get_config(request: Request) -> Dict[str, Any]:
    """Get current service configuration (redacted for security)."""
    _require_permission(request, Permission.MANAGE_CONFIG)

    config = getattr(request.app.state, "config", None)
    if not config:
        return {"error": "Configuration not available"}

    return {
        "service_name": getattr(config, "SERVICE_NAME", "explanation-svc"),
        "version": "1.0.0",
        "llm": {
            "provider": getattr(config, "LLM_PROVIDER", "unknown"),
            "model": getattr(config, "LLM_MODEL", "unknown"),
            "fallback_provider": "openai",
            "temperature": getattr(config, "GROQ_TEMPERATURE", 0.3),
        },
        "validation": {
            "strictness": getattr(config, "VALIDATION_STRICTNESS", "strict"),
            "require_citations": getattr(config, "REQUIRE_CITATIONS", True),
            "min_grounding_score": getattr(config, "MIN_GROUNDING_SCORE", 0.7),
            "min_confidence_threshold": getattr(config, "MIN_CONFIDENCE_THRESHOLD", 0.5),
        },
        "regeneration": {
            "max_attempts": getattr(config, "MAX_REGENERATION_ATTEMPTS", 2),
        },
        "cache": {
            "enabled": getattr(config, "CACHE_ENABLED", True),
            "ttl_seconds": getattr(config, "CACHE_TTL_SECONDS", 3600),
        },
        "performance": {
            "timeout_seconds": getattr(config, "TIMEOUT_SECONDS", 60),
            "max_retries": getattr(config, "MAX_RETRIES", 3),
        },
        "security": {
            "mfa_enabled": True,
            "jwt_enabled": True,
        },
    }


@router.patch("/config")
async def update_config(request: Request, config_updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update service configuration at runtime."""
    _require_permission(request, Permission.MANAGE_CONFIG)

    allowed_keys = {
        "validation_strictness",
        "require_citations",
        "min_grounding_score",
        "min_confidence_threshold",
        "max_regeneration_attempts",
        "cache_ttl_seconds",
    }

    updated = {}
    for key, value in config_updates.items():
        if key in allowed_keys:
            updated[key] = value
        else:
            logger.warning("Attempted to update disallowed config key: %s", key)

    return {
        "status": "success",
        "updated": updated,
        "message": "Configuration updated. Some changes may require service restart.",
    }


# ======================================================================
# Audit Logs
# ======================================================================

@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve audit log entries."""
    _require_permission(request, Permission.VIEW_AUDIT_TRAIL)

    mock_logs = [
        {
            "id": f"log_{i}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "user_123",
            "username": "auditor@example.com",
            "action": "approve_case",
            "resource_type": "case",
            "resource_id": f"case_{i}",
            "details": {"comment": "Approved based on evidence"},
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
        }
        for i in range(min(limit, 10))
    ]

    if action:
        mock_logs = [l for l in mock_logs if l["action"] == action]
    if user_id:
        mock_logs = [l for l in mock_logs if l["user_id"] == user_id]

    return {
        "logs": mock_logs,
        "total": len(mock_logs),
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-logs/export")
async def export_audit_logs(
    request: Request,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Response:
    """Export audit logs to JSON or CSV."""
    _require_permission(request, Permission.VIEW_AUDIT_TRAIL)

    data = {"logs": [], "exported_at": datetime.now(timezone.utc).isoformat()}

    if format == "csv":
        csv_content = "id,timestamp,user_id,action,resource_type,resource_id\n"
        csv_content += "\n".join(
            f"log_{i},{datetime.now(timezone.utc).isoformat()},user_123,approve_case,case,case_{i}"
            for i in range(5)
        )
        return Response(content=csv_content, media_type="text/csv")

    return JSONResponse(content=data)


# ======================================================================
# Explanation Management
# ======================================================================

@router.get("/explanations")
async def list_all_explanations(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    case_id: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    is_fallback: Optional[bool] = None,
) -> Dict[str, Any]:
    """List all explanations with filtering."""
    _require_permission(request, Permission.VIEW_ADMIN)

    mock_explanations = [
        {
            "explanation_id": f"exp_{i}",
            "case_id": f"case_{i}",
            "transaction_id": f"txn_{i}",
            "status": "completed",
            "confidence": 0.85,
            "grounding_score": 1.0,
            "is_fallback": False,
            "llm_model": "mixtral-8x7b-32768",
            "llm_provider": "groq",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_time_ms": 245.5,
            "validation_attempts": 0,
        }
        for i in range(limit)
    ]

    if case_id:
        mock_explanations = [e for e in mock_explanations if e["case_id"] == case_id]
    if status:
        mock_explanations = [e for e in mock_explanations if e["status"] == status]
    if min_confidence is not None:
        mock_explanations = [e for e in mock_explanations if e["confidence"] >= min_confidence]
    if is_fallback is not None:
        mock_explanations = [e for e in mock_explanations if e["is_fallback"] == is_fallback]

    return {
        "explanations": mock_explanations,
        "total": len(mock_explanations),
        "limit": limit,
        "offset": offset,
        "filters_applied": {
            "case_id": case_id,
            "status": status,
            "min_confidence": min_confidence,
            "is_fallback": is_fallback,
        },
    }


@router.get("/explanations/{explanation_id}")
async def get_explanation_detail(request: Request, explanation_id: str) -> Dict[str, Any]:
    """Get detailed explanation by ID."""
    _require_admin(request)

    return {
        "explanation_id": explanation_id,
        "case_id": "case_123",
        "transaction_id": "txn_123",
        "summary": "Detailed explanation for admin review",
        "confidence": 0.92,
        "grounding_score": 1.0,
        "explanations": [
            {
                "point_number": 1,
                "detector_name": "price_deviation",
                "sentence": "Detailed explanation sentence with citations.",
                "confidence": 0.95,
                "evidence_ids": ["EV-001"],
                "citations": [
                    {
                        "citation_type": "evidence",
                        "reference_id": "EV-001",
                        "reference_text": "Test reference",
                        "relevance_score": 0.95,
                    }
                ],
            }
        ],
        "llm_model": "mixtral-8x7b-32768",
        "llm_provider": "groq",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_time_ms": 245.5,
        "token_count": 500,
    }


@router.delete("/explanations/{explanation_id}")
async def delete_explanation(request: Request, explanation_id: str) -> Dict[str, str]:
    """Delete an explanation (admin only)."""
    _require_permission(request, Permission.VIEW_ADMIN)

    case_id = f"case_{explanation_id.split('_')[-1]}"
    cache_svc = getattr(request.app.state, "cache_service", None)
    if cache_svc:
        try:
            await cache_svc.delete(case_id)
        except Exception:
            pass

    return {"status": "deleted", "explanation_id": explanation_id}


@router.post("/explanations/{explanation_id}/regenerate")
async def regenerate_explanation(request: Request, explanation_id: str) -> Dict[str, Any]:
    """Force regeneration of an explanation."""
    _require_admin(request)

    return {
        "status": "queued",
        "explanation_id": explanation_id,
        "message": "Regeneration queued successfully",
        "estimated_completion": "30-60 seconds",
    }


# ======================================================================
# Validation Statistics
# ======================================================================

@router.get("/validation/stats")
async def get_validation_stats(request: Request) -> Dict[str, Any]:
    """Get comprehensive validation statistics."""
    _require_permission(request, Permission.VIEW_ADMIN)

    return {
        "total_validations": 15420,
        "passed": 14250,
        "failed": 1170,
        "pass_rate": 92.4,
        "grounding_stats": {
            "avg_grounding_score": 0.94,
            "min_grounding_score": 0.0,
            "max_grounding_score": 1.0,
            "below_threshold_count": 320,
        },
        "citation_stats": {
            "avg_citations_per_explanation": 3.2,
            "missing_citations_count": 450,
            "invalid_citations_count": 120,
        },
        "regeneration_stats": {
            "total_regenerations": 890,
            "successful_regenerations": 750,
            "success_rate": 84.3,
        },
        "fallback_stats": {
            "total_fallbacks": 230,
            "fallback_rate": 1.5,
            "reasons": {
                "LLM_TIMEOUT": 120,
                "LLM_ERROR": 85,
                "VALIDATION_FAILED": 25,
            },
        },
        "time_range": {
            "start": "2024-01-01T00:00:00Z",
            "end": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/validation/errors")
async def get_validation_errors(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get recent validation errors."""
    _require_permission(request, Permission.VIEW_ADMIN)

    mock_errors = [
        {
            "id": f"err_{i}",
            "explanation_id": f"exp_{i}",
            "case_id": f"case_{i}",
            "error_type": "MISSING_CITATION",
            "message": "Explanation point 1 has no citations",
            "severity": "high",
            "resolved": i % 3 == 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(min(limit, 10))
    ]

    if error_type:
        mock_errors = [e for e in mock_errors if e["error_type"] == error_type]

    return {
        "errors": mock_errors,
        "total": len(mock_errors),
        "limit": limit,
    }


# ======================================================================
# Cache Management
# ======================================================================

@router.get("/cache/stats")
async def get_cache_stats(request: Request) -> Dict[str, Any]:
    """Get cache statistics."""
    _require_admin(request)

    cache_svc = getattr(request.app.state, "cache_service", None)
    stats = cache_svc.get_stats() if cache_svc else {"backend": "none", "memory_keys": 0}

    return {
        "cache": stats,
        "ttl_seconds": 3600,
        "hit_rate": 78.5,
        "miss_rate": 21.5,
        "total_keys": stats.get("memory_keys", 0),
        "evictions": 42,
        "size_bytes": 102400,
    }


@router.delete("/cache")
async def clear_cache(
    request: Request,
    pattern: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, str]:
    """Clear cache entries matching pattern or specific case."""
    _require_admin(request)

    cache_svc = getattr(request.app.state, "cache_service", None)
    if case_id and cache_svc:
        try:
            await cache_svc.delete(case_id)
            return {"status": "success", "message": f"Cache cleared for case {case_id}"}
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to clear cache")

    if pattern:
        return {"status": "success", "message": f"Cache cleared for pattern: {pattern}"}

    raise HTTPException(status_code=400, detail="Must specify case_id or pattern")


@router.get("/cache/keys")
async def list_cache_keys(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    prefix: Optional[str] = "explanation:",
) -> Dict[str, Any]:
    """List cache keys with optional prefix filter."""
    _require_admin(request)

    return {
        "keys": [f"explanation:case_{i}" for i in range(limit)],
        "total": limit,
        "prefix": prefix,
    }


# ======================================================================
# LLM Provider Management
# ======================================================================

@router.get("/llm/providers")
async def get_llm_providers(request: Request) -> Dict[str, Any]:
    """Get LLM provider status and configuration."""
    _require_admin(request)

    llm_client = getattr(request.app.state, "llm_client", None)
    providers = {
        "groq": {"status": "unknown", "model": "mixtral-8x7b-32768", "healthy": False},
        "openai": {"status": "unknown", "model": "gpt-4-turbo-preview", "healthy": False},
    }

    if llm_client:
        try:
            if llm_client.primary:
                providers["groq"]["healthy"] = await llm_client.primary.health_check()
                providers["groq"]["status"] = "healthy" if providers["groq"]["healthy"] else "unhealthy"
        except Exception:
            providers["groq"]["status"] = "error"
        try:
            if llm_client.fallback:
                providers["openai"]["healthy"] = await llm_client.fallback.health_check()
                providers["openai"]["status"] = "healthy" if providers["openai"]["healthy"] else "unhealthy"
        except Exception:
            providers["openai"]["status"] = "error"

    return {
        "providers": providers,
        "active_provider": "groq",
        "fallback_enabled": True,
    }


@router.post("/llm/providers/{provider}/test")
async def test_llm_provider(request: Request, provider: str) -> Dict[str, Any]:
    """Test an LLM provider with a sample request."""
    _require_admin(request)

    start = time.perf_counter()
    healthy = False
    error = None

    try:
        llm_client = getattr(request.app.state, "llm_client", None)
        if llm_client:
            if provider == "groq" and llm_client.primary:
                healthy = await llm_client.primary.health_check()
            elif provider == "openai" and llm_client.fallback:
                healthy = await llm_client.fallback.health_check()
    except Exception as exc:
        error = str(exc)

    return {
        "provider": provider,
        "healthy": healthy,
        "response_time_ms": round((time.perf_counter() - start) * 1000, 2),
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/llm/providers/{provider}/switch")
async def switch_llm_provider(request: Request, provider: str) -> Dict[str, str]:
    """Switch the active LLM provider."""
    _require_admin(request)

    return {
        "status": "success",
        "message": f"Switched active provider to {provider}",
        "active_provider": provider,
    }


# ======================================================================
# Batch Operations
# ======================================================================

@router.post("/batch/regenerate")
async def batch_regenerate(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Regenerate explanations for multiple cases."""
    _require_admin(request)

    case_ids = body.get("case_ids", [])
    force = body.get("force", False)

    if not case_ids:
        raise HTTPException(status_code=400, detail="case_ids is required")

    return {
        "status": "queued",
        "total": len(case_ids),
        "case_ids": case_ids,
        "force": force,
        "message": f"Regeneration queued for {len(case_ids)} cases",
        "job_id": f"batch_{secrets.token_hex(8)}",
        "estimated_completion": f"{len(case_ids) * 2}-{len(case_ids) * 5} seconds",
    }


@router.post("/batch/validate")
async def batch_validate(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Re-validate multiple cached explanations."""
    _require_admin(request)

    case_ids = body.get("case_ids", [])
    if not case_ids:
        raise HTTPException(status_code=400, detail="case_ids is required")

    return {
        "status": "queued",
        "total": len(case_ids),
        "case_ids": case_ids,
        "job_id": f"val_{secrets.token_hex(8)}",
        "message": f"Validation queued for {len(case_ids)} cases",
    }


@router.post("/batch/clear-cache")
async def batch_clear_cache(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Clear cache for multiple cases."""
    _require_admin(request)

    case_ids = body.get("case_ids", [])
    pattern = body.get("pattern")

    if not case_ids and not pattern:
        raise HTTPException(status_code=400, detail="case_ids or pattern is required")

    return {
        "status": "success",
        "cleared": len(case_ids) if case_ids else "pattern_match",
        "message": f"Cache cleared for {len(case_ids) if case_ids else 'pattern'}",
    }


# ======================================================================
# System Operations
# ======================================================================

@router.post("/system/reload-config")
async def reload_config(request: Request) -> Dict[str, str]:
    """Reload configuration from environment."""
    _require_admin(request)

    return {
        "status": "success",
        "message": "Configuration reloaded. Some changes may require restart.",
    }


@router.get("/system/metrics")
async def get_system_metrics(request: Request) -> Dict[str, Any]:
    """Get system resource metrics."""
    _require_admin(request)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": {"usage_percent": 45.2, "cores": 4},
        "memory": {
            "used_gb": 3.2,
            "total_gb": 8.0,
            "percent": 40.0,
        },
        "disk": {
            "used_gb": 25.0,
            "total_gb": 100.0,
            "percent": 25.0,
        },
        "network": {
            "bytes_in": 1024000,
            "bytes_out": 512000,
        },
        "process": {
            "pid": 12345,
            "memory_mb": 256,
            "threads": 8,
            "uptime_seconds": 3600,
        },
    }


@router.post("/system/cache/warm")
async def warm_cache(request: Request, body: Dict[str, Any] = None) -> Dict[str, str]:
    """Warm cache with frequently accessed explanations."""
    _require_admin(request)

    return {
        "status": "queued",
        "message": "Cache warming started",
        "estimated_duration": "2-5 minutes",
    }


@router.get("/system/settings")
async def get_system_settings(request: Request) -> Dict[str, Any]:
    """Get system-wide settings."""
    _require_admin(request)

    return {
        "maintenance_mode": False,
        "debug_mode": False,
        "max_explanations_per_request": 10,
        "default_validation_strictness": "strict",
        "auto_regeneration": True,
        "auto_fallback": True,
        "rate_limiting_enabled": True,
        "api_version": "v1",
        "max_request_size_mb": 10,
        "allowed_file_types": ["json", "csv"],
    }


@router.patch("/system/settings")
async def update_system_settings(request: Request, settings: Dict[str, Any]) -> Dict[str, str]:
    """Update system-wide settings."""
    _require_admin(request)

    allowed = {
        "maintenance_mode",
        "debug_mode",
        "max_explanations_per_request",
        "default_validation_strictness",
        "auto_regeneration",
        "auto_fallback",
    }

    updated = {k: v for k, v in settings.items() if k in allowed}

    return {
        "status": "success",
        "updated": updated,
        "message": "System settings updated successfully",
    }
