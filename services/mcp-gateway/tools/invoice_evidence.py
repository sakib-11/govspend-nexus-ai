"""Tool: get_invoice_evidence — retrieve invoice evidence for a transaction."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class InvoiceEvidenceTool(BaseTool):
    """Retrieve invoice evidence for a transaction with role-based masking."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        tx_id: str = context.parameters["transaction_id"]
        evidence = self._build_evidence(tx_id, context)
        return {
            "transaction_id": tx_id,
            "invoice_evidence": evidence,
            "masking_applied": True,
            "data_quality": self._assess_quality(evidence),
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tx_id = params.get("transaction_id")
        if not tx_id or not isinstance(tx_id, str):
            raise ValueError("transaction_id is required and must be a non-empty string")
        return params

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_evidence(self, tx_id: str, ctx: ToolExecutionContext) -> Dict[str, Any]:
        """Produce evidence dict.  Replace with DB call in production."""
        return {
            "invoice_number": f"INV-{tx_id[-6:]}",
            "invoice_date": "2024-01-15",
            "amount": 15_000.00,
            "currency": "USD",
            "vendor_name": self._mask_text("ABC Corp", ctx),
            "vendor_id": f"VEND-{'12345'}",
            "items": [
                {
                    "description": "IT Hardware",
                    "quantity": 10,
                    "unit_price": 1_500.00,
                    "total": 15_000.00,
                }
            ],
            "status": "verified",
            "confidence_score": 0.95,
            "extraction_method": "OCR + AI",
        }

    def _mask_text(self, text: str, ctx: ToolExecutionContext) -> str:
        """Mask text for lower-privilege users."""
        if "auditor_level_2" in ctx.user_roles or "auditor_level_3" in ctx.user_roles:
            return text
        if "admin" in ctx.user_roles or "super_admin" in ctx.user_roles:
            return text
        parts = text.split()
        if len(parts) > 1:
            return f"{parts[0][0]}*** {parts[-1][0]}***"
        return f"{text[:2]}***" if len(text) > 2 else "***"

    @staticmethod
    def _assess_quality(evidence: Dict[str, Any]) -> Dict[str, Any]:
        required = ("invoice_number", "invoice_date", "amount", "vendor_name")
        issues = [f"Missing {f}" for f in required if not evidence.get(f)]
        score = max(0.0, 1.0 - 0.1 * len(issues))
        return {
            "overall": round(score, 2),
            "fields_complete": len(issues) == 0,
            "confidence": evidence.get("confidence_score", 0.0),
            "issues": issues,
        }


# Module-level handler expected by the registry ---------------------------------

async def get_invoice_evidence(request, context):  # type: ignore[no-untyped-def]
    """Convenience wrapper used by :class:`ToolRegistry`."""
    return await InvoiceEvidenceTool().handle(request)
