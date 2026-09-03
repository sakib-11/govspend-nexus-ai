"""Case routes — CRUD and workflow operations for Auditor Console."""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status

from models.case import CaseDetail, CaseFilter, CaseListResponse

router = APIRouter(prefix="/api/cases", tags=["cases"])


# ======================================================================
# Endpoints
# ======================================================================

@router.get("/")
async def list_cases(
    request: Request,
    filter_q: Optional[str] = None,
    tier: Optional[str] = None,
    status: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get paginated list of cases for queue view."""
    # TODO: Implement with database query
    # Mock data for now
    cases = [
        {
            "id": f"case_{i}",
            "transaction_id": f"txn_{i}",
            "risk_score": 0.75,
            "tier": "HIGH",
            "status": "PENDING",
            "department": "FINANCE",
            "vendor_token": f"vendor_{i}",
            "amount": 1000.0 * (i + 1),
            "transaction_date": "2024-01-15T10:30:00Z",
            "signal_count": 5,
            "top_signals": [
                {"type": "price_deviation", "value": 0.85, "severity": "HIGH"},
                {"type": "duplicate_fuzzy", "value": 0.92, "severity": "CRITICAL"},
            ],
            "assigned_to": "user_456" if i % 3 == 0 else None,
            "created_at": "2024-01-15T09:00:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
        }
        for i in range(limit)
    ]

    return {
        "cases": cases,
        "total": 1000,
        "limit": limit,
        "offset": offset,
        "filters_applied": {
            "tier": tier,
            "status": status,
            "jurisdiction": jurisdiction,
            "search": filter_q,
        },
    }


@router.get("/{case_id}")
async def get_case_detail(case_id: str, request: Request) -> Dict[str, Any]:
    """Get detailed view of a case for Auditor Console."""
    # TODO: Integrate with actual case service
    case_detail = {
        "id": case_id,
        "transaction_id": f"txn_{case_id.split('_')[1]}",
        "risk_score": 0.75,
        "tier": "HIGH",
        "status": "PENDING",
        "department": "FINANCE",
        "vendor_token": "vendor_123",
        "vendor_name": "Acme Corp",
        "amount": 50000.0,
        "transaction_date": "2024-01-15T10:30:00Z",
        "risk_factors": [
            {
                "type": "price_deviation",
                "value": 0.85,
                "severity": "HIGH",
                "description": "Price variance exceeds 80% threshold",
            },
            {
                "type": "duplicate_fuzzy",
                "value": 0.92,
                "severity": "CRITICAL",
                "description": "Duplicate detection with high confidence",
            },
        ],
        "jurisdiction": "FEDERAL",
        "assigned_to": "user_456",
        "assigned_role": "AUDITOR_LEVEL_2",
        "created_at": "2024-01-15T09:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "explanations": [
            {
                "explanation_id": "exp_123",
                "content": "The price deviation risk is elevated due to significant variance in the vendor's pricing structure compared to market benchmarks.",
                "confidence": 0.85,
                "grounding_score": 1.0,
                "is_grounded": True,
                "is_valid": True,
                "has_ungrounded": False,
                "validation_time_ms": 245,
            }
        ],
        "actions": [
            {
                "id": "action_1",
                "type": "approve",
                "status": "completed",
                "performer": "user_456",
                "timestamp": "2024-01-15T11:00:00Z",
                "comments": "Approved based on evidence",
            },
            {
                "id": "action_2",
                "type": "reject",
                "status": "completed",
                "performer": "user_123",
                "timestamp": "2024-01-15T10:45:00Z",
                "comments": "Rejected - insufficient evidence",
            },
        ],
        "unmask_requests": [
            {
                "id": "unmask_1",
                "status": "approved",
                "requester": "user_789",
                "requester_name": "Jane Smith",
                "requested_at": "2024-01-15T12:00:00Z",
                "approved_at": "2024-01-15T13:30:00Z",
                "approver": "user_456",
                "approval_comments": "Approved - legitimate business reason",
                "access_level": "FULL",
                "data_fields": ["vendor_revenue", "contract_terms"],
            }
        ],
        "permissions": {
            "can_approve": True,
            "can_reject": True,
            "can_escalate": True,
            "can_request_unmask": True,
            "can_view_full_data": True,
            "can_view_audit_trail": True,
        },
        "workflow_state": {
            "stage": "AUDIT",
            "stage_order": 3,
            "current_step": "review_and_approve",
            "next_steps": ["escalate_if_blocked", "approve_or_reject"],
            "deadline": "2024-01-15T18:00:00Z",
            "time_remaining_hours": 12,
        },
    }

    return case_detail


@router.post("/{case_id}/actions")
async def perform_action(
    case_id: str,
    action: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    """Perform an action on a case (approve, reject, escalate)."""
    action_type = action.get("type")
    comments = action.get("comments", "")

    # Validate action
    if action_type not in ["approve", "reject", "escalate"]:
        raise HTTPException(status_code=400, detail=f"Invalid action type: {action_type}")

    # Check permissions (mock)
    if action_type == "escalate":
        # Only Level 2+ can escalate
        pass

    # Create action record
    action_record = {
        "id": f"action_{secrets.token_hex(8)}",
        "type": action_type,
        "status": "completed",
        "performer": "user_456",
        "timestamp": "2024-01-15T11:00:00Z",
        "comments": comments,
    }

    return {
        "status": "success",
        "action": action_record,
        "next_state": "NEXT_STAGE",
        "notifications": [
            {"user_id": "user_123", "message": f"Case {case_id} was {action_type}", "type": "action"},
        ],
    }


@router.get("/{case_id}/actions")
async def get_case_actions(case_id: str, request: Request) -> List[Dict[str, Any]]:
    """Get action history for a case."""
    # Mock data
    return [
        {
            "id": "action_1",
            "type": "approve",
            "status": "completed",
            "performer": "user_456",
            "timestamp": "2024-01-15T11:00:00Z",
            "comments": "Approved based on evidence",
        },
        {
            "id": "action_2",
            "type": "reject",
            "status": "completed",
            "performer": "user_123",
            "timestamp": "2024-01-15T10:45:00Z",
            "comments": "Rejected - insufficient evidence",
        },
    ]


@router.get("/unmask-requests")
async def list_unmask_requests(
    request: Request,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get list of unmask requests for reviewer."""
    # Mock data
    requests = [
        {
            "id": "unmask_1",
            "case_id": "case_1",
            "status": "pending",
            "requester": "user_789",
            "requester_name": "Jane Smith",
            "requested_at": "2024-01-15T12:00:00Z",
            "reason": "Need to access contract terms for compliance review",
            "data_fields": ["vendor_revenue", "contract_terms"],
            "justification": "Legitimate business need",
        },
        {
            "id": "unmask_2",
            "case_id": "case_2",
            "status": "approved",
            "requester": "user_999",
            "requester_name": "Bob Johnson",
            "requested_at": "2024-01-14T14:30:00Z",
            "approved_at": "2024-01-14T16:45:00Z",
            "approver": "user_456",
            "reason": "Investigation requires access to all vendor data",
            "data_fields": ["all"],
            "justification": "Investigative necessity",
        },
    ]

    if status:
        requests = [r for r in requests if r["status"] == status]

    return {
        "requests": requests,
        "total": len(requests),
        "limit": limit,
        "offset": offset,
    }


@router.post("/unmask-requests/{request_id}/approve")
async def approve_unmask_request(
    request_id: str,
    body: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    """Approve an unmask request."""
    # Mock implementation
    return {
        "status": "approved",
        "request_id": request_id,
        "approved_at": "2024-01-15T14:30:00Z",
        "approver": "user_456",
        "approval_comments": body.get("comments", ""),
        "access_expires": "2024-01-16T14:30:00Z",
    }


@router.post("/unmask-requests/{request_id}/reject")
async def reject_unmask_request(
    request_id: str,
    body: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    """Reject an unmask request."""
    # Mock implementation
    return {
        "status": "rejected",
        "request_id": request_id,
        "rejected_at": "2024-01-15T14:30:00Z",
        "rejecter": "user_456",
        "rejection_reason": body.get("rejection_reason", ""),
    }


@router.get("/{case_id}/unmask-status")
async def get_unmask_status(
    case_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Get unmask request status for a case."""
    return {
        "case_id": case_id,
        "has_active_requests": True,
        "active_requests": [
            {
                "id": "unmask_1",
                "status": "approved",
                "access_level": "FULL",
                "data_fields": ["vendor_revenue", "contract_terms"],
                "expires_at": "2024-01-16T14:30:00Z",
            }
        ],
        "can_request_new": False,
    }