"""MCPServer — thin façade that ties the registry, executor, and protocol together."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from models.mcp import MCPRequest, MCPResponse
from tools.registry import ToolRegistry
from services.tool_executor import ToolExecutor
from services.audit_service import AuditService
from mcp.protocol import MCPProtocol

logger = logging.getLogger(__name__)


class MCPServer:
    """Facade that owns the tool lifecycle for a single FastAPI app instance."""

    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.audit_service = AuditService()
        self.executor = ToolExecutor(self.registry, None)
        self._protocol = MCPProtocol()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialise(self) -> None:
        """Register built-in tools and bind handlers."""
        self.registry.initialise()
        self._register_handlers()
        self.executor = ToolExecutor(self.registry, None)
        logger.info("MCPServer initialised (%d tools)", len(self.registry.get_all_tools()))

    def _register_handlers(self) -> None:
        """Import and register all tool handler callables."""
        from tools import (
            invoice_evidence,
            benchmark_price,
            masked_case,
            case_details,
            unmask_request,
            approve_unmask,
            execute_action,
            transaction,
            risk_score,
            audit_trail,
        )

        handler_map = {
            "get_invoice_evidence": invoice_evidence.get_invoice_evidence,
            "benchmark_price": benchmark_price.benchmark_price,
            "get_masked_case": masked_case.get_masked_case,
            "get_case_details": case_details.get_case_details,
            "request_unmask": unmask_request.request_unmask,
            "approve_unmask": approve_unmask.approve_unmask,
            "execute_action": execute_action.execute_action,
            "get_transaction": transaction.get_transaction,
            "get_risk_score": risk_score.get_risk_score,
            "get_audit_trail": audit_trail.get_audit_trail,
        }
        for name, fn in handler_map.items():
            self.registry.register_handler(name, fn)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        request: MCPRequest,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        """Run a tool and return a serialisable response."""
        return await self.executor.execute(request, context or {})

    async def execute_from_json(
        self,
        raw: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse a raw JSON dict, execute the tool, and return a dict."""
        request = self._protocol.parse_request(raw)
        response = await self.execute(request, context)
        return self._protocol.format_response(response)
