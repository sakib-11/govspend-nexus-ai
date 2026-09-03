"""Load testing for GovSpend Nexus AI using Locust.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8008
"""

from locust import HttpUser, task, between, events
import json
import random


class AuditorUser(HttpUser):
    """Simulate an auditor user — the primary persona."""

    wait_time = between(1, 3)

    def on_start(self):
        """Login on start (if auth endpoint available)."""
        try:
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "load_test_user", "password": "load_test_password"},
            )
            if response.status_code == 200:
                token = response.json().get("access_token", "")
                self.client.headers["Authorization"] = f"Bearer {token}"
        except Exception:
            pass  # No auth endpoint — run without

    @task(3)
    def view_case_queue(self):
        """View case queue — highest frequency."""
        self.client.get("/api/v1/cases/queue", name="/cases/queue")

    @task(2)
    def view_case_detail(self):
        """View case detail."""
        case_id = random.randint(1, 100)
        self.client.get(f"/api/v1/cases/{case_id}", name="/cases/:id")

    @task(2)
    def get_vendor_graph(self):
        """Get vendor digital twin graph."""
        vendor = random.choice(["VEND-001", "VEND-002", "VEND-003", "VEND-004", "VEND-005"])
        self.client.get(
            f"/api/v1/twin/vendor/{vendor}?depth=2",
            name="/twin/vendor/:token",
        )

    @task(1)
    def get_explanation(self):
        """Get AI explanation for a case."""
        case_id = f"CASE-{random.randint(1, 50):03d}"
        self.client.get(f"/api/v1/explanation/case/{case_id}", name="/explanation/case/:id")

    @task(1)
    def search_policies(self):
        """Search policies."""
        query = random.choice(["procurement", "fraud", "compliance", "GFR", "audit"])
        self.client.get(f"/api/v1/policies/search?q={query}", name="/policies/search")

    @task(1)
    def analyse_vendor(self):
        """Analyse vendor network."""
        vendor = random.choice(["VEND-001", "VEND-002", "VEND-003"])
        self.client.get(f"/api/v1/twin/vendor/{vendor}/analyse", name="/twin/vendor/:id/analyse")


class AdminUser(HttpUser):
    """Admin user with heavier read operations."""

    wait_time = between(2, 5)
    weight = 1  # Lower weight than auditors

    @task(2)
    def view_audit_log(self):
        self.client.get("/api/v1/admin/audit-log?limit=20", name="/admin/audit-log")

    @task(1)
    def view_metrics(self):
        self.client.get("/api/v1/admin/metrics/dashboard", name="/admin/metrics")

    @task(1)
    def view_users(self):
        self.client.get("/api/v1/admin/users", name="/admin/users")


class APIHealthUser(HttpUser):
    """Health check user — constant low load."""

    wait_time = between(0.5, 2)
    weight = 2

    @task(5)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def root(self):
        self.client.get("/", name="/")


# ── Lifecycle events ─────────────────────────────────────────────


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("🚀 Starting load test for GovSpend Nexus AI")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.runner.stats
    total = stats.total.requests
    fail = stats.total.failures
    rps = stats.total.current_rps if hasattr(stats.total, "current_rps") else 0
    print(f"📊 Load test complete: {total} requests, {fail} failures, {rps:.1f} req/s")
