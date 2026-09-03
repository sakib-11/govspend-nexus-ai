"""Tool: approve_unmask — approve an unmasking request (Level 3+ only)."""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class ApproveUnmaskTool(BaseTool):
    """Approve (or deny) a pending unmask request."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        unmask_request_id: str = context.parameters["unmask_request_id"]
        approved: bool = context.parameters.get("approved", True)
        comment = context.parameters.get("comment", "")

        status = "approved" if approved else "denied"

        return {
            "unmask_request_id": unmask_request_id,
            "approved_by": context.user_id,
            "approved": approved,
            "status": status,
            "comment": comment,
            "processed_at": "2024-01-16T14:00:00Z",
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("unmask_request_id"):
            raise ValueError("unmask_request_id is required")
        return params


async def approve_unmask(request, context):  # type: ignore[no-untyped-def]
    return await ApproveUnmaskTool().handle(request)
