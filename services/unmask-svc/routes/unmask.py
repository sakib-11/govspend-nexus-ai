"""Unmask routes — REST API for maker-checker unmask workflow."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from models.unmask import (
    UnmaskApproveRequest,
    UnmaskCreateRequest,
    UnmaskRejectRequest,
    UnmaskStatus,
    UnmaskViewRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/unmask", tags=["unmask"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} unavailable")
    return svc


def _require_auth(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def _require_admin(request: Request) -> Any:
    user = _require_auth(request)
    roles = [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]
    if "super_admin" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def _get_user_id(user: Any) -> str:
    return getattr(user, "user_id", "anonymous")


def _get_user_roles(user: Any) -> List[str]:
    return [r.value if hasattr(r, "value") else str(r) for r in getattr(user, "roles", [])]


# ------------------------------------------------------------------
# Request / Response helpers
# ------------------------------------------------------------------

class ViewResponse(BaseModel):
    data: Dict[str, Any]
    message: str
    timestamp: str


# ------------------------------------------------------------------
# Maker: Create unmask request
# ------------------------------------------------------------------

@router.post("/request")
async def create_unmask_request(body: UnmaskCreateRequest, request: Request) -> dict:
    """Create a new unmask request (Maker step)."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    try:
        result = await unmask_svc.create_request(
            request=body,
            user_id=_get_user_id(user),
            user_roles=_get_user_roles(user),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Error creating unmask request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ------------------------------------------------------------------
# Checker: Approve
# ------------------------------------------------------------------

@router.post("/approve")
async def approve_unmask_request(body: UnmaskApproveRequest, request: Request) -> dict:
    """Approve an unmask request (Checker step)."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    try:
        result = await unmask_svc.approve_request(
            request=body,
            user_id=_get_user_id(user),
            user_roles=_get_user_roles(user),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Error approving unmask request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ------------------------------------------------------------------
# Checker: Reject
# ------------------------------------------------------------------

@router.post("/reject")
async def reject_unmask_request(body: UnmaskRejectRequest, request: Request) -> dict:
    """Reject an unmask request."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    try:
        result = await unmask_svc.reject_request(
            request=body,
            user_id=_get_user_id(user),
            user_roles=_get_user_roles(user),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Error rejecting unmask request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ------------------------------------------------------------------
# Unmask: Fetch and decrypt data
# ------------------------------------------------------------------

@router.post("/unmask/{request_id}")
async def unmask_data(request_id: UUID, request: Request) -> dict:
    """Unmask the requested data from the ledger."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    try:
        result = await unmask_svc.unmask_data(
            request_id=request_id,
            user_id=_get_user_id(user),
            user_roles=_get_user_roles(user),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("Error unmasking data")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ------------------------------------------------------------------
# View: View unmasked data
# ------------------------------------------------------------------

@router.post("/view")
async def view_unmasked_data(body: UnmaskViewRequest, request: Request) -> dict:
    """View unmasked data with MFA verification."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    try:
        data = await unmask_svc.view_unmasked_data(
            request=body,
            user_id=_get_user_id(user),
            user_roles=_get_user_roles(user),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {
            "data": data,
            "message": "Data viewed successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Error viewing unmasked data")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------

@router.get("/{request_id}")
async def get_unmask_request(request_id: UUID, request: Request) -> dict:
    """Get a single unmask request by ID."""
    user = _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    result = await unmask_svc.get_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result.model_dump(mode="json")


@router.get("")
async def list_unmask_requests(
    request: Request,
    case_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    jurisdiction_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> List[dict]:
    """List unmask requests with optional filters."""
    _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    st = UnmaskStatus(status) if status else None
    rows = await unmask_svc.list_requests(
        case_id=case_id,
        status=st,
        jurisdiction_id=jurisdiction_id,
        limit=limit,
        offset=offset,
    )
    return rows


# ------------------------------------------------------------------
# Audit
# ------------------------------------------------------------------

@router.get("/audit/{request_id}")
async def get_audit_trail(request_id: UUID, request: Request) -> dict:
    """Get the audit trail for a request."""
    _require_auth(request)
    unmask_svc = _get_service(request, "unmask_service")

    trail = await unmask_svc.get_audit_trail(request_id)
    return {
        "request_id": str(request_id),
        "audit_trail": trail,
        "total": len(trail),
    }


@router.get("/audit/chain/verify")
async def verify_audit_chain(request: Request) -> dict:
    """Verify the audit hash chain (admin only)."""
    _require_admin(request)
    unmask_svc = _get_service(request, "unmask_service")

    result = await unmask_svc.verify_audit_chain()
    return result.model_dump(mode="json")


@router.get("/audit/chain/status")
async def get_chain_status(request: Request) -> dict:
    """Get audit chain status (admin only)."""
    _require_admin(request)
    audit_svc = _get_service(request, "audit_service")
    return await audit_svc.get_chain_status()


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "unmask-svc"}
