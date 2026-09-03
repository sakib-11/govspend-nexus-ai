"""Tool: get_masked_case — case details with role-based PII masking."""

from __future__ import annotations

from typing import Any, Dict, List

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class MaskedCaseTool(BaseTool):
    """Return case data with PII masked according to the caller's role."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        case_id: str = context.parameters["case_id"]
        raw_case = self._fetch_case(case_id)
        masked = self._apply_masking(raw_case, context)
        return {
            "case_id": case_id,
            "case_data": masked,
            "masking_level": self._masking_level(context),
            "viewable_fields": list(masked.keys()),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("case_id"):
            raise ValueError("case_id is required")
        return params

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_case(case_id: str) -> Dict[str, Any]:
        """Mock case data.  Replace with DB call in production."""
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
                    "text": "This requires further investigation",
                }
            ],
        }

    # Masking ------------------------------------------------------------------

    def _apply_masking(self, case: Dict[str, Any], ctx: ToolExecutionContext) -> Dict[str, Any]:
        level = self._masking_level(ctx)

        if level == "full":
            return dict(case)
        if level == "partial":
            masked = dict(case)
            for key in ("vendor_name", "vendor_id", "assigned_to"):
                if key in masked:
                    masked[key] = self._mask(masked[key])
            for comment in masked.get("comments", []):
                if "user" in comment:
                    comment["user"] = self._mask(comment["user"])
            return masked

        # minimal
        return {
            "case_id": case["case_id"],
            "risk_score": case["risk_score"],
            "risk_tier": case["risk_tier"],
            "status": case["status"],
            "summary": case["summary"],
            "amount": case["amount"],
        }

    def _masking_level(self, ctx: ToolExecutionContext) -> str:
        roles = set(ctx.user_roles)
        if "auditor_level_3" in roles or "admin" in roles or "super_admin" in roles:
            return "full"
        if "auditor_level_2" in roles:
            return "partial"
        return "minimal"

    @staticmethod
    def _mask(text: str) -> str:
        if len(text) <= 4:
            return "*" * len(text)
        return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"


async def get_masked_case(request, context):  # type: ignore[no-untyped-def]
    return await MaskedCaseTool().handle(request)
