"""Tool: get_case_details — full case details (Level 2+ access)."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class CaseDetailsTool(BaseTool):
    """Return complete case details for elevated-privilege auditors."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        case_id: str = context.parameters["case_id"]
        include_evidence = context.parameters.get("include_evidence", True)
        include_comments = context.parameters.get("include_comments", True)

        case = self._fetch_full_case(case_id)

        if not include_evidence:
            case.pop("evidence", None)
        if not include_comments:
            case.pop("comments", None)

        return {
            "case_id": case_id,
            "case_details": case,
            "access_level": self._highest_role(context),
            "fields_returned": list(case.keys()),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("case_id"):
            raise ValueError("case_id is required")
        return params

    @staticmethod
    def _fetch_full_case(case_id: str) -> Dict[str, Any]:
        return {
            "case_id": case_id,
            "transaction_id": "tx-12345",
            "risk_score": 0.82,
            "risk_tier": "HIGH",
            "status": "under_review",
            "created_at": "2024-01-15T10:30:00Z",
            "assigned_to": "auditor-123",
            "priority": "high",
            "summary": "Suspicious transaction with price deviation",
            "vendor_name": "ABC Corp",
            "vendor_id": "VEND-12345",
            "amount": 15_000.00,
            "department": "IT Department",
            "detectors_triggered": [
                {"name": "price_deviation", "signal": 0.85},
                {"name": "vendor_graph_risk", "signal": 0.70},
            ],
            "evidence": {
                "invoice_number": "INV-00123",
                "invoice_date": "2024-01-10",
                "items": [{"description": "IT Hardware", "quantity": 10, "unit_price": 1_500.00}],
            },
            "comments": [
                {
                    "user": "auditor-123",
                    "timestamp": "2024-01-16T08:00:00Z",
                    "text": "Requires further investigation",
                }
            ],
            "audit_trail": [
                {"event": "created", "by": "system", "at": "2024-01-15T10:30:00Z"},
                {"event": "assigned", "by": "admin-1", "at": "2024-01-15T11:00:00Z"},
            ],
        }

    @staticmethod
    def _highest_role(ctx: ToolExecutionContext) -> str:
        for level in ("super_admin", "admin", "auditor_level_3", "auditor_level_2"):
            if level in ctx.user_roles:
                return level
        return "unknown"


async def get_case_details(request, context):  # type: ignore[no-untyped-def]
    return await CaseDetailsTool().handle(request)
