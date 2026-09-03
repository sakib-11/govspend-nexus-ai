"""MCP core models for the Gateway & Tools API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ToolCategory(str, Enum):
    """Tool categories for organizing MCP tools."""

    EVIDENCE = "evidence"
    BENCHMARK = "benchmark"
    CASE = "case"
    UNMASK = "unmask"
    EXECUTION = "execution"
    AUDIT = "audit"
    SYSTEM = "system"


class ToolAccessLevel(str, Enum):
    """Tool access levels — ordered from least to most privileged."""

    PUBLIC = "public"
    AUTHENTICATED = "auth"
    AUDITOR_LEVEL_1 = "auditor_level_1"
    AUDITOR_LEVEL_2 = "auditor_level_2"
    AUDITOR_LEVEL_3 = "auditor_level_3"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Ordered hierarchy for access-level escalation checks
_ACCESS_LEVEL_ORDER: dict[ToolAccessLevel, int] = {
    ToolAccessLevel.PUBLIC: 0,
    ToolAccessLevel.AUTHENTICATED: 1,
    ToolAccessLevel.AUDITOR_LEVEL_1: 2,
    ToolAccessLevel.AUDITOR_LEVEL_2: 3,
    ToolAccessLevel.AUDITOR_LEVEL_3: 4,
    ToolAccessLevel.ADMIN: 5,
    ToolAccessLevel.SUPER_ADMIN: 6,
}


def user_has_access_level(user_roles: List[str], required: ToolAccessLevel) -> bool:
    """Return ``True`` when *user_roles* satisfy the *required* access level.

    A ``super_admin`` role always satisfies any level.
    """
    if ToolAccessLevel.SUPER_ADMIN.value in user_roles:
        return True
    required_idx = _ACCESS_LEVEL_ORDER[required]
    for role in user_roles:
        try:
            level = ToolAccessLevel(role)
        except ValueError:
            continue
        if _ACCESS_LEVEL_ORDER[level] >= required_idx:
            return True
    return False


class MCPTool(BaseModel):
    """MCP Tool definition — the canonical record of a tool."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        validate_assignment=True,
    )

    tool_id: str = Field(default_factory=lambda: f"tool-{uuid4().hex[:12]}")
    name: str
    description: str
    category: ToolCategory
    access_level: ToolAccessLevel

    # JSON Schema dicts for input / output validation
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)

    # Execution hints
    handler: str  # dotted path, e.g. "tools.invoice_evidence.get_invoice_evidence"
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=3, ge=0, le=10)

    # Metadata
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Status
    is_active: bool = True
    is_deprecated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MCPRequest(BaseModel):
    """Incoming request to execute an MCP tool."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:12]}")
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)

    # Execution options
    async_execution: bool = False
    return_full_response: bool = False

    # Authentication (set by middleware before handler sees it)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    jurisdictions: List[str] = Field(default_factory=list)


class MCPResponse(BaseModel):
    """Standard response from an MCP tool execution."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    request_id: str
    tool_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

    execution_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Audit linkage
    audit_id: Optional[str] = None


class MCPToolExecution(BaseModel):
    """Immutable record of a single tool execution."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    execution_id: str = Field(default_factory=lambda: f"exec-{uuid4().hex[:12]}")
    request_id: str
    tool_name: str
    user_id: str
    parameters: Dict[str, Any]
    context: Dict[str, Any]
    status: str = "pending"  # pending | running | completed | failed

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class ToolSchema(BaseModel):
    """Tool schema definition (input + output + examples)."""

    schema_id: str = Field(default_factory=lambda: f"sch-{uuid4().hex[:8]}")
    tool_name: str
    version: str = "1.0.0"
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    validation_rules: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionContext(BaseModel):
    """Context object threaded through every tool execution."""

    user_id: str
    user_roles: List[str] = Field(default_factory=list)
    user_jurisdictions: List[str] = Field(default_factory=list)
    session_id: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: str = ""
    tool_name: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
