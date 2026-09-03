"""Tool: execute_action — execute a pre-approved action on a case."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from tools.base import BaseTool
from models.mcp import ToolExecutionContext


_ALLOWED_ACTIONS = frozenset({"assign", "escalate", "close", "reject", "request_review"})


class ExecuteActionTool(BaseTool):
    """Execute a pre-approved action on a case (Level 2+)."""

    async def execute(self, context: ToolExecutionContext) -> Dict[str, Any]:
        case_id: str = context.parameters["case_id"]
        action: str = context.parameters["action"]
        reason: str = context.parameters.get("reason", "No reason provided")

        if action not in _ALLOWED_ACTIONS:
            raise ValueError(
                f"Action '{action}' is not pre-approved. Allowed: {', '.join(sorted(_ALLOWED_ACTIONS))}"
            )

        details = self._action_details(action, reason, context)
        now = datetime.now(timezone.utc).isoformat()

        return {
            "case_id": case_id,
            "action": action,
            "status": "completed",
            "result": {
                "action": action,
                "executed_by": context.user_id,
                "reason": reason,
                "details": details,
            },
            "timestamp": now,
            "action_id": str(uuid4()),
        }

    async def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not params.get("case_id"):
            raise ValueError("case_id is required")
        if not params.get("action"):
            raise ValueError("action is required")
        return params

    # ------------------------------------------------------------------

    @staticmethod
    def _action_details(action: str, reason: str, ctx: ToolExecutionContext) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        if action == "assign":
            return {"assigned_to": f"auditor-{uuid4().hex[:8]}", "assigned_at": now}
        if action == "escalate":
            return {"escalation_level": "level_2", "escalated_at": now}
        if action == "close":
            return {"closed_at": now, "resolution": "Investigation completed"}
        if action == "reject":
            return {"rejected_at": now, "rejection_reason": reason}
        if action == "request_review":
            return {"review_requested_at": now, "review_priority": "high"}
        return {}


async def execute_action(request, context):  # type: ignore[no-untyped-def]
    return await ExecuteActionTool().handle(request)
