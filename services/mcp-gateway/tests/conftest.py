"""Shared fixtures for MCP Gateway tests."""

from __future__ import annotations

import pytest

from models.mcp import (
    MCPRequest,
    MCPTool,
    ToolAccessLevel,
    ToolCategory,
    ToolExecutionContext,
)
from tools.registry import ToolRegistry
from services.tool_executor import ToolExecutor
from services.schema_validator import SchemaValidator
from services.audit_service import AuditService


@pytest.fixture()
def tool_registry() -> ToolRegistry:
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

    registry = ToolRegistry()
    registry.initialise()

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
        registry.register_handler(name, fn)

    return registry


@pytest.fixture()
def schema_validator() -> SchemaValidator:
    return SchemaValidator()


@pytest.fixture()
def tool_executor(tool_registry: ToolRegistry, schema_validator: SchemaValidator) -> ToolExecutor:
    return ToolExecutor(tool_registry, schema_validator)


@pytest.fixture()
def audit_service() -> AuditService:
    return AuditService()


@pytest.fixture()
def sample_request() -> MCPRequest:
    return MCPRequest(
        tool_name="get_invoice_evidence",
        parameters={"transaction_id": "tx-12345"},
        user_id="test-user",
        session_id="sess-001",
        context={"roles": ["auditor_level_1"], "jurisdictions": ["federal"]},
    )


@pytest.fixture()
def level2_request() -> MCPRequest:
    return MCPRequest(
        tool_name="get_case_details",
        parameters={"case_id": "case-001"},
        user_id="auditor-2",
        session_id="sess-002",
        context={"roles": ["auditor_level_2"], "jurisdictions": ["federal"]},
    )


@pytest.fixture()
def level3_request() -> MCPRequest:
    return MCPRequest(
        tool_name="approve_unmask",
        parameters={"unmask_request_id": "unmask-001", "approved": True},
        user_id="auditor-3",
        session_id="sess-003",
        context={"roles": ["auditor_level_3"], "jurisdictions": ["federal"]},
    )


@pytest.fixture()
def execution_context() -> ToolExecutionContext:
    return ToolExecutionContext(
        user_id="test-user",
        user_roles=["auditor_level_1"],
        user_jurisdictions=["federal"],
        session_id="sess-001",
        request_id="req-test-001",
        tool_name="get_invoice_evidence",
        parameters={"transaction_id": "tx-12345"},
    )
