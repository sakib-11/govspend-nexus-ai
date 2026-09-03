"""Tool: get_audit_trail — audit trail for transactions or cases."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class AuditTrailTool(BaseTool):
    """Return the audit trail for a given entity (transaction or case)."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        entity_type = context.parameters.get("entity_type", "transaction")
        entity_id: str = context.parameters["entity_id"]
        limit = context.parameters.get("limit", 50)

        trail = self._fetch_trail(entity_type, entity_id)
        paginated = trail[:limit]

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "audit_trail": paginated,
            "total_events": len(trail),
            "returned_events": len(paginated),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("entity_id"):
            raise ValueError("entity_id is required")
        entity_type = params.get("entity_type", "transaction")
        if entity_type not in ("transaction", "case"):
            raise ValueError("entity_type must be 'transaction' or 'case'")
        return params

    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_trail(entity_type: str, entity_id: str) -> list[Dict[str, Any]]:
        """Replace with real DB query in production."""
        return [
            {
                "event_id": f"evt-{i:04d}",
                "event_type": event,
                "actor": actor,
                "timestamp": f"2024-01-{15 + i:02d}T{10 + i}:00:00Z",
                "details": {},
            }
            for i, (event, actor) in enumerate(
                [
                    ("created", "system"),
                    ("assigned", "admin-1"),
                    ("evidence_uploaded", "auditor-123"),
                    ("risk_score_updated", "system"),
                    ("comment_added", "auditor-456"),
                    ("status_changed", "auditor-123"),
                ],
                start=1,
            )
        ]


async def get_audit_trail(request, context):  # type: ignore[no-untyped-def]
    return await AuditTrailTool().handle(request)
