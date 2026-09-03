"""Tool: get_transaction — retrieve masked transaction details."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class TransactionTool(BaseTool):
    """Return transaction details with role-based masking."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        tx_id: str = context.parameters["transaction_id"]
        tx = self._fetch_transaction(tx_id, context)
        return {
            "transaction_id": tx_id,
            "transaction": tx,
            "masking_applied": self._is_masked(context),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("transaction_id"):
            raise ValueError("transaction_id is required")
        return params

    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_transaction(tx_id: str, ctx: ToolExecutionContext) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "transaction_id": tx_id,
            "amount": 15_000.00,
            "currency": "USD",
            "date": "2024-01-15",
            "status": "completed",
            "risk_score": 0.82,
            "vendor_name": "ABC Corp",
            "vendor_id": "VEND-12345",
            "department": "IT Department",
            "description": "IT Hardware purchase",
            "payment_method": "wire_transfer",
            "account_number": "****7890",
        }
        # Level 3+ sees unmasked data
        if not any(r in ctx.user_roles for r in ("auditor_level_3", "admin", "super_admin")):
            base["vendor_name"] = "A** C**"
            base["vendor_id"] = "VEND-***45"
            base["account_number"] = "****7890"
        return base

    @staticmethod
    def _is_masked(ctx: ToolExecutionContext) -> bool:
        return not any(
            r in ctx.user_roles for r in ("auditor_level_3", "admin", "super_admin")
        )


async def get_transaction(request, context):  # type: ignore[no-untyped-def]
    return await TransactionTool().handle(request)
