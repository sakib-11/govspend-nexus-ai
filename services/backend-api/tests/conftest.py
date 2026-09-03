"""Shared test fixtures for Backend API."""

import sys
import os

# Ensure the service directory is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from models.case import CaseAction, CaseFilter, CaseStatus, CaseTier
from services.case_service import CaseService
from services.evidence_service import EvidenceService
from services.explanation_service import ExplanationService
from services.graph_service import GraphService
from services.unmask_service import UnmaskService
from services.admin_service import AdminService


@pytest.fixture()
def case_service():
    svc = CaseService()
    svc.seed_demo_data()
    return svc


@pytest.fixture()
def evidence_service():
    svc = EvidenceService()
    svc.seed_demo_data()
    return svc


@pytest.fixture()
def explanation_service():
    return ExplanationService()


@pytest.fixture()
def graph_service():
    svc = GraphService()
    svc.seed_demo_data()
    return svc


@pytest.fixture()
def unmask_service():
    return UnmaskService()


@pytest.fixture()
def admin_service():
    svc = AdminService()
    svc.seed_demo_data()
    return svc
