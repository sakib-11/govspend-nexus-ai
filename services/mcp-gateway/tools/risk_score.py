"""Tool: get_risk_score — risk scoring for transactions."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class RiskScoreTool(BaseTool):
    """Return risk score and contributing factors for a transaction."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        tx_id: str = context.parameters["transaction_id"]
        score_data = self._compute_risk(tx_id)
        return {
            "transaction_id": tx_id,
            "risk_score": score_data,
            "recommendation": self._recommendation(score_data["overall_score"]),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("transaction_id"):
            raise ValueError("transaction_id is required")
        return params

    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk(tx_id: str) -> Dict[str, Any]:
        """Replace with real model inference in production."""
        return {
            "overall_score": 0.82,
            "risk_tier": "HIGH",
            "factors": [
                {"name": "price_deviation", "score": 0.85, "weight": 0.3},
                {"name": "vendor_graph_risk", "score": 0.70, "weight": 0.25},
                {"name": "volume_anomaly", "score": 0.60, "weight": 0.2},
                {"name": "temporal_pattern", "score": 0.45, "weight": 0.15},
                {"name": "geographic_mismatch", "score": 0.30, "weight": 0.1},
            ],
            "model_version": "2.1.0",
            "calculated_at": "2024-01-15T10:30:00Z",
        }

    @staticmethod
    def _recommendation(score: float) -> str:
        if score >= 0.8:
            return "immediate_investigation"
        if score >= 0.6:
            return "flag_for_review"
        if score >= 0.4:
            return "monitor"
        return "no_action"


async def get_risk_score(request, context):  # type: ignore[no-untyped-def]
    return await RiskScoreTool().handle(request)
