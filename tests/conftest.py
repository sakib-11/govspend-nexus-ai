"""Shared test fixtures for integration, security, and performance tests."""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is available for top-level packages
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add service-specific directories FIRST so they take precedence
# over the top-level `services` package
_service_dirs = [
    "services/digital-twin-svc",
    "services/explanation-svc",
    "services/llm-prompt-svc",
    "services/unmask-svc",
    "services/masked-evidence-svc",
    "services/rag-retriever-svc",
    "services/audit-log-svc",
]
for _svc in _service_dirs:
    _full = os.path.join(PROJECT_ROOT, _svc)
    if os.path.isdir(_full) and _full not in sys.path:
        sys.path.insert(0, _full)


# ── Event loop ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Sample data ──────────────────────────────────────────────────


@pytest.fixture
def sample_transaction() -> Dict[str, Any]:
    """Sample transaction data."""
    return {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "invoice_doc_hash": "a" * 64,
        "vendor_token": "VEND-ABC123",
        "department_id": "DEPT-001",
        "amount": 125000.00,
        "unit_price": 2500.00,
        "quantity": 50,
        "category": "office_supplies",
        "region": "MH-07",
        "submitted_at": "2024-01-15T10:30:00",
        "source": "Manual",
    }


@pytest.fixture
def sample_signal() -> Dict[str, Any]:
    """Sample signal data."""
    return {
        "detector_type": "price_deviation",
        "signal_value": 0.85,
        "confidence": 0.92,
        "evidence_ids": ["EV-001", "EV-002"],
    }


@pytest.fixture
def sample_case() -> Dict[str, Any]:
    """Sample case data."""
    return {
        "case_id": "CASE-001",
        "transaction_id": "TX-001",
        "risk_score": 0.85,
        "risk_tier": "HIGH",
        "status": "OPEN",
        "department_id": "DEPT-001",
        "vendor_token": "VEND-001",
        "created_at": "2024-01-15T10:30:00",
    }


@pytest.fixture
def sample_evidence_bundle() -> Dict[str, Any]:
    """Sample evidence bundle."""
    return {
        "evidence": [
            {"id": "EV-001", "type": "invoice", "description": "Unit price 50% above market"},
            {"id": "EV-002", "type": "comparison", "description": "Similar transactions in 90 days"},
        ]
    }


@pytest.fixture
def sample_policies() -> list:
    """Sample policy references."""
    return [
        {"policy_id": "GFR-4.3", "title": "Government Financial Rules", "content": "Procurement at market rates"},
        {"policy_id": "GFR-9.1", "title": "Approval Requirements", "content": "Adequate review time"},
    ]


@pytest.fixture
def sample_llm_input() -> Dict[str, Any]:
    """Sample LLM input for explanation generation."""
    return {
        "case_id": "CASE-001",
        "transaction_id": "TX-001",
        "risk_score": 0.85,
        "risk_tier": "HIGH",
        "evidence_bundle": {
            "evidence": [
                {"id": "EV-001", "description": "Unit price above market"},
            ]
        },
        "retrieved_policies": [
            {"policy_id": "GFR-4.3", "title": "GFR", "content": "Market rates"}
        ],
        "signals": [
            {"detector_type": "price_deviation", "signal_value": 0.9, "confidence": 0.95, "evidence_ids": ["EV-001"]}
        ],
    }


@pytest.fixture
def sample_llm_output() -> Dict[str, Any]:
    """Sample LLM output for validation."""
    return {
        "summary": "Significant risk indicators detected with price deviation above market rates.",
        "confidence": 0.92,
        "explanations": [
            {
                "point_number": 1,
                "detector_name": "price_deviation",
                "sentence": "The invoice unit price exceeds historical market benchmarks by 50%.",
                "confidence": 0.95,
                "evidence_ids": ["EV-001"],
                "policy_references": ["GFR-4.3"],
                "citations": [
                    {
                        "citation_type": "evidence",
                        "reference_id": "EV-001",
                        "reference_text": "Unit price above market",
                        "relevance_score": 0.95,
                    }
                ],
            }
        ],
        "grounding_score": 1.0,
        "citations_used": 1,
    }


@pytest.fixture
def sample_vendor() -> Dict[str, Any]:
    """Sample vendor graph request."""
    return {
        "vendor_token": "VEND-12345",
        "name_masked": "Vendor Masked Name",
        "total_transactions": 10,
        "total_amount": 500000.00,
    }


@pytest.fixture
def sample_official() -> Dict[str, Any]:
    """Sample official graph data."""
    return {
        "official_id": "OFF-001",
        "name_masked": "Official Masked Name",
        "department": "DEPT-001",
    }


# ── Mock DB pool ─────────────────────────────────────────────────


class MockRecord:
    """Simulates asyncpg Record objects."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getitem__(self, key):
        return self._data.get(key)

    def get(self, key, default=None):
        return self._data.get(key, default)


class MockConnection:
    """Simulates an asyncpg connection."""

    def __init__(self, records=None):
        self.records = records or []

    async def fetch(self, query, *args):
        return [MockRecord(r) for r in self.records]

    async def fetchrow(self, query, *args):
        return MockRecord(self.records[0]) if self.records else None

    async def execute(self, query, *args):
        return "INSERT 0 1"


class MockPool:
    """Simulates an asyncpg connection pool."""

    def __init__(self, records=None):
        self._records = records or []

    def acquire(self):
        return MockConnectionContext(self._records)

    async def close(self):
        pass


class MockConnectionContext:
    def __init__(self, records):
        self._records = records

    async def __aenter__(self):
        return MockConnection(self._records)

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_db_pool():
    """Mock database pool."""
    return MockPool()


# ── Mock Redis ───────────────────────────────────────────────────


class MockRedis:
    """Simplified async Redis mock."""

    def __init__(self):
        self._data: Dict[str, str] = {}
        self._expires: Dict[str, float] = {}

    async def get(self, key):
        return self._data.get(key)

    async def setex(self, key, ttl, value):
        import time
        self._data[key] = value
        self._expires[key] = time.time() + ttl

    async def set(self, key, value):
        self._data[key] = value

    async def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)
            self._expires.pop(k, None)

    async def keys(self, pattern):
        import fnmatch
        return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

    async def close(self):
        pass


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MockRedis()


# ── User fixtures ────────────────────────────────────────────────


@pytest.fixture
def auditor_user() -> Dict[str, Any]:
    """Auditor role user."""
    return {
        "user_id": "user-auditor-1",
        "username": "test_auditor",
        "role": "auditor",
        "jurisdictions": ["MH", "KA"],
        "is_super_admin": False,
    }


@pytest.fixture
def admin_user() -> Dict[str, Any]:
    """Admin role user."""
    return {
        "user_id": "user-admin-1",
        "username": "admin",
        "role": "admin",
        "jurisdictions": ["ALL"],
        "is_super_admin": True,
    }


@pytest.fixture
def viewer_user() -> Dict[str, Any]:
    """Viewer role user."""
    return {
        "user_id": "user-viewer-1",
        "username": "viewer",
        "role": "viewer",
        "jurisdictions": ["MH"],
        "is_super_admin": False,
    }
