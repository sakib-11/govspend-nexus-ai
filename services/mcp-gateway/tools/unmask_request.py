"""Tool: request_unmask — request unmasking of sensitive data."""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


class UnmaskRequestTool(BaseTool):
    """Create a request to unmask sensitive PII for a specific case."""

    ALLOWED_FIELDS = frozenset({"vendor_name", "vendor_id", "assigned_to", "comment_users"})

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        case_id: str = context.parameters["case_id"]
        fields = context.parameters.get("fields", [])
        justification = context.parameters.get("justification", "")

        # Validate requested fields
        invalid = set(fields) - self.ALLOWED_FIELDS
        if invalid:
            raise ValueError(f"Unmasking not allowed for fields: {', '.join(sorted(invalid))}")

        request_id = f"unmask-{uuid4().hex[:10]}"
        return {
            "request_id": request_id,
            "case_id": case_id,
            "requested_by": context.user_id,
            "fields": fields,
            "justification": justification,
            "status": "pending_approval",
            "requires_approval_by": "auditor_level_3",
            "created_at": "2024-01-16T12:00:00Z",
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("case_id"):
            raise ValueError("case_id is required")
        fields = params.get("fields", [])
        if not fields:
            raise ValueError("fields list is required")
        if not isinstance(fields, list):
            raise ValueError("fields must be a list of strings")
        return params


async def request_unmask(request, context):  # type: ignore[no-untyped-def]
    return await UnmaskRequestTool().handle(request)
