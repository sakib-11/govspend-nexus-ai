"""Centralised tool registry for all MCP tools."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from models.mcp import (
    MCPTool,
    ToolAccessLevel,
    ToolCategory,
    user_has_access_level,
)

logger = logging.getLogger(__name__)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


class ToolRegistry:
    """In-memory registry that holds tool definitions, handler references,
    and JSON schemas.

    The registry is deliberately stateless (no DB) so it can be created
    at import time and hydrated during application startup.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._initialised = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialise(self) -> None:
        """Register the built-in tool definitions.  Idempotent."""
        if self._initialised:
            return
        for tool in self._builtin_tools():
            self.register_tool(tool)
        self._initialised = True
        logger.info("ToolRegistry initialised with %d tools", len(self._tools))

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_tool(self, tool: MCPTool) -> None:
        """Register (or overwrite) a tool definition."""
        self._tools[tool.name] = tool

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """Bind a callable handler to a tool name."""
        self._handlers[tool_name] = handler

    # ------------------------------------------------------------------
    # Look-ups
    # ------------------------------------------------------------------

    def get_tool(self, name: str) -> Optional[MCPTool]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[MCPTool]:
        return list(self._tools.values())

    def get_tools_by_category(self, category: ToolCategory) -> List[MCPTool]:
        return [t for t in self._tools.values() if t.category == category]

    def get_tools_by_access(self, level: ToolAccessLevel) -> List[MCPTool]:
        return [t for t in self._tools.values() if t.access_level == level]

    def get_handler(self, tool_name: str) -> Optional[Callable]:
        return self._handlers.get(tool_name)

    def get_accessible_tools(self, user_roles: List[str]) -> List[MCPTool]:
        """Return tools the user can access based on their role list."""
        return [
            t
            for t in self._tools.values()
            if t.is_active and user_has_access_level(user_roles, t.access_level)
        ]

    def get_schema(self, tool_name: str) -> Dict[str, Any]:
        tool = self.get_tool(tool_name)
        if tool is None:
            return {}
        return {"input_schema": tool.input_schema, "output_schema": tool.output_schema}

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def load_schema(self, name: str) -> Dict[str, Any]:
        """Load a named JSON schema from the schemas directory."""
        if name in self._schema_cache:
            return self._schema_cache[name]

        path = _SCHEMAS_DIR / f"{name}.schema.json"
        if path.exists():
            with open(path) as fh:
                data = json.load(fh)
            self._schema_cache[name] = data
            return data

        # Fallback: permissive schema
        fallback: Dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": True}
        self._schema_cache[name] = fallback
        return fallback

    # ------------------------------------------------------------------
    # Built-in tool definitions
    # ------------------------------------------------------------------

    @staticmethod
    def _builtin_tools() -> List[MCPTool]:
        """Return the canonical set of MCP tools."""
        _load = lambda n: _load_schema_file(n)  # noqa: E731

        return [
            MCPTool(
                name="get_invoice_evidence",
                description="Retrieve invoice evidence for a transaction with masking",
                category=ToolCategory.EVIDENCE,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_1,
                input_schema=_load("invoice_evidence_input"),
                output_schema=_load("invoice_evidence_output"),
                handler="tools.invoice_evidence.get_invoice_evidence",
                timeout_seconds=15,
                tags=["evidence", "invoice", "transaction"],
            ),
            MCPTool(
                name="benchmark_price",
                description="Get price benchmarks for a category/region",
                category=ToolCategory.BENCHMARK,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_1,
                input_schema=_load("benchmark_price_input"),
                output_schema=_load("benchmark_price_output"),
                handler="tools.benchmark_price.benchmark_price",
                timeout_seconds=10,
                tags=["benchmark", "price", "analysis"],
            ),
            MCPTool(
                name="get_masked_case",
                description="Retrieve case details with PII masked",
                category=ToolCategory.CASE,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_1,
                input_schema=_load("masked_case_input"),
                output_schema=_load("masked_case_output"),
                handler="tools.masked_case.get_masked_case",
                timeout_seconds=10,
                tags=["case", "masked", "pii"],
            ),
            MCPTool(
                name="get_case_details",
                description="Get full case details with evidence (requires Level 2+)",
                category=ToolCategory.CASE,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_2,
                input_schema=_load("case_details_input"),
                output_schema=_load("case_details_output"),
                handler="tools.case_details.get_case_details",
                timeout_seconds=15,
                tags=["case", "details", "evidence"],
            ),
            MCPTool(
                name="request_unmask",
                description="Request unmasking of sensitive data",
                category=ToolCategory.UNMASK,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_2,
                input_schema=_load("unmask_request_input"),
                output_schema=_load("unmask_request_output"),
                handler="tools.unmask_request.request_unmask",
                timeout_seconds=5,
                tags=["unmask", "request", "pii"],
            ),
            MCPTool(
                name="approve_unmask",
                description="Approve an unmasking request (Level 3+ only)",
                category=ToolCategory.UNMASK,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_3,
                input_schema=_load("approve_unmask_input"),
                output_schema=_load("approve_unmask_output"),
                handler="tools.approve_unmask.approve_unmask",
                timeout_seconds=10,
                tags=["unmask", "approve", "pii"],
            ),
            MCPTool(
                name="execute_action",
                description="Execute a pre-approved action on a case",
                category=ToolCategory.EXECUTION,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_2,
                input_schema=_load("execute_action_input"),
                output_schema=_load("execute_action_output"),
                handler="tools.execute_action.execute_action",
                timeout_seconds=30,
                tags=["execute", "action", "case"],
            ),
            MCPTool(
                name="get_transaction",
                description="Get transaction details (masked)",
                category=ToolCategory.EVIDENCE,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_1,
                input_schema=_load("transaction_input"),
                output_schema=_load("transaction_output"),
                handler="tools.transaction.get_transaction",
                timeout_seconds=10,
                tags=["transaction", "details"],
            ),
            MCPTool(
                name="get_risk_score",
                description="Get risk score and details for a transaction",
                category=ToolCategory.EVIDENCE,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_1,
                input_schema=_load("risk_score_input"),
                output_schema=_load("risk_score_output"),
                handler="tools.risk_score.get_risk_score",
                timeout_seconds=10,
                tags=["risk", "score", "analysis"],
            ),
            MCPTool(
                name="get_audit_trail",
                description="Get audit trail for a transaction or case",
                category=ToolCategory.AUDIT,
                access_level=ToolAccessLevel.AUDITOR_LEVEL_2,
                input_schema=_load("audit_trail_input"),
                output_schema=_load("audit_trail_output"),
                handler="tools.audit_trail.get_audit_trail",
                timeout_seconds=20,
                tags=["audit", "trail", "history"],
            ),
        ]


def _load_schema_file(schema_name: str) -> Dict[str, Any]:
    """Attempt to load *schema_name*.schema.json; return a permissive fallback."""
    path = _SCHEMAS_DIR / f"{schema_name}.schema.json"
    if path.exists():
        with open(path) as fh:
            return json.load(fh)
    return {"type": "object", "properties": {}, "additionalProperties": True}
