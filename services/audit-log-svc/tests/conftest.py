"""Shared fixtures for audit logging tests."""

from __future__ import annotations

import pytest

from models.audit import (
    AuditEntry,
    AuditEventType,
    AuditSeverity,
)
from services.hash_chain_manager import HashChainManager
from services.audit_logger import AuditLogger
from services.audit_verifier import AuditVerifier
from services.audit_retriever import AuditRetriever
from services.tamper_detector import TamperDetector


@pytest.fixture()
def chain_manager() -> HashChainManager:
    return HashChainManager(salt="test-salt")


@pytest.fixture()
def audit_logger(chain_manager: HashChainManager) -> AuditLogger:
    return AuditLogger(chain_manager, async_logging=False)


@pytest.fixture()
def audit_verifier(chain_manager: HashChainManager) -> AuditVerifier:
    return AuditVerifier(chain_manager)


@pytest.fixture()
def audit_retriever(chain_manager: HashChainManager) -> AuditRetriever:
    return AuditRetriever(chain_manager)


@pytest.fixture()
def tamper_detector(audit_verifier: AuditVerifier) -> TamperDetector:
    return TamperDetector(audit_verifier)


@pytest.fixture()
def sample_entry() -> AuditEntry:
    return AuditEntry(
        event_type=AuditEventType.MCP_TOOL_CALL,
        user_id="test-user-001",
        user_roles=["auditor_level_1"],
        user_jurisdictions=["federal"],
        resource_type="tool",
        resource_id="get_invoice_evidence",
        action="execute",
        request_id="req-001",
        severity=AuditSeverity.INFO,
    )
