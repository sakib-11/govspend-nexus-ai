"""Unmask request and workflow routes — Access control and audit trails."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/unmask", tags=["unmask"])


# ======================================================================
# Mock Data
# ======================================================================

def _get_mock_unmask_requests() -> List[Dict[str, Any]]:
    """Generate mock unmask requests."""
    return [
        {
            "id": "req_001",
            "case_id": "case_123",
            "requester": "user_456",
            "requester_name": "Sarah Johnson",
            "requester_email": "sarah.j@agency.gov",
            "status": "pending",
            "priority": "high",
            "requested_at": "2024-01-15T10:30:00Z",
            "reason": "Need access to contract terms for audit review",
            "justification": "Regulatory compliance requirement",
            "data_fields": ["contract_terms", "vendor_revenue"],
            "expiration_hours": 24,
            "metadata": {"ip_address": "192.168.1.100", "user_agent": "Mozilla/5.0..."},
        },
        {
            "id": "req_002",
            "case_id": "case_456",
            "requester": "user_789",
            "requester_name": "Mike Chen",
            "requester_email": "mike.c@agency.gov",
            "status": "approved",
            "priority": "normal",
            "requested_at": "2024-01-14T14:15:00Z",
            "approved_at": "2024-01-14T16:30:00Z",
            "approver": "user_123",
            "approver_name": "Admin User",
            "reason": "Investigative access during fraud inquiry",
            "justification": "Active investigation",
            "data_fields": ["all"],
            "expiration_hours": 72,
            "metadata": {"ip_address": "192.168.1.200", "user_agent": "Mozilla/5.0..."},
        },
        {
            "id": "req_003",
            "case_id": "case_789",
            "requester": "user_999",
            "requester_name": "Emily Davis",
            "requester_email": "emily.d@agency.gov",
            "status": "rejected",
            "priority": "low",
            "requested_at": "2024-01-13T09:00:00Z",
            "rejected_at": "2024-01-13T11:45:00Z",
            "rejecter": "user_123",
            "rejecter_name": "Admin User",
            "rejection_reason": "Business purpose not aligned with current investigation",
            "reason": "Business intelligence access",
            "justification": "Market research needs",
            "data_fields": ["public_data"],
            "expiration_hours": 48,
            "metadata": {"ip_address": "192.168.1.150", "user_agent": "Mozilla/5.0..."},
        },
    ]


# ======================================================================
# Endpoints
# ======================================================================

@router.get("/requests")
async def list_unmask_requests(
    request: Request,
    status_filter: Optional[str] = None,
    requester: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get list of unmask requests with filtering for reviewers."""
    all_requests = _get_mock_unmask_requests()

    filtered = all_requests
    if status_filter:
        filtered = [r for r in filtered if r["status"] == status_filter]
    if requester:
        filtered = [r for r in filtered if r["requester"] == requester]

    total = len(filtered)
    paginated = filtered[offset : offset + limit]

    return {
        "requests": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters_applied": {"status": status_filter, "requester": requester},
    }


@router.post("/request")
async def create_unmask_request(
    request: Request,
    request_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new unmask access request."""
    required_fields = ["case_id", "reason", "justification", "data_fields"]
    for field in required_fields:
        if field not in request_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    request_id = f"req_{secrets.token_hex(8)}"
    new_request = {
        "id": request_id,
        "case_id": request_data["case_id"],
        "requester": current_user.user_id,
        "requester_name": getattr(current_user, "full_name", ""),
        "requester_email": getattr(current_user, "email", ""),
        "status": "pending",
        "priority": "normal",
        "requested_at": "2024-01-15T10:30:00Z",
        "reason": request_data["reason"],
        "justification": request_data["justification"],
        "data_fields": request_data["data_fields"],
        "expiration_hours": 24,
        "metadata": {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
        },
    }

    return {
        "status": "success",
        "request_id": request_id,
        "message": "Unmask request created successfully",
        "estimated_processing_time": "2-4 hours",
        "next_steps": [
            "Request will be reviewed by Level 2+ auditor",
            "You will be notified when request is approved or rejected",
            "Access will be granted upon approval",
        ],
    }


@router.post("/request/{request_id}/approve")
async def approve_unmask_request(
    request_id: str,
    request: Request,
    approval_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Approve a pending unmask request."""
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_roles = getattr(current_user, "roles", [])
    if "auditor_level_2" not in user_roles and "auditor_level_3" not in user_roles:
        raise HTTPException(status_code=403, detail="Only Level 2+ auditors can approve unmask requests")

    return {
        "status": "approved",
        "request_id": request_id,
        "approved_at": "2024-01-15T11:00:00Z",
        "approver": current_user.user_id,
        "approval_comments": approval_data.get("comments", ""),
        "access_expires": "2024-01-16T11:00:00Z",
    }


@router.post("/request/{request_id}/reject")
async def reject_unmask_request(
    request_id: str,
    request: Request,
    rejection_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Reject a pending unmask request with reason."""
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_roles = getattr(current_user, "roles", [])
    if "auditor_level_2" not in user_roles and "auditor_level_3" not in user_roles:
        raise HTTPException(status_code=403, detail="Only Level 2+ auditors can reject unmask requests")

    if not rejection_data.get("rejection_reason"):
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    return {
        "status": "rejected",
        "request_id": request_id,
        "rejected_at": "2024-01-15T11:00:00Z",
        "rejecter": current_user.user_id,
        "rejection_reason": rejection_data["rejection_reason"],
    }


@router.get("/case/{case_id}/status")
async def get_case_unmask_status(
    case_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Get unmask request status and active access for a case."""
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    return {
        "case_id": case_id,
        "has_active_requests": True,
        "has_active_access": True,
        "active_requests": [
            {
                "id": "req_001",
                "status": "approved",
                "requester": "user_456",
                "requester_name": "Sarah Johnson",
                "approved_at": "2024-01-14T16:30:00Z",
                "approver": "user_123",
                "approver_name": "Admin User",
                "access_expires": "2024-01-16T14:30:00Z",
                "access_level": "full",
                "data_fields": ["vendor_revenue", "contract_terms"],
            }
        ],
        "pending_requests": [
            {
                "id": "req_004",
                "requester": "user_999",
                "requester_name": "Emily Davis",
                "requested_at": "2024-01-15T09:00:00Z",
                "reason": "Business intelligence",
                "priority": "low",
                "expiration_hours": 48,
            }
        ],
        "can_request_new": True,
        "request_count_24h": 3,
        "approval_rate": 67.0,
    }