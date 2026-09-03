"""Digital Twin service — production configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class DigitalTwinConfig(BaseSettings):
    """Configuration for the Digital Twin service."""

    # ── Service ──────────────────────────────────────────────────────
    service_name: str = "digital-twin-svc"
    port: int = 8007
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "govspend"
    db_user: str = "twin_user"
    db_password: str = "twin_pass"
    db_min_pool: int = 5
    db_max_pool: int = 20

    # ── Redis ────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    cache_ttl_seconds: int = 300  # 5 minutes

    # ── Graph Settings ───────────────────────────────────────────────
    max_graph_depth: int = 5
    default_graph_depth: int = 2
    max_nodes_returned: int = 500
    max_edges_returned: int = 1000
    enable_caching: bool = True

    # ── Rate Limiting ────────────────────────────────────────────────
    rate_limit_per_minute: int = 60

    # ── Performance ──────────────────────────────────────────────────
    query_timeout_seconds: int = 30

    # ── HMAC / Auth ──────────────────────────────────────────────────
    hmac_secret: str = "digital-twin-secret-change-in-production"

    model_config = {
        "env_prefix": "TWIN_",
        "env_file": ".env.twin",
        "extra": "ignore",
    }


@lru_cache()
def get_config() -> DigitalTwinConfig:
    return DigitalTwinConfig()
