"""SQLAlchemy ORM models for GovSpend Nexus backend-api."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import declarative_base

from db import Base


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True)
    transaction_id = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    tier = Column(String, nullable=False)
    status = Column(String, nullable=False)
    confidence_factor = Column(Float, nullable=False, default=0.0)
    weights_version = Column(String, nullable=False, default="1.0")
    department = Column(String, nullable=False, default="")
    vendor_token = Column(String, nullable=False, default="")
    amount = Column(Float, nullable=False, default=0.0)
    transaction_date = Column(DateTime, nullable=False)
    jurisdiction_id = Column(String, nullable=True)
    transaction = Column(JSON, nullable=True)
    vendor = Column(JSON, nullable=True)
    signals = Column(JSON, nullable=True)
    signals_summary = Column(JSON, nullable=True)
    evidence_ids = Column(JSON, nullable=True)
    evidence_summary = Column(JSON, nullable=True)
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    actions = Column(JSON, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False)
    transaction_id = Column(String, nullable=False)
    evidence_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    confidence = Column(Float, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, nullable=False, default=False)
    hash = Column(String, nullable=False, default="")


class Explanation(Base):
    __tablename__ = "explanations"

    case_id = Column(String, primary_key=True)
    transaction_id = Column(String, nullable=False)
    explanations = Column(JSON, nullable=False)
    summary = Column(Text, nullable=False)
    overall_confidence = Column(Float, nullable=False)
    grounding_score = Column(Float, nullable=False)
    evidence_count = Column(Integer, nullable=False)
    policy_count = Column(Integer, nullable=False)
    generated_at = Column(String, nullable=False)
    version = Column(String, nullable=False, default="1.0")


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    size = Column(Integer, nullable=False, default=10)
    color = Column(String, nullable=False, default="#9E9E9E")
    data = Column(JSON, nullable=True)
    node_metadata = Column("metadata", JSON, nullable=True)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    target = Column(String, nullable=False)
    type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    data = Column(JSON, nullable=True)


class UnmaskRequest(Base):
    __tablename__ = "unmask_requests"

    request_id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_token = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    jurisdiction_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    requested_by = Column(String, nullable=False)
    requested_at = Column(DateTime, nullable=False)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    unmasked_data = Column(JSON, nullable=True)


class PolicyWeight(Base):
    __tablename__ = "policy_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String, nullable=False, unique=True)
    weights = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(String, nullable=False)
    description = Column(String, nullable=True)


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    entry_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    sequence = Column(Integer, nullable=False)
    hash = Column(String, nullable=False)
    previous_hash = Column(String, nullable=False)


class AdminUser(Base):
    __tablename__ = "admin_users"

    user_id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    roles = Column(JSON, nullable=False)
    jurisdictions = Column(JSON, nullable=False)


class NexusCase(Base):
    __tablename__ = "nexus_cases"

    case_id = Column(String, primary_key=True)
    institution_id = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    department = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    vendor_token = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_band = Column(String, nullable=False)
    signals = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    pii = Column(JSON, nullable=True)


class NexusInvoice(Base):
    __tablename__ = "nexus_invoices"

    id = Column(String, primary_key=True)
    institution_id = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    tender_reference = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    line_items = Column(JSON, nullable=False)
    pii_tokens = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, nullable=False)


class NexusUnmaskRequest(Base):
    __tablename__ = "nexus_unmask_requests"

    id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False)
    institution_id = Column(String, nullable=False)
    field = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    requested_by = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


class NexusAuditEntry(Base):
    __tablename__ = "nexus_audit_entries"

    id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    comment = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)
