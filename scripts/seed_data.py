#!/usr/bin/env python3
"""Seed data script for GovSpend Nexus AI.

Creates sample vendors, officials, departments, and relationships
for development, staging, and production testing.

Usage:
    python scripts/seed_data.py --env production
    python scripts/seed_data.py --clear   # Clear and re-seed
"""

import sys
import os
import argparse

# Add service paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for svc in [
    "services/digital-twin-svc",
    "services/unmask-svc",
    "services/masked-evidence-svc",
]:
    path = os.path.join(PROJECT_ROOT, svc)
    if os.path.exists(path):
        sys.path.insert(0, path)

try:
    from services.graph_service import GraphService
    from services.twin_service import TwinService
    HAS_SERVICES = True
except ImportError:
    HAS_SERVICES = False

# ── Sample data ──────────────────────────────────────────────────

VENDORS = [
    ("VEND-001", "Alpha Supplies Pvt Ltd"),
    ("VEND-002", "Beta Infrastructure Corp"),
    ("VEND-003", "Gamma Tech Solutions"),
    ("VEND-004", "Delta Procurement Services"),
    ("VEND-005", "Epsilon Construction Ltd"),
    ("VEND-006", "Zeta Office Solutions"),
    ("VEND-007", "Eta Medical Supplies"),
    ("VEND-008", "Theta IT Services"),
]

OFFICIALS = [
    ("OFF-001", "Official Alpha"),
    ("OFF-002", "Official Beta"),
    ("OFF-003", "Official Gamma"),
    ("OFF-004", "Official Delta"),
    ("OFF-005", "Official Epsilon"),
]

DEPARTMENTS = [
    ("DEPT-001", "Dept of IT"),
    ("DEPT-002", "Dept of Health"),
    ("DEPT-003", "Dept of Infrastructure"),
    ("DEPT-004", "Dept of Education"),
]


def seed(graph_service=None, twin_service=None, clear: bool = False):
    """Populate the graph and services with sample seed data."""
    if clear and graph_service and twin_service:
        print("Clearing existing data...")
        graph_service._vendors.clear()
        graph_service._officials.clear()
        graph_service.rel_service._edges.clear()
        graph_service.rel_service._adjacency.clear()

    # Create vendors
    for vid, name in VENDORS:
        if graph_service:
            graph_service.create_vendor(vid, name)
        if twin_service:
            twin_service.create_vendor(vid, name)
    print(f"✅ Seeded {len(VENDORS)} vendors")

    # Create officials
    for oid, name in OFFICIALS:
        if graph_service:
            graph_service.create_official(oid, name)
        if twin_service:
            twin_service.create_official(oid, name)
    print(f"✅ Seeded {len(OFFICIALS)} officials")

    # Create relationships (vendor → official: employs)
    import random
    random.seed(42)  # Reproducible

    total_edges = 0
    for vid, _ in VENDORS:
        num_officials = random.randint(1, 3)
        chosen = random.sample(OFFICIALS, num_officials)
        for oid, _ in chosen:
            tx_count = random.randint(5, 50)
            if graph_service:
                graph_service.add_relationship(
                    vid, oid, "employs",
                    transaction_count=tx_count,
                )
            if twin_service:
                twin_service.add_relationship(
                    vid, oid, "employed_by",
                    transaction_count=tx_count,
                )
            total_edges += 1

    # Create vendor → department (contracted)
    for vid, _ in VENDORS:
        num_depts = random.randint(1, 2)
        chosen = random.sample(DEPARTMENTS, num_depts)
        for did, _ in chosen:
            if graph_service:
                graph_service.add_relationship(vid, did, "contracted")
            total_edges += 1

    # Create some official → official relationships
    for i in range(len(OFFICIALS) - 1):
        if graph_service:
            graph_service.add_relationship(
                OFFICIALS[i][0], OFFICIALS[i+1][0], "related",
            )
        total_edges += 1

    print(f"✅ Seeded {total_edges} entity relationships")


def main():
    parser = argparse.ArgumentParser(description="Seed GovSpend test data")
    parser.add_argument("--env", default="production", help="Environment to seed")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    args = parser.parse_args()

    print(f"🌱 Seeding initial data for environment: [{args.env}]")
    if HAS_SERVICES:
        gs = GraphService()
        ts = TwinService()
        seed(gs, ts, clear=args.clear)
    else:
        seed(None, None, clear=args.clear)

    print("🎉 Initial seed data populated successfully!")


if __name__ == "__main__":
    main()
